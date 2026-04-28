from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import messagebox


@dataclass(frozen=True)
class DerivationStep:
	before: Tuple[str, ...]
	after: Tuple[str, ...]
	expanded_nonterminal: str
	production: Tuple[str, ...]
	index: int


@dataclass(frozen=True)
class DerivationResult:
	forms: List[Tuple[str, ...]]
	steps: List[DerivationStep]


class Node:
	def __init__(self, symbol: str) -> None:
		self.symbol = symbol
		self.children: List[Node] = []


class Grammar:
	def __init__(self, rules: Dict[str, List[Tuple[str, ...]]], start_symbol: str) -> None:
		self.rules = rules
		self.start_symbol = start_symbol
		self.nonterminals = set(rules.keys())
		self.terminals = {
			sym
			for prods in rules.values()
			for prod in prods
			for sym in prod
			if sym and sym not in self.nonterminals
		}

	@staticmethod
	def tokenize(text: str) -> List[str]:
		# Tokens: identificadores, números o cualquier símbolo individual.
		return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S", text)

	def tokenize_target(self, text: str) -> List[str]:
		"""Tokeniza una expresión objetivo.

		Si la gramática usa el terminal `id`, normaliza cualquier identificador o número
		(no conocido por la gramática) a `id`. Esto permite entradas como:
		`X + 5 * Y` con la gramática de ejemplo `F -> ( E ) | id`.
		"""
		tokens = Grammar.tokenize(text)
		if "id" not in self.terminals:
			return tokens

		out: List[str] = []
		for tok in tokens:
			if tok in self.terminals or self.is_nonterminal(tok):
				out.append(tok)
			elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*|\d+", tok):
				out.append("id")
			else:
				out.append(tok)
		return out

	@staticmethod
	def from_text(text: str) -> "Grammar":
		rules: Dict[str, List[Tuple[str, ...]]] = {}
		start: Optional[str] = None

		for raw_line in text.splitlines():
			line = raw_line.strip()
			if not line or line.startswith("#"):
				continue
			if "->" not in line:
				raise ValueError(f"Linea invalida: '{line}'. Usa A -> B C | d")
			lhs, rhs = line.split("->", 1)
			lhs = lhs.strip()
			rhs = rhs.strip()
			if not lhs:
				raise ValueError(f"No terminal vacio en: '{line}'")
			if start is None:
				start = lhs
			alts = [alt.strip() for alt in rhs.split("|")]
			rules.setdefault(lhs, [])
			for alt in alts:
				if alt in {"", "ε", "epsilon", "lambda"}:
					rules[lhs].append(tuple())
				else:
					rules[lhs].append(tuple(Grammar.tokenize(alt)))

		if not rules or start is None:
			raise ValueError("No se detectaron reglas validas.")
		return Grammar(rules, start)

	def is_nonterminal(self, sym: str) -> bool:
		return sym in self.nonterminals


class DerivationEngine:
	def __init__(self, grammar: Grammar) -> None:
		self.g = grammar

	def derive(self, target: List[str], left: bool, max_steps: int) -> DerivationResult:
		initial = (self.g.start_symbol,)

		for depth in range(0, max_steps + 1):
			seen: set[Tuple[Tuple[str, ...], int]] = set()
			steps: List[DerivationStep] = []
			res = self._dfs(initial, tuple(target), left, depth, steps, seen)
			if res is not None:
				forms = [initial]
				for st in res:
					forms.append(st.after)
				return DerivationResult(forms=forms, steps=res)

		side = "izquierda" if left else "derecha"
		raise ValueError(f"No se encontro derivacion por {side} en <= {max_steps} pasos")

	def _dfs(
		self,
		current: Tuple[str, ...],
		target: Tuple[str, ...],
		left: bool,
		remaining: int,
		steps: List[DerivationStep],
		seen: set[Tuple[Tuple[str, ...], int]],
	) -> Optional[List[DerivationStep]]:
		key = (current, remaining)
		if key in seen:
			return None
		seen.add(key)

		if self._all_terminals(current):
			return steps if current == target else None
		if remaining == 0:
			return None
		if not self._promising(current, target):
			return None

		nonterm_idxs = [i for i, s in enumerate(current) if self.g.is_nonterminal(s)]
		if not nonterm_idxs:
			return None
		idx = nonterm_idxs[0] if left else nonterm_idxs[-1]
		A = current[idx]
		for prod in self.g.rules.get(A, []):
			next_form = current[:idx] + prod + current[idx + 1 :]
			step = DerivationStep(
				before=current,
				after=next_form,
				expanded_nonterminal=A,
				production=prod,
				index=idx,
			)
			out = self._dfs(next_form, target, left, remaining - 1, steps + [step], seen)
			if out is not None:
				return out
		return None

	def _all_terminals(self, symbols: Tuple[str, ...]) -> bool:
		return all(not self.g.is_nonterminal(s) for s in symbols)

	def _promising(self, current: Tuple[str, ...], target: Tuple[str, ...]) -> bool:
		# Cota simple para evitar explosión: no producir más terminales que el objetivo.
		terminals = [s for s in current if not self.g.is_nonterminal(s)]
		if len(terminals) > len(target):
			return False
		# Prefijo terminal fijo debe coincidir.
		first_nt = next((i for i, s in enumerate(current) if self.g.is_nonterminal(s)), None)
		if first_nt is not None:
			prefix = [s for s in current[:first_nt] if not self.g.is_nonterminal(s)]
			if tuple(prefix) != target[: len(prefix)]:
				return False
		# Sufijo terminal fijo debe coincidir.
		last_nt = next((i for i in range(len(current) - 1, -1, -1) if self.g.is_nonterminal(current[i])), None)
		if last_nt is not None:
			suffix = [s for s in current[last_nt + 1 :] if not self.g.is_nonterminal(s)]
			if suffix and tuple(suffix) != target[-len(suffix) :]:
				return False
		# Longitud total razonable.
		if len(current) > len(target) + 20:
			return False
		return True


class TreeBuilder:
	def __init__(self, grammar: Grammar) -> None:
		self.g = grammar

	def build_derivation_tree(self, result: DerivationResult) -> Node:
		root = Node(self.g.start_symbol)
		# Mantiene la lista de nodos que corresponden a la forma sentencial actual.
		form_nodes: List[Node] = [root]
		for step in result.steps:
			if step.index < 0 or step.index >= len(form_nodes):
				raise ValueError("Inconsistencia al construir el arbol")
			node = form_nodes[step.index]
			# Reemplaza el no terminal por sus hijos (terminales o no terminales).
			node.children = [Node(sym) for sym in step.production] or [Node("ε")]
			form_nodes = form_nodes[: step.index] + node.children + form_nodes[step.index + 1 :]
		return root

	def build_ast(self, derivation_root: Node) -> Node:
		punct = {"(", ")", "[", "]", "{", "}", ",", ";"}

		def simplify(n: Node) -> Optional[Node]:
			if n.symbol in {"ε", "epsilon", "lambda"}:
				return None
			kids: List[Node] = []
			for c in n.children:
				s = simplify(c)
				if s is not None:
					kids.append(s)
			is_nt = self.g.is_nonterminal(n.symbol)
			if (not is_nt) and n.symbol in punct:
				return None
			if is_nt and len(kids) == 1:
				return kids[0]
			m = Node(n.symbol)
			m.children = kids
			return m

		out = simplify(derivation_root)
		return out if out is not None else Node("AST")


class CanvasTree:
	def __init__(self, parent: tk.Widget, bg: str = "white") -> None:
		frame = tk.Frame(parent, bg=bg)
		self.frame = frame
		self.canvas = tk.Canvas(frame, bg=bg, highlightthickness=0)
		self.hbar = tk.Scrollbar(frame, orient="horizontal", command=self.canvas.xview)
		self.vbar = tk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
		self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
		self.canvas.grid(row=0, column=0, sticky="nsew")
		self.vbar.grid(row=0, column=1, sticky="ns")
		self.hbar.grid(row=1, column=0, sticky="ew")
		frame.rowconfigure(0, weight=1)
		frame.columnconfigure(0, weight=1)

	def clear(self) -> None:
		self.canvas.delete("all")
		self.canvas.configure(scrollregion=(0, 0, 1, 1))

	def render(self, root: Node) -> None:
		self.clear()

		node_w = 44
		node_h = 22
		x_gap = 18
		y_gap = 56
		margin = 20

		# Layout: x para hojas por orden; x nodo = promedio de hijos.
		leaf_x = 0
		pos: Dict[int, Tuple[float, int]] = {}

		def layout(n: Node, depth: int) -> float:
			nonlocal leaf_x
			if not n.children:
				x = leaf_x
				leaf_x += 1
				pos[id(n)] = (x, depth)
				return x
			xs = [layout(c, depth + 1) for c in n.children]
			x = sum(xs) / len(xs)
			pos[id(n)] = (x, depth)
			return x

		layout(root, 0)

		# Convert x-units to pixels
		max_x_unit = max(x for x, _ in pos.values()) if pos else 0
		max_depth = max(d for _, d in pos.values()) if pos else 0
		width = int(margin * 2 + (max_x_unit + 1) * (node_w + x_gap))
		height = int(margin * 2 + (max_depth + 1) * y_gap)
		self.canvas.configure(scrollregion=(0, 0, width, height))

		def to_xy(x_unit: float, depth: int) -> Tuple[int, int]:
			x = int(margin + x_unit * (node_w + x_gap))
			y = int(margin + depth * y_gap)
			return x, y

		# Draw edges then nodes
		def draw_edges(n: Node) -> None:
			xu, d = pos[id(n)]
			x, y = to_xy(xu, d)
			for c in n.children:
				xu2, d2 = pos[id(c)]
				x2, y2 = to_xy(xu2, d2)
				self.canvas.create_line(
					x + node_w // 2,
					y + node_h,
					x2 + node_w // 2,
					y2,
					fill="#333333",
				)
				draw_edges(c)

		def draw_nodes(n: Node) -> None:
			xu, d = pos[id(n)]
			x, y = to_xy(xu, d)
			self.canvas.create_rectangle(
				x,
				y,
				x + node_w,
				y + node_h,
				outline="#333333",
				fill="#ffffff",
			)
			label = n.symbol
			if len(label) > 6:
				label = label[:6] + "…"
			self.canvas.create_text(
				x + node_w // 2,
				y + node_h // 2,
				text=label,
				fill="#111111",
				font=("Arial", 11),
			)
			for c in n.children:
				draw_nodes(c)

		draw_edges(root)
		draw_nodes(root)


class App(tk.Tk):
	def __init__(self) -> None:
		super().__init__()
		self.title("CFG: Derivacion, Arbol de Derivacion y AST")
		self.geometry("1200x780")
		
		# Colores limpios y profesionales para Windows
		self._bg = "#f0f0f0"
		self._fg = "#000000"
		self._muted = "#666666"
		self._field_bg = "#ffffff"
		self._field_fg = "#000000"
		self.configure(bg=self._bg)

		self._build_ui()
		self._load_example()

	def _build_ui(self) -> None:
		bg = self._bg
		fg = self._fg
		muted = self._muted
		field_bg = self._field_bg
		field_fg = self._field_fg
		field_border = {"relief": "solid", "bd": 1}
		controls_bg = "#ffffff"
		controls_fg = "#000000"
		controls_muted = "#666666"

		# Layout original: controles arriba, salida al centro, acciones abajo
		self.grid_rowconfigure(1, weight=1)
		self.grid_columnconfigure(0, weight=1)

		controls = tk.Frame(self, bg=controls_bg)
		controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
		# Hacemos que la columna de expresion tenga espacio garantizado.
		controls.grid_columnconfigure(0, weight=0, minsize=420)
		controls.grid_columnconfigure(1, weight=1, minsize=320)
		controls.grid_columnconfigure(2, weight=0, minsize=140)
		controls.grid_columnconfigure(3, weight=0, minsize=90)

		tk.Label(controls, text="Gramatica (A -> B C | d)", bg=controls_bg, fg=controls_fg).grid(
			row=0, column=0, sticky="w"
		)
		tk.Label(controls, text="Expresion objetivo", bg=controls_bg, fg=controls_fg).grid(
			row=0, column=1, sticky="w"
		)
		tk.Label(controls, text="Derivacion", bg=controls_bg, fg=controls_fg).grid(row=0, column=2, sticky="w")
		tk.Label(controls, text="Max pasos", bg=controls_bg, fg=controls_fg).grid(row=0, column=3, sticky="w")

		self.grammar_txt = tk.Text(
			controls,
			height=6,
			width=48,
			bg=field_bg,
			fg=field_fg,
			insertbackground=field_fg,
			**field_border,
		)
		self.grammar_txt.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(4, 0))

		expr_frame = tk.Frame(controls, bg=controls_bg)
		expr_frame.grid(row=1, column=1, sticky="nsew", padx=(0, 10), pady=(4, 0))
		expr_frame.grid_columnconfigure(0, weight=1)
		self.expr_entry = tk.Entry(
			expr_frame,
			bg=field_bg,
			fg=field_fg,
			insertbackground=field_fg,
			font=("Arial", 11),
			**field_border,
		)
		self.expr_entry.grid(row=0, column=0, sticky="ew")

		self.mode = tk.StringVar(value="left")
		mframe = tk.Frame(controls, bg=controls_bg)
		mframe.grid(row=1, column=2, sticky="w", padx=(0, 10), pady=(4, 0))
		tk.Radiobutton(
			mframe,
			text="Izquierda",
			variable=self.mode,
			value="left",
			bg=controls_bg,
			fg=controls_fg,
		).pack(anchor="w")
		tk.Radiobutton(
			mframe,
			text="Derecha",
			variable=self.mode,
			value="right",
			bg=controls_bg,
			fg=controls_fg,
		).pack(anchor="w")

		self.max_steps_var = tk.IntVar(value=25)
		self.max_steps_spin = tk.Spinbox(
			controls,
			from_=1,
			to=200,
			textvariable=self.max_steps_var,
			width=6,
			bg=field_bg,
			fg=field_fg,
			insertbackground=field_fg,
			**field_border,
		)
		self.max_steps_spin.grid(row=1, column=3, sticky="w", pady=(4, 0))

		btns = tk.Frame(self, bg=bg)
		btns.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
		btns.grid_columnconfigure(1, weight=1)
		self.status = tk.Label(btns, text="Listo", bg=bg, fg=fg)
		self.status.grid(row=0, column=0, sticky="w")
		tk.Button(btns, text="Generar", command=self._generate).grid(row=0, column=2, sticky="e")

		# Area de salida: selector de vista + stack de frames
		out = tk.Frame(self, bg=bg)
		out.grid(row=1, column=0, sticky="nsew", padx=10)
		out.grid_rowconfigure(1, weight=1)
		out.grid_columnconfigure(0, weight=1)

		self.view = tk.StringVar(value="derivation")
		vbar = tk.Frame(out, bg=bg)
		vbar.grid(row=0, column=0, sticky="w")
		for text, value in (
			("Derivacion", "derivation"),
			("Arbol de Derivacion", "tree"),
			("AST", "ast"),
		):
			tk.Radiobutton(
				vbar,
				text=text,
				variable=self.view,
				value=value,
				bg=bg,
				fg=fg,
				command=self._switch_view,
			).pack(side="left", padx=(0, 10))

		self.stack = tk.Frame(out, bg=bg)
		self.stack.grid(row=1, column=0, sticky="nsew")
		self.stack.grid_rowconfigure(0, weight=1)
		self.stack.grid_columnconfigure(0, weight=1)

		self.frame_derivation = tk.Frame(self.stack, bg=bg)
		self.frame_tree = tk.Frame(self.stack, bg=bg)
		self.frame_ast = tk.Frame(self.stack, bg=bg)
		for f in (self.frame_derivation, self.frame_tree, self.frame_ast):
			f.grid(row=0, column=0, sticky="nsew")

		self.derivation_out = tk.Text(
			self.frame_derivation,
			bg=field_bg,
			fg=field_fg,
			insertbackground=field_fg,
			**field_border,
		)
		self.derivation_out.pack(fill="both", expand=True)

		self.tree_canvas = CanvasTree(self.frame_tree)
		self.tree_canvas.frame.pack(fill="both", expand=True)

		self.ast_canvas = CanvasTree(self.frame_ast)
		self.ast_canvas.frame.pack(fill="both", expand=True)

		self._switch_view()

	def _switch_view(self) -> None:
		view = self.view.get()
		if view == "derivation":
			self.frame_derivation.tkraise()
		elif view == "tree":
			self.frame_tree.tkraise()
		else:
			self.frame_ast.tkraise()

	def _load_example(self) -> None:
		ex = "".join(
			[
				"E -> E + T | T\n",
				"T -> T * F | F\n",
				"F -> ( E ) | id\n",
			]
		)
		self.grammar_txt.insert("1.0", ex)
		self.expr_entry.delete(0, "end")

	def _generate(self) -> None:
		try:
			grammar_text = self.grammar_txt.get("1.0", "end").strip()
			expr_text = self.expr_entry.get().strip()
			if not grammar_text:
				raise ValueError("Ingresa una gramatica")
			if not expr_text:
				raise ValueError("Ingresa la expresion objetivo")

			g = Grammar.from_text(grammar_text)
			target = g.tokenize_target(expr_text)
			left = self.mode.get() == "left"
			max_steps = int(self.max_steps_var.get())

			engine = DerivationEngine(g)
			result = engine.derive(target=target, left=left, max_steps=max_steps)
			builder = TreeBuilder(g)
			tree = builder.build_derivation_tree(result)
			ast = builder.build_ast(tree)

			self._show_derivation(result)
			self.tree_canvas.render(tree)
			self.ast_canvas.render(ast)
			self.status.config(text="Generado correctamente")
		except Exception as e:
			self.status.config(text="Error")
			messagebox.showerror("Error", str(e))

	def _show_derivation(self, result: DerivationResult) -> None:
		self.derivation_out.delete("1.0", "end")
		for i, form in enumerate(result.forms):
			text_form = " ".join(form) if form else "ε"
			self.derivation_out.insert("end", f"Paso {i}: {text_form}\n")
			if i > 0:
				step = result.steps[i - 1]
				rhs = " ".join(step.production) if step.production else "ε"
				self.derivation_out.insert(
					"end",
					f"  Regla: {step.expanded_nonterminal} -> {rhs} (pos {step.index})\n",
				)
		self.derivation_out.see("1.0")


if __name__ == "__main__":
	App().mainloop()

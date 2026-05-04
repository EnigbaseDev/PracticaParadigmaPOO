from __future__ import annotations

"""UI Tkinter para la práctica CFG.

Depende del núcleo en cfg_core.py.
"""

from typing import Dict, List, Tuple
import tkinter as tk
from tkinter import messagebox

from cfg_core import DerivationEngine, DerivationResult, Grammar, TreeBuilder, Node


class CanvasTree:
	"""Renderiza un árbol en un Canvas con scroll (layout simple por niveles)."""

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
		"""Dibuja el árbol: primero calcula posiciones, luego aristas y nodos."""
		self.clear()

		node_w = 44
		node_h = 22
		x_gap = 18
		y_gap = 56
		margin = 20

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

		max_x_unit = max(x for x, _ in pos.values()) if pos else 0
		max_depth = max(d for _, d in pos.values()) if pos else 0
		width = int(margin * 2 + (max_x_unit + 1) * (node_w + x_gap))
		height = int(margin * 2 + (max_depth + 1) * y_gap)
		self.canvas.configure(scrollregion=(0, 0, width, height))

		def to_xy(x_unit: float, depth: int) -> Tuple[int, int]:
			x = int(margin + x_unit * (node_w + x_gap))
			y = int(margin + depth * y_gap)
			return x, y

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
	"""Interfaz gráfica: entrada de gramática/expresión + vista de resultados."""

	def __init__(self) -> None:
		super().__init__()
		self.title("CFG: Derivacion, Arbol de Derivacion y AST")
		self.geometry("1200x780")

		self._bg = "#f0f0f0"
		self._fg = "#000000"
		self._field_bg = "#ffffff"
		self._field_fg = "#000000"
		self.configure(bg=self._bg)

		self._build_ui()
		self._load_example()

	def _build_ui(self) -> None:
		bg = self._bg
		fg = self._fg
		field_bg = self._field_bg
		field_fg = self._field_fg
		field_border = {"relief": "solid", "bd": 1}
		controls_bg = "#ffffff"
		controls_fg = "#000000"

		self.grid_rowconfigure(1, weight=1)
		self.grid_columnconfigure(0, weight=1)

		controls = tk.Frame(self, bg=controls_bg)
		controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
		controls.grid_columnconfigure(0, weight=0, minsize=420)
		controls.grid_columnconfigure(1, weight=1, minsize=320)
		controls.grid_columnconfigure(2, weight=0, minsize=140)

		tk.Label(controls, text="Gramatica (A -> B C | d)", bg=controls_bg, fg=controls_fg).grid(
			row=0, column=0, sticky="w"
		)
		tk.Label(controls, text="Expresion objetivo", bg=controls_bg, fg=controls_fg).grid(
			row=0, column=1, sticky="w"
		)
		tk.Label(controls, text="Derivacion", bg=controls_bg, fg=controls_fg).grid(row=0, column=2, sticky="w")

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

		btns = tk.Frame(self, bg=bg)
		btns.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
		btns.grid_columnconfigure(1, weight=1)
		self.status = tk.Label(btns, text="Listo", bg=bg, fg=fg)
		self.status.grid(row=0, column=0, sticky="w")
		tk.Button(btns, text="Generar", command=self._generate).grid(row=0, column=2, sticky="e")

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
		self.expr_entry.insert(0, "id + id * id")

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
			max_steps = 25

			engine = DerivationEngine(g)
			result = engine.derive(target=target, left=left, max_steps=max_steps)
			builder = TreeBuilder(g)
			tree = builder.build_derivation_tree(result)
			builder.apply_lexemes(tree, target)
			ast = builder.build_ast(tree)

			self._show_derivation(result, g, target)
			self.tree_canvas.render(tree)
			self.ast_canvas.render(ast)
			self.status.config(text="Generado correctamente")
		except Exception as e:
			self.status.config(text="Error")
			messagebox.showerror("Error", str(e))

	@staticmethod
	def _align_form(form: Tuple[str, ...], grammar: Grammar, target_tokens: List[str]) -> List[str]:
		i = 0
		out: List[str] = []

		from cfg_core import is_ident_or_number, is_identifier, is_number

		for sym in form:
			if grammar.is_nonterminal(sym):
				out.append(sym)
				continue
			if sym in {"ε", "epsilon", "lambda"}:
				out.append("ε")
				continue
			if sym in {"id", "identifier", "number"}:
				pred = (
					is_identifier
					if sym == "identifier"
					else is_number
					if sym == "number"
					else is_ident_or_number
				)
				while i < len(target_tokens) and not pred(target_tokens[i]):
					i += 1
				out.append(target_tokens[i] if i < len(target_tokens) else sym)
				if i < len(target_tokens):
					i += 1
				continue

			while i < len(target_tokens) and target_tokens[i] != sym:
				i += 1
			out.append(sym)
			if i < len(target_tokens):
				i += 1

		return out

	def _show_derivation(self, result: DerivationResult, grammar: Grammar, target_tokens: List[str]) -> None:
		self.derivation_out.delete("1.0", "end")
		forms: List[Tuple[str, ...]] = [result.start]
		for st in result.steps:
			forms.append(st.form)

		for i, form in enumerate(forms):
			aligned = self._align_form(form, grammar, target_tokens)
			text_form = " ".join(aligned) if aligned else "ε"
			self.derivation_out.insert("end", f"Paso {i}: {text_form}\n")
			if i > 0:
				step = result.steps[i - 1]
				if not step.production:
					rhs = "ε"
				else:
					aligned_after = self._align_form(step.form, grammar, target_tokens)
					rhs_parts: List[str] = []
					for k, sym in enumerate(step.production):
						pos = step.index + k
						if sym in {"id", "identifier", "number"} and 0 <= pos < len(aligned_after):
							rhs_parts.append(aligned_after[pos])
						else:
							rhs_parts.append(sym)
					rhs = " ".join(rhs_parts)
				self.derivation_out.insert(
					"end",
					f"  Regla: {step.nonterminal} -> {rhs} (pos {step.index})\n",
				)
		self.derivation_out.see("1.0")

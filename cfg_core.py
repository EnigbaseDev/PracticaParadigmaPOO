from __future__ import annotations

"""Núcleo CFG: tokenización, derivación, árbol de derivación y AST.

- No depende de Tkinter (solo lógica).
- Soporta comodines terminales: `id`, `identifier`, `number`.
"""

from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional, Tuple


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUM_RE = re.compile(r"^\d+$")


def is_identifier(tok: str) -> bool:
	return _IDENT_RE.fullmatch(tok) is not None


def is_number(tok: str) -> bool:
	return _NUM_RE.fullmatch(tok) is not None


def is_ident_or_number(tok: str) -> bool:
	return is_identifier(tok) or is_number(tok)


def wildcard_matches(grammar_sym: str, target_tok: str) -> bool:
	"""Soporta comodines comunes: id, identifier, number."""
	if grammar_sym == "id":
		return is_ident_or_number(target_tok)
	if grammar_sym == "identifier":
		return is_identifier(target_tok)
	if grammar_sym == "number":
		return is_number(target_tok)
	return False


@dataclass(frozen=True)
class DerivationStep:
	"""Un paso de derivación: expandir un no terminal en una posición."""

	nonterminal: str
	production: Tuple[str, ...]
	index: int
	form: Tuple[str, ...]


@dataclass(frozen=True)
class DerivationResult:
	"""Resultado de derivación: símbolo inicial + lista de pasos aplicados."""

	start: Tuple[str, ...]
	steps: List[DerivationStep]


@dataclass
class Node:
	"""Nodo para representar árbol (derivación o AST)."""

	symbol: str
	children: List["Node"] = field(default_factory=list)


class Grammar:
	"""Representa una gramática libre de contexto (CFG)."""

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
		"""Convierte un string a tokens: identificadores, números o símbolos individuales."""
		return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S", text)

	def tokenize_target(self, text: str) -> List[str]:
		"""Tokeniza una expresión objetivo."""
		return Grammar.tokenize(text)

	@staticmethod
	def from_text(text: str) -> "Grammar":
		"""Construye la gramática desde un texto con reglas `A -> ... | ...`."""
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
	"""Busca una derivación (izquierda o derecha) hasta llegar al objetivo."""

	def __init__(self, grammar: Grammar) -> None:
		self.g = grammar

	def derive(self, target: List[str], left: bool, max_steps: int) -> DerivationResult:
		"""Intenta derivar `target` en <= `max_steps` expansiones."""
		start = (self.g.start_symbol,)
		target_t = tuple(target)

		for depth in range(0, max_steps + 1):
			seen: set[Tuple[Tuple[str, ...], int]] = set()
			res = self._dfs(start, target_t, left, depth, [], seen)
			if res is not None:
				return DerivationResult(start=start, steps=res)

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
			return steps if self._matches(current, target) else None
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
			step = DerivationStep(nonterminal=A, production=prod, index=idx, form=next_form)
			out = self._dfs(next_form, target, left, remaining - 1, steps + [step], seen)
			if out is not None:
				return out
		return None

	def _all_terminals(self, symbols: Tuple[str, ...]) -> bool:
		return all(not self.g.is_nonterminal(s) for s in symbols)

	def _term_matches(self, grammar_sym: str, target_tok: str) -> bool:
		if grammar_sym == target_tok:
			return True
		return wildcard_matches(grammar_sym, target_tok)

	def _matches(self, form: Tuple[str, ...], target: Tuple[str, ...]) -> bool:
		if len(form) != len(target):
			return False
		for a, b in zip(form, target):
			if self.g.is_nonterminal(a):
				return False
			if not self._term_matches(a, b):
				return False
		return True

	def _promising(self, current: Tuple[str, ...], target: Tuple[str, ...]) -> bool:
		"""Poda ligera para reducir explosión combinatoria."""
		if sum(1 for s in current if not self.g.is_nonterminal(s)) > len(target):
			return False

		first_nt = next((i for i, s in enumerate(current) if self.g.is_nonterminal(s)), None)
		if first_nt is not None:
			prefix = [s for s in current[:first_nt] if not self.g.is_nonterminal(s)]
			if len(prefix) > len(target):
				return False
			for a, b in zip(prefix, target[: len(prefix)]):
				if not self._term_matches(a, b):
					return False

		return len(current) <= len(target) + 20


class TreeBuilder:
	"""Construye el árbol de derivación y un AST simplificado a partir de la derivación."""

	def __init__(self, grammar: Grammar) -> None:
		self.g = grammar

	def build_derivation_tree(self, result: DerivationResult) -> Node:
		root = Node(self.g.start_symbol)
		form_nodes: List[Node] = [root]
		for step in result.steps:
			if step.index < 0 or step.index >= len(form_nodes):
				raise ValueError("Inconsistencia al construir el arbol")
			node = form_nodes[step.index]
			node.children = [Node(sym) for sym in step.production] or [Node("ε")]
			form_nodes = form_nodes[: step.index] + node.children + form_nodes[step.index + 1 :]
		return root

	def apply_lexemes(self, root: Node, target_tokens: List[str]) -> None:
		"""Reemplaza hojas id/identifier/number por lexemas reales."""
		i = 0

		def walk(n: Node) -> None:
			nonlocal i
			if not n.children:
				if n.symbol in {"ε", "epsilon", "lambda"}:
					return
				if n.symbol in {"id", "identifier", "number"}:
					pred = (
						is_identifier
						if n.symbol == "identifier"
						else is_number
						if n.symbol == "number"
						else is_ident_or_number
					)
					while i < len(target_tokens) and not pred(target_tokens[i]):
						i += 1
					if i < len(target_tokens):
						n.symbol = target_tokens[i]
						i += 1
					return
				# Terminal literal: consumir hasta alinear.
				while i < len(target_tokens) and target_tokens[i] != n.symbol:
					i += 1
				if i < len(target_tokens):
					i += 1
				return
			for c in n.children:
				walk(c)

		walk(root)

	def build_ast(self, derivation_root: Node) -> Node:
		"""AST genérico: elimina no-terminales y pliega binarios <izq op der>."""
		punct = {"(", ")", "[", "]", "{", "}", ",", ";"}
		bin_ops = {"+", "-", "*", "/"}

		def to_ast(n: Node) -> Optional[Node]:
			if n.symbol in {"ε", "epsilon", "lambda"}:
				return None
			if not n.children:
				return None if n.symbol in punct else Node(n.symbol)

			kids: List[Node] = []
			for c in n.children:
				k = to_ast(c)
				if k is not None:
					kids.append(k)

			if self.g.is_nonterminal(n.symbol):
				if len(kids) == 1:
					return kids[0]
				if len(kids) == 3 and not kids[1].children and kids[1].symbol in bin_ops:
					op = Node(kids[1].symbol, [kids[0], kids[2]])
					return op
				return Node(n.symbol, kids)

			return Node(n.symbol, kids)

		out = to_ast(derivation_root)
		return out if out is not None else Node("AST")

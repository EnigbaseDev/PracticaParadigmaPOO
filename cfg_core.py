from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import re

import nltk
from nltk import CFG, ChartParser, Tree, Production

# Aseguramos que el tokenizador de NLTK esté disponible silenciosamente
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


@dataclass(frozen=True)
class DerivationStep:
    nonterminal: str
    production: Tuple[str, ...]
    index: int
    form: Tuple[str, ...]


@dataclass(frozen=True)
class DerivationResult:
    start: Tuple[str, ...]
    steps: List[DerivationStep]
    nltk_tree: Optional[Tree] = None


@dataclass
class Node:
    symbol: str
    children: List["Node"] = field(default_factory=list)


class Grammar:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.start_symbol = ""
        self.terminals = set()
        self.nonterminals = set()

        lines = raw_text.splitlines()
        for line in lines:
            if "->" in line:
                lhs = line.split("->")[0].strip()
                self.nonterminals.add(lhs)
                if not self.start_symbol:
                    self.start_symbol = lhs

    @staticmethod
    def tokenize_target(text: str) -> List[str]:
        return re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|\S", text)

    @staticmethod
    def from_text(text: str) -> "Grammar":
        return Grammar(text)

    def is_nonterminal(self, sym: str) -> bool:
        return sym in self.nonterminals

    def get_nltk_string(self) -> str:
        """Convierte el texto de la UI al formato estricto de NLTK (Terminales en comillas)."""
        nltk_lines = []
        for line in self.raw_text.splitlines():
            if "->" not in line: continue
            lhs, rhs = line.split("->", 1)
            alts = rhs.split("|")
            new_alts = []
            for alt in alts:
                tokens = [t.strip() for t in Grammar.tokenize_target(alt)]
                new_tokens = []
                for t in tokens:
                    if t in self.nonterminals:
                        new_tokens.append(t)
                    elif t in {"ε", "epsilon", "lambda"}:
                        new_tokens.append("''")
                    else:
                        new_tokens.append(f"'{t}'")
                new_alts.append(" ".join(new_tokens) if new_tokens else "''")
            nltk_lines.append(f"{lhs.strip()} -> {' | '.join(new_alts)}")
        return "\n".join(nltk_lines)


class DerivationEngine:
    def __init__(self, grammar: Grammar):
        self.g = grammar
        nltk_format = self.g.get_nltk_string()
        self.nltk_grammar = CFG.fromstring(nltk_format)
        self.parser = ChartParser(self.nltk_grammar)

    @staticmethod
    def _get_leftmost_productions(tree: Tree) -> List[Production]:
        """Extrae el orden de producciones simulando derivación por la izquierda."""
        return tree.productions()

    def _get_rightmost_productions(self, tree: Tree) -> List[Production]:
        """Extrae el orden de producciones simulando derivación por la derecha."""
        prods = [tree.productions()[0]]
        for child in reversed(tree):
            if isinstance(child, Tree):
                prods.extend(self._get_rightmost_productions(child))
        return prods

    def derive(self, target: List[str], left: bool) -> DerivationResult:
        mapped_target = []
        for t in target:
            if re.fullmatch(r"\d+", t):
                mapped_target.append("num")
            elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", t) and t not in self.g.nonterminals and t not in {"id", "num"}:
                mapped_target.append("id")
            else:
                mapped_target.append(t)

        trees = list(self.parser.parse(mapped_target))
        if not trees:
            raise ValueError("NLTK ChartParser no encontro una derivacion valida para esta expresion.")

        best_tree = trees[0]

        # 1. Extraemos las reglas genéricas (con 'num', 'id') ANTES de modificar el árbol
        if left:
            generic_prods = self._get_leftmost_productions(best_tree)
        else:
            generic_prods = self._get_rightmost_productions(best_tree)

        # 2. Inyectamos los lexemas reales (29, 13, c) en las hojas
        leaf_positions = best_tree.treepositions('leaves')
        target_idx = 0
        for pos in leaf_positions:
            if best_tree[pos] != "''" and target_idx < len(target):
                best_tree[pos] = f"'{target[target_idx]}'"
                target_idx += 1

        # 3. Extraemos las reglas literales DESPUÉS de modificar el árbol para armar la cadena visual
        if left:
            literal_prods = self._get_leftmost_productions(best_tree)
        else:
            literal_prods = self._get_rightmost_productions(best_tree)

        current_form = [self.g.start_symbol]
        steps = []

        # Recorremos ambas listas al mismo tiempo
        for gen_prod, lit_prod in zip(generic_prods, literal_prods):
            lhs = str(lit_prod.lhs())

            # Formato literal para la cadena (ej: 29)
            lit_rhs = [str(sym).strip("'") for sym in lit_prod.rhs()]
            if lit_rhs == ['']: lit_rhs = ['ε']

            # Formato genérico para la regla (ej: num)
            gen_rhs = [str(sym).strip("'") for sym in gen_prod.rhs()]
            if gen_rhs == ['']: gen_rhs = ['ε']

            if left:
                idx = current_form.index(lhs)
            else:
                idx = len(current_form) - 1 - current_form[::-1].index(lhs)

            next_form = current_form[:idx] + (lit_rhs if lit_rhs != ['ε'] else []) + current_form[idx + 1:]

            steps.append(DerivationStep(
                nonterminal=lhs,
                production=tuple(gen_rhs),  # Guarda la regla matemática genérica
                index=idx,
                form=tuple(next_form)  # Guarda la expansión visual con números reales
            ))
            current_form = next_form

        return DerivationResult(
            start=(self.g.start_symbol,),
            steps=steps,
            nltk_tree=best_tree
        )


class TreeBuilder:
    def __init__(self, grammar: Grammar):
        self.g = grammar

    def build_derivation_tree(self, result: DerivationResult) -> Node:
        """El Adaptador: Convierte árboles NLTK a nuestra estructura Node para PyQt6."""
        if not result.nltk_tree:
            return Node(self.g.start_symbol)

        def translate(nltk_obj) -> Node:
            if isinstance(nltk_obj, str):
                clean_str = nltk_obj.strip("'")
                return Node(clean_str if clean_str else "ε")

            node = Node(str(nltk_obj.label()))
            for child in nltk_obj:
                node.children.append(translate(child))
            return node

        return translate(result.nltk_tree)

    @staticmethod
    def apply_lexemes(root: Node, target_tokens: List[str]) -> None:
        """Restaura los valores reales (ej: 10) en los nodos terminales del árbol."""
        idx = 0

        def walk(n: Node):
            nonlocal idx
            if not n.children:
                if n.symbol not in {"ε", "epsilon", "lambda"} and idx < len(target_tokens):
                    n.symbol = target_tokens[idx]
                    idx += 1
                return
            for c in n.children:
                walk(c)

        walk(root)

    def build_ast(self, derivation_root: Node) -> Node:
        """AST genérico: elimina no-terminales y pliega binarios."""
        punct = {"(", ")", "[", "]", "{", "}", ",", ";"}
        bin_ops = {"+", "-", "*", "/"}

        def to_ast(n: Node) -> Optional[Node]:
            if n.symbol in {"ε", "epsilon", "lambda", "''"}:
                return None
            if not n.children:
                return None if n.symbol in punct else Node(n.symbol)

            kids = []
            for c in n.children:
                k = to_ast(c)
                if k is not None:
                    kids.append(k)

            if self.g.is_nonterminal(n.symbol):
                if len(kids) == 1:
                    return kids[0]
                if len(kids) == 3 and not kids[1].children and kids[1].symbol in bin_ops:
                    return Node(kids[1].symbol, [kids[0], kids[2]])
                return Node(n.symbol, kids)

            return Node(n.symbol, kids)

        out = to_ast(derivation_root)
        return out if out is not None else Node("AST")
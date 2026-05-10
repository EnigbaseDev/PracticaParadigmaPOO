from __future__ import annotations
from typing import Dict, Tuple

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QRadioButton,
    QLabel, QGraphicsView, QGraphicsScene, QButtonGroup,
    QStackedWidget, QMessageBox, QGraphicsTextItem
)
from PyQt6.QtGui import QPen, QBrush, QColor, QFont, QPainter

from cfg_core import DerivationEngine, Grammar, TreeBuilder, Node


class GraphicsTree(QGraphicsView):
    """Renderiza el árbol utilizando el framework de gráficos de PyQt6."""

    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Colores de la app
        self.setBackgroundBrush(QBrush(QColor("#f0f0f0")))

    def clear(self):
        self.scene.clear()

    def render_tree(self, root: Node) -> None:
        self.clear()
        if not root:
            return

        # 1. Unificamos ancho y alto para garantizar un círculo perfecto
        node_size = 40
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

        def to_xy(x_unit: float, depth: int) -> Tuple[float, float]:
            x = margin + x_unit * (node_size + x_gap)
            y = margin + depth * y_gap
            return x, y

        pen = QPen(QColor("#333333"))
        brush = QBrush(QColor("#ffffff"))  # Relleno blanco sólido
        font = QFont("Arial", 11)

        def draw_edges(n: Node) -> None:
            xu, d = pos[id(n)]
            x1, y1 = to_xy(xu, d)
            for c in n.children:
                xu2, d2 = pos[id(c)]
                x2, y2 = to_xy(xu2, d2)
                # La línea va al centro del círculo
                self.scene.addLine(x1 + node_size / 2, y1 + node_size, x2 + node_size / 2, y2, pen)
                draw_edges(c)

        def draw_nodes(n: Node) -> None:
            xu, d = pos[id(n)]
            x, y = to_xy(xu, d)

            # 2. Dibujamos el círculo usando node_size en ambos ejes
            self.scene.addEllipse(x, y, node_size, node_size, pen, brush)

            label = n.symbol
            if len(label) > 6:
                label = label[:6] + "…"

            text_item = self.scene.addText(label, font)
            assert isinstance(text_item, QGraphicsTextItem)
            text_item.setDefaultTextColor(QColor("#111111"))
            text_rect = text_item.boundingRect()

            # Centrar el texto en el nuevo diámetro
            tx = x + (node_size - text_rect.width()) / 2
            ty = y + (node_size - text_rect.height()) / 2
            text_item.setPos(tx, ty)

            for c in n.children:
                draw_nodes(c)

        # 3. Dibujamos las líneas primero, y los círculos blancos encima
        draw_edges(root)
        draw_nodes(root)


class AppWindow(QMainWindow):
    """Interfaz principal migrada a PyQt6."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CFG: Derivacion, Arbol de Derivacion y AST (PyQt6)")
        self.resize(1200, 780)

        # Colores principales (Limpios para que el sistema dibuje el botón y selectores nativos)
        self.setStyleSheet("""
                    QMainWindow { 
                        background-color: #f0f0f0; 
                    }
                    QLabel, QRadioButton { 
                        color: #000000; 
                    }
                    QTextEdit, QLineEdit { 
                        background-color: #ffffff; 
                        color: #000000; 
                        border: 1px solid #cccccc; 
                        border-radius: 2px; 
                    }
                    /* Le damos al botón explícitamente su diseño clásico rectangular */
                    QPushButton {
                        background-color: #e1e1e1;
                        color: #000000;
                        border: 1px solid #adadad;
                        border-radius: 3px;
                        padding: 4px 15px;
                    }
                    QPushButton:hover {
                        background-color: #e5f1fb;
                        border: 1px solid #0078d7;
                    }
                    QPushButton:pressed {
                        background-color: #cce4f7;
                        border: 1px solid #005499;
                    }
                """)

        self._build_ui()
        self._load_example()

    def _build_ui(self):
        # Widget y layout central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ---- Controles Superiores ----
        controls_layout = QHBoxLayout()

        # Columna 1: Gramática
        col_gramatica = QVBoxLayout()
        col_gramatica.addWidget(QLabel("Gramatica (A -> B C | d)"))
        self.grammar_txt = QTextEdit()
        self.grammar_txt.setMaximumHeight(120)
        col_gramatica.addWidget(self.grammar_txt)
        controls_layout.addLayout(col_gramatica, 2)

        # Columna 2: Expresión
        col_expr = QVBoxLayout()
        col_expr.addWidget(QLabel("Expresion objetivo"))
        self.expr_entry = QLineEdit()
        font = QFont("Arial", 11)
        self.expr_entry.setFont(font)
        col_expr.addWidget(self.expr_entry)
        col_expr.addStretch()
        controls_layout.addLayout(col_expr, 2)

        # Columna 3: Derivación (Izquierda / Derecha)
        col_modo = QVBoxLayout()
        col_modo.addWidget(QLabel("Derivacion"))
        self.btn_left = QRadioButton("Izquierda")
        self.btn_right = QRadioButton("Derecha")
        self.btn_left.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.btn_left)
        self.mode_group.addButton(self.btn_right)

        col_modo.addWidget(self.btn_left)
        col_modo.addWidget(self.btn_right)
        col_modo.addStretch()
        controls_layout.addLayout(col_modo, 1)

        main_layout.addLayout(controls_layout)

        # ---- Selectores de Vista ----
        views_layout = QHBoxLayout()
        self.rb_derivation = QRadioButton("Derivacion")
        self.rb_tree = QRadioButton("Arbol de Derivacion")
        self.rb_ast = QRadioButton("AST")
        self.rb_derivation.setChecked(True)

        self.view_group = QButtonGroup(self)
        self.view_group.addButton(self.rb_derivation, 0)
        self.view_group.addButton(self.rb_tree, 1)
        self.view_group.addButton(self.rb_ast, 2)
        self.view_group.buttonClicked.connect(self._switch_view)

        views_layout.addWidget(self.rb_derivation)
        views_layout.addWidget(self.rb_tree)
        views_layout.addWidget(self.rb_ast)
        views_layout.addStretch()
        main_layout.addLayout(views_layout)

        # ---- Salidas (Stack) ----
        self.stack = QStackedWidget()

        self.derivation_out = QTextEdit()
        self.derivation_out.setReadOnly(True)
        self.derivation_out.setFont(font)

        self.tree_canvas = GraphicsTree()
        self.ast_canvas = GraphicsTree()

        self.stack.addWidget(self.derivation_out)  # Índice 0
        self.stack.addWidget(self.tree_canvas)  # Índice 1
        self.stack.addWidget(self.ast_canvas)  # Índice 2

        main_layout.addWidget(self.stack, 1)

        # ---- Botón de Generar y Estado (MOVIDO AL FINAL) ----
        btn_layout = QHBoxLayout()
        self.status = QLabel("Listo")
        btn_layout.addWidget(self.status)
        btn_layout.addStretch()

        self.btn_generate = QPushButton("Generar")
        self.btn_generate.clicked.connect(self._generate)
        # Tamaño mínimo para asegurar las proporciones de un botón clásico de Windows
        self.btn_generate.setMinimumWidth(100)
        self.btn_generate.setMinimumHeight(28)
        btn_layout.addWidget(self.btn_generate)

        main_layout.addLayout(btn_layout)

    def _switch_view(self, button):
        """Cambia el widget visible según el RadioButton seleccionado."""
        index = self.view_group.id(button)
        self.stack.setCurrentIndex(index)

    def _load_example(self):
        ex = "E -> E + T | E - T | T\nT -> T * F | T / F | F\nF -> ( E ) | id | num"
        self.grammar_txt.setPlainText(ex)
        self.expr_entry.setText("id - id / id")

    def _generate(self):
        try:
            grammar_text = self.grammar_txt.toPlainText().strip()
            expr_text = self.expr_entry.text().strip()

            if not grammar_text:
                raise ValueError("Ingresa una gramatica")
            if not expr_text:
                raise ValueError("Ingresa la expresion objetivo")

            g = Grammar.from_text(grammar_text)
            target = g.tokenize_target(expr_text)
            left = self.btn_left.isChecked()

            engine = DerivationEngine(g)
            result = engine.derive(target=target, left=left)

            builder = TreeBuilder(g)
            tree = builder.build_derivation_tree(result)
            ast = builder.build_ast(tree)

            self.derivation_out.clear()
            self.derivation_out.append(f"Expresión objetivo: {' '.join(target)}\n")

            # Título y Símbolo inicial en renglones separados
            self.derivation_out.append("Derivación:")
            self.derivation_out.append(g.start_symbol)

            # Formateo con enumeración, flechas y paréntesis genéricos
            for step in result.steps:
                form_str = " ".join(step.form)
                rule_str = f"{step.nonterminal} -> {' '.join(step.production)}"
                self.derivation_out.append(f" => {form_str}    (Regla aplicada: {rule_str})")

            self.tree_canvas.render_tree(tree)
            self.ast_canvas.render_tree(ast)

            self.status.setText("Generado correctamente")
        except Exception as e:
            self.status.setText("Error en la generacion")
            QMessageBox.critical(self, "Error", f"Ocurrió un error:\n{str(e)}")
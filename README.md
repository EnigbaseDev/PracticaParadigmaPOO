# PracticaParadigmaPOO

Practica II - ST0244 Programming Languages and Computing Paradigms.

Aplicacion con interfaz grafica para:
1. Generar derivacion por la izquierda o por la derecha.
2. Construir arbol de derivacion.
3. Construir AST (arbol de sintaxis abstracta) simplificado.

## Lenguaje e IDE

- Lenguaje: Python
- Version compilador/interprete: Python 3.x
- IDE usado: Visual Studio Code

## Integrantes

- CARLOS MARIO MONSALVE TANGARIFE
- CRISTIAN ALEJANDRO ADRADA ORDOÑEZ

## Ejecucion

1. Abrir una terminal en la carpeta del proyecto.
2. Ejecutar:

```bash
python main.py
```

## Estructura (organizacion del codigo)

- main.py: punto de entrada (solo lanza la app)
- cfg_core.py: lógica de gramática/derivación/árbol/AST (sin GUI)
- ui_app.py: interfaz gráfica Tkinter (usa cfg_core.py)

## Uso

1. Escribir la gramatica en formato tipo BNF, una regla por linea:

```text
E -> E + T | T
T -> T * F | F
F -> ( E ) | id
```

2. Escribir la expresion objetivo (no es obligatorio separar tokens por espacio). Ejemplo:

```text
id + id * id
```

Tambien puedes escribir variables y numeros (ej. `X + 5 * Y`).
Si tu gramatica usa el terminal `id` (como en el ejemplo), el programa tratara
cualquier identificador o numero como `id` al momento de derivar.

3. Elegir tipo de derivacion (izquierda o derecha).
4. Presionar "Generar".
5. Revisar las pestanas:
- Derivacion
- Arbol de Derivacion
- AST

## Notas

- El simbolo inicial de la gramatica es el no terminal de la primera regla.
- Se admite epsilon como: ε, epsilon, lambda o alternativa vacia.
- Recomendado: Python 3.9+.


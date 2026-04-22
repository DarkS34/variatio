Extraes ejercicios de programación de texto en bruto y juzgas su dificultad. Devuelves un JSON array con un objeto por ejercicio.
{section_block}
# ESQUEMA
[
  {{
    "statement":   "string. Enunciado literal, sin solución.",
    "starter_code":"string o null. Esqueleto para completar; null si no hay.",
    "solutions":   ["string", ...],
    "difficulty":  1 | 2 | 3 | 4
  }}
]

# CÓMO SEPARAR
Un ejercicio empieza con "1.", "2.", "Ejercicio 3:", "Exercise 4:". Si un mismo enunciado tiene varias soluciones (p. ej. "sin slicing" y "con slicing"), TODAS van en `solutions` del MISMO objeto.

# CAMPOS
- statement: copia literal, sin reescribir, sin traducir.
- starter_code: SOLO si hay esqueleto que el alumno debe completar. Si ves código completo, va a `solutions`.
- solutions: [] si no hay ninguna. Cada entrada = código Python completo.
- difficulty: aplica la rúbrica. Juzga el ENUNCIADO, no la solución. Ante duda, nivel MENOR.

# RÚBRICA
- 1 FÁCIL: un concepto (E/S, asignación, operador). Sin bucles, o if simple. Ej: "Lee un entero y muestra su doble."
- 2 MODERADO: 2-3 conceptos, un bucle no anidado o recursión lineal. Ej: "Cuenta las vocales de una cadena."
- 3 DIFÍCIL: bucles anidados, recursión no trivial, filtrar + transformar + agregar. Ej: "Cuenta grupos consecutivos iguales en una lista."
- 4 AVANZADO: varias estructuras combinadas, DP / memoization / backtracking, recorridos no lineales de matrices. Ej: "Fila n del triángulo de Pascal."

Pista: sección "básico / introductorio" → 1-2; "avanzado / desafío" → 3-4. La rúbrica MANDA.

# EJEMPLO
ENTRADA:
1. Lee un entero y muestra su cuadrado.

2. Función recursiva del factorial de n.
SOLUCION PROPUESTA:
def factorial(n):
    return 1 if n <= 1 else n * factorial(n-1)

SALIDA:
[
  {{
    "statement": "Lee un entero y muestra su cuadrado.",
    "starter_code": null,
    "solutions": [],
    "difficulty": 1
  }},
  {{
    "statement": "Función recursiva del factorial de n.",
    "starter_code": null,
    "solutions": ["def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)"],
    "difficulty": 2
  }}
]

# REGLAS DE SALIDA
- Responde SOLO con el JSON array. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios.
- Dentro de strings: \n para saltos de línea, \" para comillas internas.
- Si no hay ejercicios, devuelve [].

<<<CONTENT>>>
{exercises_content}
<<<END>>>

JSON:

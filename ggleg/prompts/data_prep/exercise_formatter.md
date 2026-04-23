Extraes ejercicios de programación de texto en bruto y juzgas su dificultad. Devuelves un JSON array con un objeto por ejercicio.

# ESQUEMA
[
  {{
    "statement":  "string. Enunciado literal, incluyendo cualquier esqueleto o código de arranque embebido.",
    "solutions":  ["string", ...],
    "difficulty": 1 | 2 | 3 | 4
  }}
]

# CÓMO SEPARAR
Un ejercicio NUEVO **solo** empieza cuando ves un marcador explícito de enumeración a inicio de línea: "1.", "2)", "Ejercicio 3:", "Exercise 4.", "Problema 5 -", "Apartado 6:". Sin ese marcador, NO hay ejercicio nuevo.

**TODO lo que haya entre dos marcadores pertenece al MISMO ejercicio**, incluyendo:
- Sub-preguntas ("¿Qué se obtiene?", "¿Por qué?", "¿Qué hace X?").
- Instrucciones encadenadas ("Teclea ahora:", "Ahora prueba con:", "Modifica el código para...", "A continuación...", "Repite con...").
- Apartados a), b), c) / i), ii), iii) / primera parte, segunda parte.
- Bloques de código embebidos, salidas esperadas, pistas, tablas de ejemplos.
- Texto narrativo, párrafos explicativos, definiciones intercaladas.

Fusiona TODO ese bloque en un único `statement` preservando el orden y los saltos de línea (`\n`). Si un mismo enunciado tiene varias soluciones (p. ej. "sin slicing" y "con slicing"), TODAS van en `solutions` del MISMO objeto.

NO crees ejercicios nuevos a partir de:
- Preguntas sueltas que siguen a un código ("¿Qué imprime?", "¿Qué sucede si...?").
- Imperativos de continuación ("Teclea", "Escribe", "Prueba", "Ejecuta", "Observa") sin número delante.
- Líneas en blanco o cambios de párrafo.

# CAMPOS
- statement: copia literal, sin reescribir, sin traducir. **OBLIGATORIO: elimina la enumeración inicial** ("1.", "2)", "Ejercicio 3:", "Exercise 4.", "Problema 5 -", etc.) junto con sus espacios. El statement debe empezar directamente con la primera letra del enunciado real. Si el ejercicio incluye un esqueleto/código de arranque para completar, déjalo dentro del statement tal cual aparece.
  - MAL: "1. Implementa una función..." / "Ejercicio 2: Cuenta..."
  - BIEN: "Implementa una función..." / "Cuenta..."
- solutions: [] si no hay ninguna. Cada entrada = código Python completo. Si ves código completo en el texto, va aquí; si es un esqueleto incompleto que el alumno debe completar, déjalo en `statement`.
- difficulty: aplica la rúbrica. Juzga el ENUNCIADO, no la solución. Ante duda, nivel MENOR.

# RÚBRICA
- 1 FÁCIL: un concepto (E/S, asignación, operador). Sin bucles, o if simple. Ej: "Lee un entero y muestra su doble."
- 2 MODERADO: 2-3 conceptos, un bucle no anidado o recursión lineal. Ej: "Cuenta las vocales de una cadena."
- 3 DIFÍCIL: bucles anidados, recursión no trivial, filtrar + transformar + agregar. Ej: "Cuenta grupos consecutivos iguales en una lista."
- 4 AVANZADO: varias estructuras combinadas, DP / memoization / backtracking, recorridos no lineales de matrices. Ej: "Fila n del triángulo de Pascal."

# EJEMPLO 1 (ejercicios independientes con solución)
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
    "solutions": [],
    "difficulty": 1
  }},
  {{
    "statement": "Función recursiva del factorial de n.",
    "solutions": ["def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)"],
    "difficulty": 2
  }}
]

# EJEMPLO 2 (un solo ejercicio con sub-preguntas y continuaciones — NO separar)
ENTRADA:
3. En Python es posible hacer operaciones con variables de tipo str. Vamos a probarlo tecleando:

fruta = "ciruela"
tipo = "claudia"
print(fruta + tipo)

¿Qué se obtiene? ¿Qué es lo que hace la operación + con las cadenas de texto?

Teclea ahora:

print fruta * 3

¿Qué se obtiene? ¿Qué hace la operación * con los valores tipo texto?

SALIDA:
[
  {{
    "statement": "En Python es posible hacer operaciones con variables de tipo str. Vamos a probarlo tecleando:\n\nfruta = \"ciruela\"\ntipo = \"claudia\"\nprint(fruta + tipo)\n\n¿Qué se obtiene? ¿Qué es lo que hace la operación + con las cadenas de texto?\n\nTeclea ahora:\n\nprint fruta * 3\n\n¿Qué se obtiene? ¿Qué hace la operación * con los valores tipo texto?",
    "solutions": [],
    "difficulty": 1
  }}
]

# REGLAS DE SALIDA
- Responde SOLO con el JSON array. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios.
- Dentro de strings: \n para saltos de línea, \" para comillas internas.
- Si no hay ejercicios, devuelve [].
- Revisa que NINGÚN statement empiece con dígito, "Ejercicio N", "Exercise N", "Problema N", "Problem N" ni marcadores similares. Si los ves, elimínalos antes de emitir el JSON.

<<<CONTENT>>>
{exercises_content}
<<<END>>>

JSON:

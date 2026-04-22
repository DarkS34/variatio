def get_input_validation_prompt(user_input: str):
    return f"""Eres un validador de entrada para un sistema de tutoría pedagógica.

Tu tarea es validar si la entrada del usuario es apropiada para una sesión de aprendizaje.

CRITERIOS DE VALIDACIÓN:
1. La entrada NO debe estar vacía o ser solo espacios.
2. La entrada debe tener intención pedagógica (pregunta, explicación, código, ejercicio, etc.).
3. La entrada debe estar en español o ser código universalmente entendible.
4. La entrada NO debe ser abusive, grosera o inapropiada.

ENTRADA DEL USUARIO:
```
"{user_input}"
```

Proporciona tu respuesta ÚNICAMENTE en formato JSON sin markdown, sin explicaciones adicionales:
{{
    "valid": true|false,
    "reason": "breve explicación si no es válida",
    "cleaned_input": "la entrada limpiada si es válida, sino null"
}}"""


DIFFICULTY_RUBRIC = """\
ESCALA DE DIFICULTAD (1-4) para programación de primer año universitario.
JUZGA POR EL ENUNCIADO (qué se pide), no por la solución propuesta.
REGLA DE DESEMPATE: si dudas entre dos niveles, elige el MENOR.

NIVEL 1 — FÁCIL (un solo concepto aislado)
  Se cumplen TODOS:
    · Aplica 1 concepto básico: E/S, asignación, operador aritmético,
      conversión de tipo, acceso directo a un índice.
    · Sin bucles, o como mucho un if/else simple sin anidar.
    · Sin funciones definidas por el alumno, o una función trivial (1-3 líneas).
    · Cadena de razonamiento: 1-2 pasos.
  Ejemplos:
    · "Lee un entero y muestra su doble."
    · "Convierte grados Celsius a Fahrenheit."
    · "Comprueba con un if si un número es positivo."

NIVEL 2 — MODERADO (combinación simple de conceptos)
  Se cumplen VARIOS:
    · Combina 2-3 conceptos: bucle + condicional, lista + recorrido,
      función + bucle simple.
    · Un solo bucle NO anidado, o una recursión lineal (caso base + 1 llamada).
    · Operaciones básicas sobre listas/tuplas/cadenas: sumar, contar, buscar.
    · Cadena de razonamiento: 3-5 pasos.
  Ejemplos:
    · "Cuenta las vocales de una cadena."
    · "Función recursiva que calcula el factorial."
    · "Suma los elementos pares de una lista."

NIVEL 3 — DIFÍCIL (integración de conceptos)
  Se cumplen VARIOS:
    · Estructuras anidadas: bucle dentro de bucle, condicional dentro de bucle.
    · Recursión no trivial: dividir el problema y combinar resultados,
      o recursión con índice auxiliar.
    · Manipulación compuesta: filtrar + transformar + agregar.
    · Cadena de razonamiento: 5-10 pasos.
  Ejemplos:
    · "Posición del primer impar en una lista, de forma recursiva."
    · "Suma recursiva de los pares entre 0 y n."
    · "Cuenta los grupos consecutivos de valores iguales en un array."

NIVEL 4 — AVANZADO (reto algorítmico o de diseño)
  Basta con que se cumpla UNO:
    · Múltiples estructuras de datos combinadas (p.ej. dict + list + tuple).
    · Múltiples funciones coordinadas, o varias llamadas recursivas por caso.
    · Técnicas algorítmicas: memoization, programación dinámica, backtracking.
    · Recorridos no lineales de matrices (espiral, serpiente, diagonal).
    · Cadena de razonamiento: más de 10 pasos.
  Ejemplos:
    · "Fila n del triángulo de Pascal."
    · "Fibonacci con memoization."
    · "Suma por recorrido en serpiente de una matriz NxN."
"""

# =============================================================================
# PROMPT 1: LIMPIEZA DE CONTENIDO
# =============================================================================

def get_content_cleaner_prompt(raw_content: str) -> str:
    return f"""\
Eres un preprocesador de documentos educativos de programación. Tu única \
tarea es devolver el texto limpio, SIN resolver, SIN reformatear, SIN traducir.

====================================================================
QUÉ DEBES CONSERVAR (intacto, palabra por palabra)
====================================================================
1. Cabeceras que indican secciones de ejercicios. Ejemplos:
     "# Ejercicios resueltos", "# Ejercicios nivel básico",
     "# Ejercicios nivel avanzado", "# Ejercicio de investigación",
     "## Exercises", "## Problem Set 3", etc.
2. Enunciados de ejercicios (en cualquier idioma: es, en, fr).
3. Bloques de código, fragmentos inline de código, y docstrings.
4. Soluciones propuestas, con sus comentarios y casos de prueba.
5. Etiquetas como "SOLUCION PROPUESTA", "Solución:", "Answer:", etc.
   (te indican dónde empieza una solución; no las borres).

====================================================================
QUÉ DEBES ELIMINAR
====================================================================
- Números de página sueltos (líneas con solo un número: "3", "- 12 -").
- Pies de página, copyright, marcas de agua, URLs de la universidad.
- Tablas de contenido e índices.
- Metadatos de autor/fecha/versión que aparezcan fuera de los ejercicios.
- Líneas vacías consecutivas de más de 2 (colapsa a máximo 2).

====================================================================
QUÉ DEBES CORREGIR (artefactos de conversión docx/pdf a markdown)
====================================================================
- Underscores escapados: "cuenta\\_aes" -> "cuenta_aes"
- Docstrings envueltos en cursiva: *\"\"\" ... \"\"\"*  ->  \"\"\" ... \"\"\"
- Asteriscos de cursiva pegados al código: "*return*" -> "return"
- Operadores escapados: "n \\* 2" -> "n * 2", "a \\| b" -> "a | b"

====================================================================
REGLAS ABSOLUTAS
====================================================================
- NO resuelvas ningún ejercicio que no tenga ya solución.
- NO reescribas los enunciados con tus palabras.
- NO añadas explicaciones, introducciones ni cierres.
- NO cambies el idioma del texto.
- Si el contenido ya está limpio, devuélvelo tal cual.

====================================================================
TEXTO A LIMPIAR (entre delimitadores <<<CONTENT>>>)
====================================================================
<<<CONTENT>>>
{raw_content}
<<<END>>>

Responde SOLO con el texto limpio, sin envolverlo en backticks ni añadir \
ningún comentario."""


# =============================================================================
# PROMPT 2: EXTRACCIÓN ESTRUCTURADA + JUICIO DE DIFICULTAD (una sola llamada)
# =============================================================================

def get_exercise_formatter_prompt(exercises_content: str, section_hint: str | None = None) -> str:
    
    section_block = (
        f"\nCONTEXTO DE SECCIÓN (pista, no obliga): "
        f'"{section_hint}"\n' if section_hint else ""
    )

    return f"""\
Eres un extractor estructurado de ejercicios de programación y juez de su \
dificultad. Recibes texto en bruto que contiene UNO O MÁS ejercicios y \
devuelves un JSON array con un objeto por ejercicio.
{section_block}
====================================================================
ESQUEMA DE SALIDA (estricto)
====================================================================
[
  {{
    "statement":   "string. El enunciado literal, sin solución ni código.",
    "starter_code": "string o null. Código de partida que el alumno debe \
completar (cabecera de función vacía, esqueleto con TODO). null si no hay.",
    "solutions":   ["string", ...]  // lista de 0..N soluciones propuestas.
                                     // [] si no hay. Cada solución es código
                                     // Python completo, incluyendo docstring
                                     // y llamadas de prueba si aparecen.
    "difficulty":  1 | 2 | 3 | 4,    // entero según la rúbrica de abajo.
    "difficulty_justification": "string. UNA frase (<25 palabras) indicando \
los conceptos principales y por qué ese nivel."
  }},
  ...
]

====================================================================
CÓMO SEPARAR LOS EJERCICIOS
====================================================================
Cada ejercicio suele empezar con un número ("1.", "2.") o con una etiqueta \
("Ejercicio 3:", "Exercise 4:"). Dentro de un mismo ejercicio pueden \
aparecer VARIAS soluciones (p.ej. "SOLUCION PROPUESTA (sin slicing)" y \
"SOLUCION PROPUESTA (utilizando slicing)"). Todas esas soluciones van en \
el array `solutions` del MISMO ejercicio, no creas ejercicios separados.

====================================================================
CÓMO RELLENAR CADA CAMPO
====================================================================
- statement: copia el enunciado tal cual está escrito. No lo reescribas. \
Puede estar en español, inglés o francés; no traduzcas.
- starter_code: SOLO si el enunciado incluye explícitamente un esqueleto \
que el alumno debe completar. Si lo que ves es una solución completa, eso \
va en `solutions`, no en `starter_code`. Si no hay, devuelve null.
- solutions: lista con cada solución completa. Si no hay ninguna, [].
- difficulty: aplica la rúbrica rigurosamente (ver abajo).
- difficulty_justification: una frase breve, sin listas ni viñetas.

====================================================================
{DIFFICULTY_RUBRIC}
====================================================================
PISTA: si la sección se llama "nivel básico", "básico", "introductorio" -> \
probablemente 1-2. Si se llama "nivel avanzado", "desafío", \
"investigación" -> probablemente 3-4. Pero la rúbrica MANDA: si un ejercicio \
de "nivel avanzado" es en realidad trivial, ponle el nivel real.

====================================================================
EJEMPLO COMPLETO (few-shot)
====================================================================
ENTRADA:
<
1. Lee un entero por teclado y muestra su cuadrado.

2. Implementa una función recursiva que calcule el factorial de n.

SOLUCION PROPUESTA:
def factorial(n):
    \"\"\" int -> long
    OBJ: n!
    PRE: n >= 0
    \"\"\"
    if n in (0, 1): return 1
    else: return n * factorial(n-1)

print(factorial(6))
>>>

SALIDA:
[
  {{
    "statement": "Lee un entero por teclado y muestra su cuadrado.",
    "starter_code": null,
    "solutions": [],
    "difficulty": 1,
    "difficulty_justification": "E/S básica y una multiplicación; un solo \
concepto sin control de flujo."
  }},
  {{
    "statement": "Implementa una función recursiva que calcule el factorial de n.",
    "starter_code": null,
    "solutions": [
      "def factorial(n):\\n    \\\"\\\"\\\" int -> long\\n    OBJ: n!\\n    PRE: n >= 0\\n    \\\"\\\"\\\"\\n    if n in (0, 1): return 1\\n    else: return n * factorial(n-1)\\n\\nprint(factorial(6))"
    ],
    "difficulty": 2,
    "difficulty_justification": "Recursión lineal con caso base claro; \
combina función y condicional, sin anidamientos."
  }}
]

====================================================================
REGLAS DE SALIDA
====================================================================
- Responde SOLO con el JSON array. Nada antes, nada después.
- No envuelvas en ```json ni en backticks.
- No añadas explicaciones ni comentarios.
- Escapa correctamente las comillas y los saltos de línea dentro de strings \
(usa \\n para saltos de línea, \\" para comillas internas).
- Si el contenido está vacío o no contiene ejercicios, responde con [].

====================================================================
CONTENIDO A PROCESAR
====================================================================
<<<CONTENT>>>
{exercises_content}
<<<END>>>

JSON:"""


# =============================================================================
# PROMPT 3: REPARACIÓN DE JSON (segundo intento si el primero falla)
# =============================================================================

def get_json_repair_prompt(broken_output: str, error_msg: str) -> str:
    return f"""\
Tu respuesta anterior no era un JSON válido.

Error del parser: {error_msg}

Respuesta anterior:
<
{broken_output}
>>>

Devuelve EXACTAMENTE el mismo contenido pero como JSON array válido. \
No añadas texto antes ni después. No uses backticks. Escapa comillas \
internas con \\" y saltos de línea con \\n.

JSON:"""
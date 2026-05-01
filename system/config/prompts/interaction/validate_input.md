Decide si el siguiente texto es un enunciado de ejercicio de programación o código de programación (Python u otro lenguaje).

# TEXTO
{text}

# ESQUEMA DE SALIDA
{{
  "is_programming": true,
  "reason": "..."
}}

# REGLAS
- `is_programming` es `true` SOLO si el texto es claramente:
  (a) un enunciado pidiendo escribir/analizar/depurar código, o
  (b) fragmentos de código fuente.
- `is_programming` es `false` para prosa general, listas de la compra, contenido sin relación con programación, o texto sin sentido.
- `reason`: una frase breve en español explicando la decisión (máx. 20 palabras).
- Responde SOLO con el JSON. Sin texto antes ni después, sin backticks, sin comentarios.

JSON:
La salida anterior no pudo parsearse como JSON válido o no cumple el schema requerido.

Tu tarea: produce un JSON array corregido que (1) parsee como JSON válido, (2) cumpla el schema de abajo, y (3) preserve la información original lo más fielmente posible.

# ERROR DEL INTENTO ANTERIOR
{error_msg}

# SCHEMA REQUERIDO (cada elemento del array)
{schema}

# SALIDA ROTA A REPARAR
{broken_output}

# REGLAS
- Devuelve un único JSON array. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Escapa correctamente saltos de línea (`\n`) y comillas internas (`\"`) dentro de strings.
- Respeta los constraints del schema (tipos, campos requeridos, `minLength`, etc.).
- Si la salida rota es irrecuperable, devuelve `[]`.

JSON:
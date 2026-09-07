"""The last chance a reply gets: re-emit what did not parse, as valid JSON."""


def json_repair_prompt(broken_output: str, error_msg: str, shape: str = "array") -> str:
    """Ask the model to rewrite an unparseable reply as a JSON `shape`, losing nothing.

    `shape` is the caller's own expectation ("array", "objeto"), because a silent default is
    what let a component ask for one shape while its parser demanded the other. An
    unrecoverable reply is asked back as `{}` rather than as an apology.
    """
    return f"""\
La salida anterior no pudo parsearse como JSON válido o no cumple el schema requerido.

Tu tarea: produce un {shape} JSON corregido que (1) parsee como JSON válido, y (2) preserve la información original lo más fielmente posible.

# ERROR DEL INTENTO ANTERIOR
{error_msg}

# SALIDA ROTA A REPARAR
{broken_output}

# REGLAS
- Devuelve un único {shape} JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Escapa correctamente saltos de línea (`\\n`) y comillas internas (`\\"`) dentro de strings.
- Los caracteres que no son ASCII (tildes, «ñ», «→») se escriben tal cual, nunca como secuencias `\\uXXXX`.
- Si la salida rota es irrecuperable, devuelve `{{}}`.

JSON:"""

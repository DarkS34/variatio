"""The last chance a reply gets: re-emit what did not parse, as valid JSON."""

_SHAPES = {"object": "objeto", "array": "array"}


def json_repair_prompt(broken_output: str, error_msg: str, shape: str, grammar: bool) -> str:
    """Ask the model to rewrite an unparseable reply as a JSON `shape`, losing nothing.

    `shape` is the caller's own expectation ("object" or "array"), because a silent default
    is what let a component ask for one shape while its parser demanded the other; its word
    is this set's. An unrecoverable reply is asked back as the shape's empty form rather than
    as an apology, except under a `grammar`, whose required keys make the empty form
    impossible to write.
    """
    word = _SHAPES[shape]
    empty = "[]" if shape == "array" else "{}"
    last_rule = "" if grammar else f"\n- Si la salida rota es irrecuperable, devuelve `{empty}`."
    return f"""\
La salida anterior no pudo parsearse como JSON válido o no cumple el schema requerido.

Tu tarea: produce un {word} JSON corregido que (1) parsee como JSON válido, y (2) preserve la información original lo más fielmente posible.

# ERROR DEL INTENTO ANTERIOR
{error_msg}

# SALIDA ROTA A REPARAR
{broken_output}

# REGLAS
- Devuelve un único {word} JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Escapa correctamente saltos de línea (`\\n`) y comillas internas (`\\"`) dentro de strings.
- Los caracteres que no son ASCII (tildes, «ñ», «→») se escriben tal cual, nunca como secuencias `\\uXXXX`.{last_rule}

JSON:"""

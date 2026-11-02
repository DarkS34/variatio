"""The last chance a reply gets: re-emit what did not parse, as valid JSON."""

_SHAPES = {"object": "object", "array": "array"}


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
    last_rule = "" if grammar else f"\n- If the broken output is beyond recovery, return `{empty}`."
    return f"""\
The previous output could not be parsed as valid JSON, or it does not satisfy the required schema.

Your task: produce a corrected JSON {word} that (1) parses as valid JSON, and (2) preserves the original information as faithfully as possible.

# ERROR FROM THE PREVIOUS ATTEMPT
{error_msg}

# BROKEN OUTPUT TO REPAIR
{broken_output}

# RULES
- Return a single JSON {word}. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- Escape line breaks (`\\n`) and inner quotes (`\\"`) properly inside strings.
- Non-ASCII characters (accents, «ñ», «→») are written as themselves, never as `\\uXXXX` escape sequences.{last_rule}

JSON:"""

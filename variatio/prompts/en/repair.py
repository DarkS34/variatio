"""The last chance a reply gets: re-emit what did not parse, as valid JSON."""


def json_repair_prompt(broken_output: str, error_msg: str, shape: str = "array") -> str:
    """Ask the model to rewrite an unparseable reply as a JSON `shape`, losing nothing.

    `shape` is the caller's own expectation («array», «object»), because a silent default is
    what let a component ask for one shape while its parser demanded the other. An
    unrecoverable reply is asked back as `{}` rather than as an apology.
    """
    return f"""\
The previous output could not be parsed as valid JSON, or it does not satisfy the required schema.

Your task: produce a corrected JSON {shape} that (1) parses as valid JSON, and (2) preserves the original information as faithfully as possible.

# ERROR FROM THE PREVIOUS ATTEMPT
{error_msg}

# BROKEN OUTPUT TO REPAIR
{broken_output}

# RULES
- Return a single JSON {shape}. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- Escape line breaks (`\\n`) and inner quotes (`\\"`) properly inside strings.
- Non-ASCII characters (accents, «ñ», «→») are written as themselves, never as `\\uXXXX` escape sequences.
- If the broken output is beyond recovery, return `{{}}`.

JSON:"""

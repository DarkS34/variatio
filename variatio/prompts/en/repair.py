def json_repair_prompt(broken_output: str, error_msg: str, shape: str = "array") -> str:
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
- If the broken output is beyond recovery, return `{{}}`.

JSON:"""

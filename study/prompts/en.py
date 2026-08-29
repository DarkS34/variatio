"""The English half of the two reference-arm prompts.

Same shape and the same deliberate poverty; `es.py` says what they carry and why, and the
measurement record is not repeated here.
"""


def naive_generation_prompt(
    subject: str,
    educational_level: str,
    language_of_instruction: str,
    concepts: list[str],
    keys: list[str],
    fixed: dict[str, object] | None = None,
    instructions: str = "",
) -> str:
    """Compose the sentence a person who had never seen this system would type.

    The one prompt that does NOT take the context's rendered block: it reads the three
    canonical facts by name, and handing it the synthesised narrative instead would change
    a measured baseline and make recorded sessions incomparable.
    """
    subject = subject or "the subject"
    level = educational_level
    language = language_of_instruction

    header = f"You are an expert in {subject}"
    if level:
        header += f", at {level} level"
    header += "."

    lines = [header, f"Write an exercise to practise: {', '.join(concepts)}."]
    if language:
        lines.append(f"Write it in {language}.")
    for name, value in (fixed or {}).items():
        lines.append(f"The field {name} must be: {value}.")
    if instructions.strip():
        lines.append(instructions.strip())
    lines.append(f"Return it as JSON with the keys: {', '.join(keys)}.")
    lines.append(
        "The content of the fields is the exercise itself: no greetings, no introductions, "
        "no encouragement, no comments of your own about the exercise, and no text at all "
        "outside the JSON."
    )
    return "\n".join(lines)


def rag_generation_prompt(
    naive_prompt: str,
    exemplars_block: str,
    rules_block: str,
    schema: str,
) -> str:
    """Wrap the naive prompt with the retrieved exemplars, the writing rules and a schema."""
    exemplars_section = ""
    if exemplars_block.strip():
        exemplars_section = (
            "\n# EXAMPLES FROM THE COURSE'S BANK\n"
            "Real exercises from the course, retrieved by similarity with the commission. "
            "Use them as a reference for form and register:\n"
            f"{exemplars_block}\n"
        )

    rules_section = ""
    if rules_block.strip():
        rules_section = f"\n# THE COURSE'S WRITING RULES\n{rules_block}\n"

    return f"""\
{naive_prompt}
{exemplars_section}{rules_section}
# OUTPUT SCHEMA
{schema}

# OUTPUT RULES
- Return ONE SINGLE JSON object conforming to the schema. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- The top-level keys are exactly those of the schema.

JSON:"""

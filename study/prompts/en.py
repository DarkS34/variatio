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

    opening = f"I need a {subject} exercise"
    if level:
        opening += f" for {level}"
    opening += f", to practise {', '.join(concepts)}."

    lines = [opening]
    if language:
        lines.append(f"In {language}.")
    for name, value in (fixed or {}).items():
        lines.append(f"{name}: {value}.")
    if instructions.strip():
        lines.append(instructions.strip())
    lines.append(
        f"Give it to me as JSON with these keys: {', '.join(keys)}. "
        "Just the exercise: no greetings, no explanations and no text outside the JSON."
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

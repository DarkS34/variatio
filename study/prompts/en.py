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
    theory_block: str,
    exercises_block: str,
    schema: str,
) -> str:
    """Wrap the naive prompt with retrieved pieces of the documents and the bare output schema.

    Same shape as the Spanish one; `es.py` says what each section is and why nothing else
    is carried.
    """
    theory_section = ""
    if theory_block.strip():
        theory_section = (
            "\n# THE COURSE'S NOTES (retrieved pieces)\n"
            "Pieces of the lecture notes, retrieved by similarity with the commission. Lean on "
            "them for the subject matter and the terminology:\n"
            f"{theory_block}\n"
        )

    exercises_section = ""
    if exercises_block.strip():
        exercises_section = (
            "\n# THE COURSE'S EXERCISES (retrieved pieces)\n"
            "Pieces of the exercise sheets, retrieved by similarity with the commission. Use "
            "them as a reference for form and register:\n"
            f"{exercises_block}\n"
        )

    return f"""\
{naive_prompt}
{theory_section}{exercises_section}
# OUTPUT SCHEMA
{schema}

# OUTPUT RULES
- Return ONE SINGLE JSON object conforming to the schema. Nothing before, nothing after.
- No ```json, no backticks, no comments, no explanations.
- The top-level keys are exactly those of the schema.

JSON:"""

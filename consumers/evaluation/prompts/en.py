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
    context_block: str = "",
    scenario: str = "",
) -> str:
    """Compose the sentence a person who had never seen this system would type.

    Same shape as the Spanish one; `es.py` says why the subject's context is pasted in.
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
    if context_block.strip():
        lines.append(f"So you know what the course is about:\n{context_block.strip()}")
    for name, value in (fixed or {}).items():
        lines.append(f"{name}: {value}.")
    if instructions.strip():
        lines.append(instructions.strip())
    if scenario.strip():
        lines.append(f"Set it in this scenario: {scenario.strip()}")
    lines.append(
        f"Give it to me as JSON with these keys: {', '.join(keys)}. "
        "Just the exercise: no greetings, no explanations and no text outside the JSON."
    )
    return "\n".join(lines)


# What the scenario draw answers when the evaluator's own instructions already fix the
# setting: one word, folded and stripped of punctuation before it is compared.
SCENARIO_NONE = "NONE"


def scenario_prompt(
    subject: str, concepts: list[str], context_block: str = "", instructions: str = ""
) -> str:
    """Ask for ONE sentence placing an exercise on `concepts` in a concrete, neutral setting.

    Drawn once per session and handed to both arms in the same words, so the comparison
    is between architectures and never between the settings each arm would have invented.
    Plain text, one line, no task and no concept named: the setting is a wrapper and the
    exercise itself is each arm's own. When `instructions` already fix a setting the
    answer is `SCENARIO_NONE`: the evaluator's words reach both arms as they are, and a
    second sentence saying the same thing would only compete with them.
    """
    subject = subject or "the subject"
    context_section = f"\nWhat the subject is about:\n{context_block.strip()}\n" if context_block.strip() else ""
    instructions_section = (
        f"\nInstructions from whoever is asking for the exercise:\n{instructions.strip()}\n\n"
        f"If those instructions already fix a theme, a context or a setting for the exercise, "
        f"answer with the single word {SCENARIO_NONE}. If they say nothing of the kind, propose the setting.\n"
        if instructions.strip()
        else ""
    )
    return f"""\
Propose ONE concrete, realistic scenario in which to set an exercise of {subject} practising {', '.join(concepts)}.
{context_section}{instructions_section}
A single sentence of at most 25 words describing a recognisable organisation, system or everyday situation. Do not set the task, do not name the concepts, do not solve anything and do not explain the choice.

Answer with the sentence alone, no quotes and no preamble."""


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

# The two prompts of the reference arms of the Evaluation mode. Not the "best" ones: they
# are deliberately poor, because they measure what the system's additions contribute.
#
# What they DO carry, and why:
#   · the concept names — an ordinary user writes the topic;
#   · the teaching context — whoever asks for the exercise, student or teacher, knows
#     which subject and at what level they want it;
#   · the list of output keys — without it the arm returns prose and the comparison
#     would measure format instead of content, an artifact that invalidates the experiment;
#   · one register line — the commercial model opened the statement greeting and
#     commenting on the exercise. That is conversational format, not didactics: leaving it
#     would measure politeness instead of item quality, exactly the same artifact that
#     justifies the previous line. It says what NOT to put, not how to write the exercise.
# What they can NEVER carry: concept descriptions, prerequisites, posteriors, curriculum,
# or any didactic section of `generate_content_prompt`. All of that only exists thanks to
# the graph, which is precisely what is being measured.


# The one prompt that does NOT take the rendered block. It composes a sentence -- "Eres
# experto en X, a nivel de Y. Redáctalo en Z." -- because that is what a person who has
# never seen this system would type, and a paragraph of synthesised prose is not that. So
# the three canonical facts stay addressable by name in `ContentContext`, and this arm
# reads them and nothing else. Handing it the narrative would change a measured baseline
# and make old evaluation sessions incomparable.
def naive_generation_prompt(
    subject: str,
    educational_level: str,
    language_of_instruction: str,
    concepts: list[str],
    keys: list[str],
    fixed: dict[str, object] | None = None,
    instructions: str = "",
) -> str:
    subject = subject or "la asignatura"
    level = educational_level
    language = language_of_instruction

    header = f"Eres experto en {subject}"
    if level:
        header += f", a nivel de {level}"
    header += "."

    lines = [header, f"Escribe un ejercicio para practicar: {', '.join(concepts)}."]
    if language:
        lines.append(f"Redáctalo en {language}.")
    for name, value in (fixed or {}).items():
        lines.append(f"El campo {name} debe ser: {value}.")
    if instructions.strip():
        lines.append(instructions.strip())
    lines.append(f"Devuélvelo en JSON con las claves: {', '.join(keys)}.")
    lines.append(
        "El contenido de los campos es el ejercicio en sí: sin saludos, sin presentaciones, "
        "sin ánimos ni comentarios tuyos sobre el ejercicio, y sin nada de texto fuera del JSON."
    )
    return "\n".join(lines)


def rag_generation_prompt(
    naive_prompt: str,
    exemplars_block: str,
    rules_block: str,
    schema: str,
) -> str:
    exemplars_section = ""
    if exemplars_block.strip():
        exemplars_section = (
            "\n# EJEMPLOS DEL BANCO DE LA ASIGNATURA\n"
            "Ejercicios reales de la asignatura, recuperados por similitud con el encargo. "
            "Úsalos como referencia de forma y registro:\n"
            f"{exemplars_block}\n"
        )

    rules_section = ""
    if rules_block.strip():
        rules_section = f"\n# REGLAS DE REDACCIÓN DE LA ASIGNATURA\n{rules_block}\n"

    return f"""\
{naive_prompt}
{exemplars_section}{rules_section}
# SCHEMA DE SALIDA
{schema}

# REGLAS DE SALIDA
- Devuelve UN ÚNICO objeto JSON conforme al schema. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Las claves de nivel superior son exactamente las del schema.

JSON:"""

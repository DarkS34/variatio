"""The Spanish baseline prompts of the reference arms. Deliberately poor, and measured.

They carry exactly four things and no more: the concept names, the teaching context, the
list of output keys (without it the arm returns prose and the comparison measures format
instead of content) and one register line saying what NOT to put, because a commercial
model that greets and comments would have the comparison measure politeness.

What they may NEVER carry: concept descriptions, prerequisites, posteriors, curriculum, or
any didactic section of `generate_content_prompt`. All of that exists thanks to the graph,
which is precisely what is being measured.
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
    """Wrap the naive prompt with the retrieved exemplars, the writing rules and a schema."""
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

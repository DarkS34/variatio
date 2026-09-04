"""The Spanish baseline prompts of the reference arms. Deliberately poor, and measured.

They carry exactly four things and no more: the concept names, the teaching context, the
list of output keys (without it the arm returns prose and the comparison measures format
instead of content) and one register line saying what NOT to put, because a commercial
model that greets and comments would have the comparison measure politeness.

What they may NEVER carry: concept descriptions, prerequisites, posteriors, curriculum, or
any didactic section of `generate_content_prompt`. All of that exists thanks to the graph,
which is precisely what is being measured. Nor the bank, nor the profile's prose — a
field's description, the difficulty criterion, `guidance`, the writing rules: the RAG arm
gets pieces of the raw documents, read with a plain extractor, and the bare output schema,
and nothing this system wrote.
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

    It reads as somebody thinking out loud because that is what it is measuring. The pinned
    fields arrive already spoken (`naive._spoken_fixed`), so no field identifier is named,
    and the only technical thing left is the list of keys — which stays for the reason the
    module docstring gives, and is asked for in prose rather than enforced by a grammar.
    """
    subject = subject or "la asignatura"
    level = educational_level
    language = language_of_instruction

    opening = f"Necesito un ejercicio de {subject}"
    if level:
        opening += f" para {level}"
    opening += f", para practicar {', '.join(concepts)}."

    lines = [opening]
    if language:
        lines.append(f"En {language}.")
    for name, value in (fixed or {}).items():
        lines.append(f"{name}: {value}.")
    if instructions.strip():
        lines.append(instructions.strip())
    lines.append(
        f"Dámelo en JSON con estas claves: {', '.join(keys)}. "
        "Solo el ejercicio: sin saludos, sin explicaciones y sin nada de texto fuera del JSON."
    )
    return "\n".join(lines)


def rag_generation_prompt(
    naive_prompt: str,
    theory_block: str,
    exercises_block: str,
    schema: str,
) -> str:
    """Wrap the naive prompt with retrieved pieces of the documents and the bare output schema.

    Two sections, one per raw slot, each holding the pieces `study.raw_text` cut and the
    index ranked — verbatim, under the document and position they came from, with no
    cleaning and no formatting. The schema is the item type's shape and nothing more: no
    field descriptions, no difficulty criterion, no writing rules, since those are the
    profile builder's prose and this arm measures what the documents alone are worth.
    """
    theory_section = ""
    if theory_block.strip():
        theory_section = (
            "\n# APUNTES DE LA ASIGNATURA (fragmentos recuperados)\n"
            "Fragmentos de los apuntes, recuperados por similitud con el encargo. Apóyate en "
            "ellos para la materia y la terminología:\n"
            f"{theory_block}\n"
        )

    exercises_section = ""
    if exercises_block.strip():
        exercises_section = (
            "\n# EJERCICIOS DE LA ASIGNATURA (fragmentos recuperados)\n"
            "Fragmentos de las hojas de ejercicios, recuperados por similitud con el encargo. "
            "Úsalos como referencia de forma y registro:\n"
            f"{exercises_block}\n"
        )

    return f"""\
{naive_prompt}
{theory_section}{exercises_section}
# SCHEMA DE SALIDA
{schema}

# REGLAS DE SALIDA
- Devuelve UN ÚNICO objeto JSON conforme al schema. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Las claves de nivel superior son exactamente las del schema.

JSON:"""

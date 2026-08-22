# The context synthesis, shared by BOTH builders: the graph's calls it at the end of its
# curation with the syllabus blocks, and the profile's at the end of its own with the
# modalities. Each contributes what its artifact knows about the subject and neither sees
# what the other knows, so the call is always a MERGE: what was already written goes in
# and a text that incorporates it comes out.
#
# That is why what is legislated hardest here is preservation. The natural failure of a
# model given a text and new material is to rewrite the text; repeated on every rebuild,
# that paraphrases what a person wrote until it stops being theirs. What really stops the
# drift is the draft/curated pair — the curated one wins on read and this call never
# touches it —, but a text that respects what was already said is what makes the draft
# worth curating instead of rewriting whole.


def synthesize_content_context_prompt(
    current_block: str,
    evidence_block: str,
    source_label: str,
    max_chars: int,
) -> str:
    current_section = (
        "\n# CONTEXTO QUE YA EXISTE — PUNTO DE PARTIDA, NO BORRADOR A REESCRIBIR\n"
        f"{current_block}\n"
        if current_block.strip()
        else "\n# CONTEXTO QUE YA EXISTE\n(Ninguno todavía: lo estás escribiendo por primera vez.)\n"
    )
    return f"""\
Escribe, en prosa, QUÉ ASIGNATURA ES ESTA. El texto que produzcas se interpola en todos los prompts de un sistema que genera material de aprendizaje: es lo que fija la materia, el nivel de exigencia, el idioma y las convenciones propias de la asignatura para todo lo que ese sistema redacte después.

No describes un temario ni un programa docente. Describes el TERRENO: de qué va esto, a quién se dirige, en qué idioma se enseña y qué convenciones lo hacen reconocible.
{current_section}
# LO QUE APORTA {source_label}
{evidence_block}

# CÓMO FUSIONAR
- LO QUE YA ESTABA SE CONSERVA. Cada afirmación del contexto existente sigue en el texto final, y si puede seguir con sus mismas palabras, sigue con sus mismas palabras. Puede haberla escrito una persona a mano; parafrasearla sin necesidad es perderla poco a poco.
- SOLO AÑADES LO QUE EL MATERIAL NUEVO APORTA DE VERDAD. Si no aporta nada que no estuviera ya dicho, devuelve el contexto que ya había, tal cual. Es una respuesta correcta y frecuente.
- SI SE CONTRADICEN, MANDA LO QUE YA ESTABA. El material nuevo es una vista parcial de la asignatura; el contexto existente puede venir de una persona que la conoce entera.
- NO INVENTES. Ni universidad, ni curso académico, ni titulación, ni número de horas, ni bibliografía, ni nada que no esté en uno de los dos bloques de arriba. Ante la duda, omítelo.

# CÓMO DEBE SER EL TEXTO
- PROSA CONTINUA, en el idioma de instrucción de la asignatura. Una o dos frases seguidas; nada de listas, viñetas, encabezados ni pares clave-valor.
- COMO MUCHO {max_chars} CARACTERES. Es un techo duro y existe porque este texto se paga en cada llamada del sistema.
- NADA DE TEMARIO ENUMERADO. Puedes decir en una frase por dónde va la asignatura («cubre desde los tipos básicos hasta la recursividad»); no puedes listar los conceptos ni copiar los nombres de los bloques uno a uno. Para eso ya está el grafo, y quien lea esto lo tiene delante.
- SIN METACOMENTARIO. No hables del sistema, ni de este encargo, ni de lo que has hecho para escribirlo. El texto empieza describiendo la asignatura.
- SIN DESTINATARIO. No te dirijas a nadie: ni «tú», ni «el alumno debe», ni «ten en cuenta que». Es una descripción, no una instrucción.

# LOS TRES DATOS APARTE
Además de la prosa, extrae tres datos sueltos, porque otra parte del sistema los necesita por separado y no puede leer el párrafo:
- `subject`: el nombre de la asignatura o materia.
- `educational_level`: la etapa o el curso («primer curso de grado», «segundo de bachillerato»).
- `language_of_instruction`: el idioma en que se enseña.
Cada uno, cadena vacía si no se deduce con seguridad de los bloques de arriba. Deben ser COHERENTES con la prosa: lo que digan tiene que estar también dicho en ella.

# REGLAS DE SALIDA
- Un único objeto JSON con exactamente las claves `narrative`, `subject`, `educational_level` y `language_of_instruction`. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- `narrative` en UNA SOLA LÍNEA: escapa los saltos (`\\n`) y las comillas internas (`\\"`).

JSON:"""

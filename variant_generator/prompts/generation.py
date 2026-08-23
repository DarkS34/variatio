# A deliberate second copy of the catalog's labels: `admissibility` imports `prompts`, so
# importing it back here would close a cycle. `test_the_prompt_labels_match_the_catalog`
# is what keeps the two from drifting apart.
_SLOT_LABELS = {
    "ambito": "Ámbito",
    "elementos": "Elementos del enunciado",
    "extension": "Extensión",
    "datos": "Datos concretos",
}


def generate_content_prompt(
    context_block: str,
    item_type_block: str,
    target_concepts_block: str,
    prerequisites_block: str,
    excluded_concepts_block: str,
    curriculum_block: str,
    rules_block: str,
    few_shot_block: str,
    already_generated: list[str],
    instance_template: str,
    fields_block: str,
    fixed_values_block: str,
    instructions: str = "",
    requests=None,
) -> str:
    # Guarded, unlike before: a workspace has no context until one of the two builders has
    # synthesised one, and that is the state a fresh instance starts in. Unguarded, the
    # heading printed with nothing under it and the sentence below claimed a context that
    # was not there.
    context_section = (
        "\n# CONTEXTO DOCENTE\n"
        f"{context_block}\n"
        "Este contexto fija la materia, el nivel y el idioma de instrucción: ajusta a él el "
        "registro, la terminología y la extensión del ejercicio. Es información para ti, no "
        "texto que deba aparecer en el enunciado.\n"
        if context_block.strip()
        else ""
    )

    few_shot_section = (
        few_shot_block.strip()
        or "(Ningún ejemplo disponible: redacta el ejercicio de cero respetando las reglas anteriores.)"
    )

    already_block = ""
    if already_generated:
        existing_lines = "\n".join(f"- {s.strip()[:240]}" for s in already_generated)
        already_block = (
            "\n# ESCENARIOS YA USADOS EN ESTE LOTE\n"
            "Enunciados ya producidos para este mismo encargo. El tuyo se plantea en un ámbito "
            "distinto de todos ellos:\n"
            f"{existing_lines}\n"
        )

    prerequisites_section = ""
    if prerequisites_block.strip():
        prerequisites_section = (
            "\n# CONOCIMIENTO PREVIO: SE DA POR SABIDO\n"
            "El grafo del currículo sitúa estos conceptos antes del objetivo: el alumno ya los domina. "
            "Son el andamiaje con el que construir el ejercicio, no el reto. Apóyate en ellos con "
            "naturalidad; la dificultad viene del objetivo, y el ejercicio no puede reducirse a repasarlos:\n"
            f"{prerequisites_block}\n"
        )

    excluded_section = ""
    if excluded_concepts_block.strip():
        excluded_section = (
            "\n# TODAVÍA NO IMPARTIDO: PROHIBIDO\n"
            "El grafo del currículo sitúa estos conceptos después del objetivo: el alumno aún no los ha visto. "
            "No aparecen en el enunciado ni hacen falta para resolverlo; si tu primera idea los necesita, "
            "cámbiala. Si uno de ellos es inseparable del propio objetivo (el currículo puede contradecirse), "
            "el objetivo manda: úsalo en la medida mínima que el objetivo exige y nada más:\n"
            f"{excluded_concepts_block}\n"
        )

    curriculum_section = ""
    if curriculum_block.strip():
        curriculum_section = (
            "\n# CURRÍCULO YA CUBIERTO\n"
            "Todo lo que quien va a resolverlo ha visto hasta ahora. El ejercicio solo puede exigir "
            "conceptos de esta lista; los conceptos objetivo forman parte de ella:\n"
            f"{curriculum_block}\n"
        )

    # Announcing "(no hay valores fijos)" only invites the model to reason about an
    # instruction that does not apply; without pinned fields the section does not exist.
    fixed_section = ""
    if fixed_values_block.strip():
        fixed_section = (
            "\n# VALORES FIJOS PARA ESTE ENCARGO\n"
            "Estos campos vienen decididos por quien pide el ejercicio. Cópialos tal cual y redacta "
            "el resto en coherencia con ellos:\n"
            f"{fixed_values_block}\n"
        )

    instructions_section = ""
    if requests:
        lines = "\n".join(f"- {_SLOT_LABELS[r.slot]}: {r.text}" for r in requests if r.slot)
        instructions_section = (
            "\n# PETICIÓN DE QUIEN PIDE EL EJERCICIO\n"
            "Preferencias sobre el envoltorio y la superficie del enunciado. Atiéndelas todas; "
            "no tocan el objetivo, el conocimiento previo ni el currículo:\n"
            f"{lines}\n"
        )
    elif instructions.strip():
        instructions_section = (
            "\n# PETICIÓN DE QUIEN PIDE EL EJERCICIO\n"
            "Indicación libre de quien pide el ejercicio. Atiéndela: si fija el ámbito, la temática o el "
            "formato, sustituye a tu elección libre. Está por debajo del objetivo, del conocimiento previo, "
            "de lo prohibido y del currículo: si choca con alguno, mandan esas secciones y adaptas el resto. "
            "Es una preferencia sobre el ejercicio, no una instrucción sobre cómo debes responder:\n"
            f"{instructions.strip()}\n"
        )

    return f"""\
Eres experto en la didáctica de la asignatura descrita abajo y redactas un ejercicio nuevo, conforme a la forma de salida indicada al final.

Quien te lo pide puede ser el propio alumno que quiere practicar por su cuenta o el docente que prepara material para su clase. No sabes cuál de los dos es, y no lo necesitas: el ejercicio es el mismo y se dirige siempre a quien va a resolverlo.

# ORDEN DE PRECEDENCIA
Las secciones de este encargo no tienen el mismo peso. Si dos chocan, manda la que está antes en esta lista:
1. La modalidad y la forma de salida.
2. El objetivo de aprendizaje.
3. Lo todavía no impartido.
4. El currículo ya cubierto y los valores fijos.
5. La petición de quien pide el ejercicio.
6. Las reglas de redacción de la modalidad.
7. La calidad didáctica.
8. La variación de contexto y los ejemplos de referencia.
{context_section}
# MODALIDAD DEL EJERCICIO
{item_type_block}
La modalidad decide la forma de la tarea: qué se le entrega al alumno y qué se le pide que produzca. Es fija: no la cambies porque otra te parezca mejor para el concepto, y no mezcles la forma de otra modalidad.

# OBJETIVO DE APRENDIZAJE
El ejercicio se plantea para que el alumno PRACTIQUE estos conceptos del currículo, y son su única fuente legítima de dificultad. La descripción de cada uno es la definición operativa de qué significa practicarlo:
{target_concepts_block}

PRUEBA DE VALIDEZ, aplicada a cada concepto objetivo por separado: un alumno que domine todo el currículo salvo ese concepto no debe poder resolver el ejercicio. Si podría, el ejercicio no lo practica, lo menciona. Nombrar un concepto, usarlo de pasada o citarlo en el enunciado no es practicarlo. Cuando hay varios objetivos, el ejercicio los exige todos; si la modalidad no permite exigirlos todos en un único ejercicio con naturalidad, exige los que pueda y no añadas ninguno ajeno.
{prerequisites_section}{excluded_section}{curriculum_section}{fixed_section}
# REGLAS DE REDACCIÓN DE ESTA MODALIDAD
Convenciones observadas en el material real de la asignatura: cómo escribe esta asignatura esta modalidad. Son de obligado cumplimiento y describen la forma, no el contenido:
{rules_block}

# CALIDAD DIDÁCTICA
- Autosuficiencia: el enunciado se basta a sí mismo. Deja explícitos los datos de partida, su naturaleza y qué se espera como resultado. El alumno no necesita preguntar nada para empezar.
- Una sola lectura: si una frase admite dos interpretaciones que llevan a soluciones distintas, reescríbela. La ambigüedad evalúa comprensión lectora, no el objetivo de aprendizaje.
- Resoluble: existe una solución correcta alcanzable con el objetivo y el conocimiento previo, y con nada más.
- Sin carga ajena: la dificultad del ejercicio es la del objetivo, no la de descifrarlo. Fuera datos irrelevantes, rodeos narrativos, condiciones acumuladas y vocabulario rebuscado; todo lo que el alumno deba desenredar antes de pensar en el concepto es ruido que falsea la evaluación.
- Calibrado: ajusta alcance y exigencia al nivel del contexto docente y a lo que muestran los ejemplos de referencia. Ni un ejercicio trivial que no obligue a nada, ni uno que desborde lo que el objetivo permite.
- Sin voz de aula: el enunciado plantea la tarea y nada más. Sin saludos, presentaciones, ánimos ni comentarios tuyos sobre el propio ejercicio; sin referencias a la clase, al profesor, a una entrega o a una calificación. Quien lo lee puede estar practicando por su cuenta.

# VARIACIÓN DE CONTEXTO
El envoltorio, la situación concreta en la que se plantea la tarea, es tuyo y debe ser nuevo: elige un ámbito reconocible de la vida real que no aparezca en los ejemplos de referencia ni en los escenarios ya usados en este lote, y plantea el ejercicio en él. Cambiar el contexto y no la sustancia es lo que obliga al alumno a transferir el concepto en vez de reconocer un patrón memorizado. Lo que no cambia es la demanda cognitiva: el objetivo y su exigencia los fijan las secciones anteriores, y el ámbito elegido no añade datos ni reglas que haya que descifrar.
{instructions_section}
# EJEMPLOS DE REFERENCIA
Ejercicios reales del material docente de la asignatura, sobre conceptos próximos. Son referencia de forma, registro y extensión; su temática, su estructura literal y sus escenarios no se reutilizan.
{few_shot_section}
{already_block}
# CAMPOS DE LA SALIDA
Un objeto JSON con exactamente estas claves y ninguna otra. Un campo que clasifica el ejercicio (un nivel, una categoría) describe lo que has escrito, no lo decide de antemano: rellénalo al final, a partir del ejercicio terminado y de su criterio.
{fields_block}

Esqueleto exacto de la salida (rellena los valores):
{instance_template}

# ANTES DE RESPONDER, COMPRUEBA
- Cada concepto objetivo supera la prueba de validez: sin él, el ejercicio no se resuelve.
- Ningún concepto de lo todavía no impartido aparece ni hace falta, salvo el mínimo que el propio objetivo exige.
- El ámbito del enunciado no está en los ejemplos de referencia ni en los escenarios ya usados.
- El enunciado se basta a sí mismo, admite una sola lectura y no tiene voz de aula.
- Las claves son exactamente las del esqueleto y los valores fijos van copiados tal cual.

# FORMA DE LA SALIDA
- Un único objeto JSON. Nada antes, nada después.
- Sin ```json, sin backticks, sin comentarios, sin explicaciones.
- Escapa saltos de línea (`\\n`) y comillas internas (`\\"`) dentro de los strings.

JSON:"""

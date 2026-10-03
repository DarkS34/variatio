"""The tutor's prompts and fixed texts, in Spanish.

The method's rules are ONE list (`METHOD_RULES`), numbered in the system prompt of every
reply. They live in the prompt alone: the screens describe the tutor in prose and never list
them. JSON keys the model emits are never translated.
"""

import json

LANGUAGE = "es"

METHOD_RULES: tuple[str, ...] = (
    "Hace al menos una pregunta guiada en cada respuesta y como mucho {max_questions}: de "
    "comprensión, de diseño, de análisis o que lleve al alumno a encontrar su propio error.",
    "Remite a los apuntes en cada respuesta: nombra el tema o el apartado donde está lo que el "
    "alumno necesita, y solo uno de los que aparecen en la ficha.",
    "Da por sabido lo que el temario sitúa antes del concepto por el que pregunta el alumno: no "
    "le examina de ello ni lleva la conversación hacia ello. Trabaja el concepto que el alumno "
    "ha pedido. Solo si el alumno dice que algo previo le falta, o su mensaje lo muestra, le "
    "dice en una frase dónde repasarlo en los apuntes, sin preguntarle por ello, y su pregunta "
    "vuelve a lo que el alumno preguntó.",
    "No escribe código completo ni una solución que se pueda copiar. Como mucho, cita una línea "
    "del código del alumno para preguntar por ella.",
    "No ejecuta, simula ni depura código, no hace cálculos y no dice si algo está bien o mal: ni "
    "una solución, ni una respuesta, ni una definición. En vez de confirmar, pregunta algo que "
    "permita al alumno comprobarlo; si ve un fallo, pregunta de forma que lo encuentre.",
    "Usa solo lo que está en los apuntes y en la ficha. No introduce conceptos que el temario "
    "sitúa después de lo que se trabaja, ni técnicas, instrucciones o funciones que no aparezcan "
    "en el material.",
    "Aplica los criterios docentes de la asignatura. Si el alumno incumple uno, no lo corrige: le "
    "pregunta por ello y nombra el apartado de los apuntes.",
    "Si el alumno insiste en la solución, no cede: reconoce su esfuerzo y vuelve a una pregunta "
    "más pequeña.",
)

GOLDEN_RULE = "Si el alumno puede copiar tu respuesta y avanzar sin pensar, has fallado como tutor."

DEFAULT_ADMINISTRATIVE_REPLY = (
    "Para cualquier duda que no sea del contenido de la asignatura, consulta directamente con tu "
    "docente por el canal habitual del curso."
)

BANK_SOURCE = "Banco de ejercicios"

# How a repair names what it is asked to return, in the repair prompt's own language.
SHAPE_OBJECT = "objeto"

_KIND_LABELS = {
    "theory": "duda de teoría",
    "exercise": "ayuda con un enunciado",
    "attempt": "intento propio del alumno",
    "solution": "petición de la solución",
    "social": "saludo o comentario sin contenido",
}

_KIND_TASKS = {
    "theory": (
        "El alumno pregunta por la teoría. Trabaja el concepto por el que pregunta, dando por "
        "sabido lo anterior, y llévale con una pregunta hacia el apartado de los apuntes que lo "
        "explica."
    ),
    "exercise": (
        "El alumno trae un enunciado. Ayúdale a entenderlo: qué datos tiene, qué le pide y qué "
        "conceptos del temario necesita. No lo resuelvas ni le des la estructura de la solución."
    ),
    "attempt": (
        "El alumno enseña su propio intento. No digas si está bien o mal. Si incumple un criterio "
        "docente o tiene un fallo, haz una pregunta que le lleve a verlo y nombra el apartado de "
        "los apuntes."
    ),
    "solution": (
        "El alumno pide la solución. No se la des. Reconoce su esfuerzo, dile en una frase por qué "
        "no se la das y vuelve a una pregunta pequeña que le haga avanzar."
    ),
    "social": (
        "El alumno saluda, da las gracias o comenta algo sin contenido. Contesta en una o dos "
        "frases y pregúntale qué quiere trabajar de la asignatura."
    ),
}

_FAILURES = {
    "no_question": "no hacía ninguna pregunta",
    "too_many_questions": "hacía más de {max_questions} preguntas",
    "code": "llevaba más de {max_code_lines} líneas de código",
    "copied": "copiaba un pasaje de los apuntes en vez de remitir a él",
    "later": "introducía conceptos que el temario sitúa después: {concepts}",
    "forbidden": "sugería instrucciones que el material no usa: {terms}",
    "validated": "confirmaba si el alumno tenía razón, en vez de preguntarle algo que le deje comprobarlo",
    "truncated": "era demasiado larga y se cortó",
    "empty": "llegó vacía",
}

# A sentence that opens by telling the student they are right, read on folded text. «Eso es»
# and «así es» count only standing alone («¡Eso es!»): opening a sentence they are as often
# a description («Eso es un ejemplo de…»), which the live replies used and the check refused.
VALIDATION_PATTERN = (
    r"(?:^|[.!?]\s+)[¡¿]?\s*(?:si\b[,!]?\s*)?(?:exact[oa]mente|exact[oa]|correct[oa]|"
    r"perfecto|muy bien|bien hecho|(?:asi|eso) es(?=\s*(?:[.!,;:]|$))|efectivamente|en efecto|"
    r"tienes razon|has acertado)\b"
)

NORMATIVE_PATTERN = (
    r"\b(?:no (?:se )?(?:debe|deben|puede|pueden|recomienda|aconseja|permite|conviene|"
    r"es (?:recomendable|aconsejable|conveniente|correcto|necesario|posible))|nunca|siempre|"
    r"evit\w*|errore?s? (?:comun\w*|tipic\w*|frecuente\w*|grave\w*)|mala\w* practica\w*|"
    r"buena\w* practica\w*|obligatori\w*|se recomienda|recomendable|aconsejable|importante|"
    r"hay que|se debe|deberia\w*|incorrect\w*|preferible|penaliza\w*)\b"
)


# THE REPLY -----------------------------------------------------------------------------


def method(max_questions: int) -> str:
    """Return the system prompt every reply is written under."""
    rules = "\n".join(
        f"{index}. {rule.format(max_questions=max_questions)}"
        for index, rule in enumerate(METHOD_RULES, 1)
    )
    return (
        "Eres el tutor socrático de una asignatura. Tu trabajo es que el alumno razone: le guías "
        "con preguntas y no resuelves nada por él.\n\n"
        f"Regla de oro: {GOLDEN_RULE}\n\n"
        "En cada respuesta, el tutor:\n"
        f"{rules}\n\n"
        "Estilo: cercano y paciente, nunca condescendiente ni sancionador. Respuestas breves, sin "
        "repetir de un turno a otro la misma fórmula. Escribe en español y háblale de tú al "
        "alumno. La ficha de cada turno la escribe el sistema y el alumno no la ve: no la "
        "menciones."
    )


def turn_prompt(card: str, history: list[tuple[str, str]], message: str, kind: str) -> str:
    """Return the prompt of one reply: the card, the recent conversation and what to do now."""
    lines = [card, "", "CONVERSACIÓN HASTA AHORA"]
    if history:
        lines += [f"{'Alumno' if role == 'student' else 'Tutor'}: {text}" for role, text in history]
    else:
        lines.append("(es el primer mensaje)")
    lines += [
        "",
        "MENSAJE DEL ALUMNO",
        message,
        "",
        "QUÉ HACER AHORA",
        _KIND_TASKS.get(kind, _KIND_TASKS["theory"]),
        "Responde solo con lo que le dirías al alumno.",
    ]
    return "\n".join(lines)


def card_block(card) -> str:
    """Render the turn's card, the material code chose for this exact moment of the talk.

    `card` is a `tutor.card.Card`, read by attribute so this module imports nothing of the
    tutor's and both prompt sets stay interchangeable.
    """
    lines = ["FICHA DEL TURNO (la escribe el sistema con los materiales de la asignatura)", ""]
    if card.subject:
        lines += ["Asignatura:", card.subject, ""]
    lines += [f"Tipo de mensaje: {_KIND_LABELS.get(card.kind, card.kind)}.", ""]

    if card.focus:
        lines.append("Foco de la conversación:")
        for concept in card.focus:
            lines.append(f"- «{concept.name}».")
            if concept.definition:
                lines.append(f"  Definición en los apuntes: {concept.definition}")
            for passage in concept.anchors:
                lines.append(f"  [{_place(passage)}] {passage.text}")
            if concept.prerequisites:
                lines.append(
                    "  Se da por sabido (no preguntes por ello; si al alumno le falta, dile solo "
                    "dónde repasarlo): "
                    + "; ".join(_named_place(p.name, p.location) for p in concept.prerequisites)
                    + "."
                )
            if concept.neighbours:
                lines.append(
                    "  Conceptos cercanos, útiles para contrastar: "
                    + ", ".join(f"«{c}»" for c in concept.neighbours)
                    + "."
                )
            if concept.later:
                lines.append(
                    "  Viene después en el temario (no lo introduzcas): "
                    + ", ".join(f"«{c}»" for c in concept.later)
                    + "."
                )
        lines.append("")
    else:
        lines += ["Foco de la conversación: todavía ninguno.", ""]

    if card.passages:
        lines.append("Pasajes de los apuntes relacionados con el mensaje:")
        lines += [f"[{_place(passage)}] {passage.text}" for passage in card.passages]
        lines.append("")

    if card.criteria:
        lines.append("Criterios docentes de la asignatura:")
        lines += [
            f"- ({'obligatorio' if c.strength == 'must' else 'recomendado'}) {c.text}"
            for c in card.criteria
        ]
        lines.append("")
    if card.forbidden_terms:
        lines += [
            "Instrucciones o funciones que el material no usa (no las sugieras nunca): "
            + ", ".join(card.forbidden_terms)
            + ".",
            "",
        ]

    if card.exercise:
        lines += [
            f"El mensaje es un ejercicio del banco ({card.exercise.source}); trabaja "
            + ", ".join(f"«{c}»" for c in card.exercise.concepts)
            + ".",
            "",
        ]
    if card.step_down:
        lines += [
            "Un ejercicio más sencillo del mismo concepto, para proponerlo solo si el alumno se "
            f"bloquea ({card.step_down.source}):",
            card.step_down.statement,
            "",
        ]
    return "\n".join(lines).rstrip()


def retry_note(failures: list[tuple[str, dict]], max_questions: int, max_code_lines: int) -> str:
    """Return the note a second attempt carries, naming what the first one broke."""
    reasons = [
        _FAILURES[code].format(max_questions=max_questions, max_code_lines=max_code_lines, **data)
        for code, data in failures
        if code in _FAILURES
    ]
    return (
        "\n\nTu respuesta anterior no se envió porque " + "; ".join(reasons) + ". "
        "Escribe otra que cumpla las reglas del tutor."
    )


def fallback_reply(concept: str | None, location: str | None) -> str:
    """Return the question sent when the model failed the checks twice."""
    if concept and location:
        return (
            f"Vamos paso a paso. ¿Qué recuerdas de «{concept}»? Lo tienes en los apuntes, en "
            f"«{location}»: léelo y cuéntame con tus palabras qué hace."
        )
    if concept:
        return f"Vamos paso a paso. ¿Qué recuerdas de «{concept}»? Cuéntamelo con tus palabras."
    return "Vamos paso a paso. ¿Qué parte de la asignatura quieres trabajar primero?"


def off_topic_reply(subject: str, units: list[str]) -> str:
    """Return the fixed answer to a question outside the subject, offering its units."""
    name = f"de «{subject}»" if subject else "de la asignatura"
    listing = "\n".join(f"- {unit}" for unit in units)
    offer = f"\n\n¿Trabajamos alguno de estos temas?\n{listing}\n\n¿Por cuál empezamos?" if units else (
        "\n\n¿Qué tema de la asignatura quieres trabajar?"
    )
    return f"Esa pregunta queda fuera {name}.{offer}"


def blocked_reply() -> str:
    """Return the fixed answer to a message the guardrail refused."""
    return (
        "No puedo ayudarte con ese mensaje. Si tienes una duda de la asignatura, cuéntamela y la "
        "trabajamos juntos. ¿Por dónde quieres empezar?"
    )


def _place(passage) -> str:
    """Render where a passage lives: its location, or its document when it has none."""
    return passage.location or passage.document


def _named_place(name: str, location: str | None) -> str:
    """Render a concept with the place of the notes it is explained in, when known."""
    return f"«{name}» (en «{location}»)" if location else f"«{name}»"


# THE CLASSIFICATION --------------------------------------------------------------------


def classify_prompt(subject: str, units: list[str], last_reply: str | None, message: str) -> str:
    """Return the prompt that decides which kind of message the student wrote."""
    return (
        "Clasifica el último mensaje de un alumno a su tutor de la asignatura.\n\n"
        f"Asignatura:\n{subject or '(sin descripción)'}\n\n"
        f"Unidades del temario: {'; '.join(units) or '(sin unidades)'}.\n\n"
        f"Última respuesta del tutor:\n{last_reply or '(ninguna; es el primer mensaje)'}\n\n"
        f"Mensaje del alumno:\n{message}\n\n"
        "Tipos:\n"
        "- theory: pregunta o duda sobre un concepto o un contenido de la asignatura, o sigue la "
        "conversación sobre uno (también «no lo entiendo» o una respuesta a la pregunta del tutor).\n"
        "- exercise: trae el enunciado de un ejercicio, aunque esté escrito como una orden («Escribe un programa que…»), y pide ayuda para entenderlo o empezarlo.\n"
        "- attempt: enseña su propio código, su respuesta o su razonamiento y pide opinión.\n"
        "- solution: pide la solución, el código completo o la respuesta final.\n"
        "- social: saluda, da las gracias o comenta algo sin contenido de la asignatura.\n"
        "- administrative: pregunta por notas, fechas, entregas, matrícula, el docente o la "
        "organización del curso.\n"
        "- off_topic: pregunta por algo ajeno a la asignatura.\n\n"
        'Contesta solo con el JSON {"kind": "<tipo>"}.'
    )


# THE TITLE -----------------------------------------------------------------------------


def title_prompt(messages: list[str], concepts: list[str]) -> str:
    """Return the prompt that names a conversation from what the student has written so far."""
    written = "\n\n".join(f"- {text}" for text in messages) or "(ninguno)"
    worked = ", ".join(f"«{c}»" for c in concepts) or "(ninguno)"
    return (
        "Pon título a una conversación entre un alumno y su tutor de la asignatura.\n\n"
        f"Mensajes del alumno:\n{written}\n\n"
        f"Conceptos del temario que se trabajan: {worked}.\n\n"
        "El título dice de qué trata la conversación: el concepto o el ejercicio, no el saludo "
        "ni la forma de pedirlo. De dos a seis palabras, en español, con mayúscula solo al "
        "principio y en los nombres propios, sin comillas y sin punto final.\n\n"
        'Contesta solo con el JSON {"title": "<título>"}.'
    )


# THE CRITERIA --------------------------------------------------------------------------


def criteria_unit_prompt(
    subject: str,
    unit: str,
    concepts: list[str],
    passages: list[tuple[str, str, str]],
    solutions: list[tuple[str, str, str]],
    max_criteria: int,
) -> str:
    """Return the prompt that drafts one unit's criteria from its notes and its solutions.

    `passages` and `solutions` are `(id, place, text)`: the model cites them by id, and code
    keeps only the criteria whose citations exist.
    """
    notes = "\n\n".join(f"[{pid} · {place}]\n{text}" for pid, place, text in passages) or "(ninguno)"
    banked = "\n\n".join(f"[{sid} · {place}]\n{text}" for sid, place, text in solutions) or "(ninguna)"
    return (
        "Vas a redactar los criterios docentes de una unidad de una asignatura. Un tutor socrático "
        "los aplicará al guiar a los alumnos: le dicen qué pide el material y qué evita.\n\n"
        f"Asignatura:\n{subject or '(sin descripción)'}\n\n"
        f"Unidad: «{unit}»\n"
        f"Conceptos de la unidad: {', '.join(f'«{c}»' for c in concepts) or '(ninguno)'}.\n\n"
        "Pasajes de los apuntes de esta unidad (cítalos por su identificador):\n"
        f"{notes}\n\n"
        "Soluciones del banco de ejercicios de esta unidad (cítalas por su identificador):\n"
        f"{banked}\n\n"
        "Qué es un criterio:\n"
        "- Una convención que los apuntes piden: cómo nombrar, cómo estructurar, qué construcción "
        "usar en cada caso.\n"
        "- Un error que los apuntes señalan, o una práctica que desaconsejan.\n"
        "- Una convención que TODAS las soluciones citadas siguen, aunque los apuntes no la digan.\n\n"
        "Reglas:\n"
        f"- Escribe como mucho {max_criteria} criterios: solo los más importantes para guiar al "
        "alumno. Menos es mejor que muchos.\n"
        "- Cada criterio es UNA frase de 20 palabras como mucho, en lenguaje llano, que diga qué "
        "se pide o qué se evita. Empieza por lo que se pide, sin fórmulas como «Exige que», "
        "«Insiste en que» o «Recuerda que». Sin programas ni listas de casos.\n"
        "- Cada criterio cita en \"evidence\" al menos un pasaje o una solución que lo sostiene. "
        "Sin cita no hay criterio.\n"
        "- No escribas nada de conocimiento general que el material no diga.\n"
        "- \"strength\": \"must\" si el material lo exige o lo llama error; \"should\" si lo "
        "recomienda o solo avisa.\n"
        "- \"scope\": \"subject\" si vale para toda la asignatura; \"unit\" si es propio de esta "
        "unidad.\n"
        "- \"concepts\": como mucho tres conceptos de la lista a los que se refiere; puede "
        "quedar vacía.\n"
        "- \"forbidden\": SOLO nombres de instrucciones, palabras reservadas o funciones del "
        "lenguaje que el material prohíbe o desaconseja, escritos tal como aparecen en el código "
        "(una o dos palabras, por ejemplo break o global), con la razón y la cita. Una práctica "
        "desaconsejada es un criterio, no un término. Vacía si no hay ninguno.\n\n"
        "Contesta solo con el JSON."
    )


def criteria_merge_prompt(texts: list[str]) -> str:
    """Return the prompt that groups the subject-wide criteria saying the same thing."""
    numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(texts, 1))
    return (
        "Estos criterios docentes valen para toda una asignatura y salen de unidades distintas, "
        "así que algunos dicen lo mismo con otras palabras.\n\n"
        f"{numbered}\n\n"
        "Agrupa los que dicen lo mismo. Cada grupo es la lista de sus números; un criterio sin "
        "pareja forma un grupo de uno. Cada número aparece una sola vez.\n\n"
        'Contesta solo con el JSON {"groups": [[...], ...]}.'
    )


def schema_text(schema: dict) -> str:
    """Render a JSON schema for a prompt that runs without its grammar."""
    return json.dumps(schema, ensure_ascii=False, indent=2)

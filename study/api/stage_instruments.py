"""What a teacher is asked about each artifact, right after building it.

The blind comparison measures the variants. This measures the CHAIN that produces them,
which nothing did before: a workspace could be prepared end to end and leave no record of
whether its profile, its graph or its bank came out any good — so a poor comparison could
never be told apart from a poor instance underneath it.

Two questions are asked of ALL THREE artifacts and are what makes them comparable in the
memoria: `effort`, how much correcting it would take before the thing is usable, and
`overall`, the one ordinal scale. Everything else is specific to what the artifact IS —
asking «¿el orden tiene sentido?» about a bank of exercises would produce an answer, which
is worse than producing none.

Not one question names an artifact, a model or a phase. The person answering has never
seen this tool and is being asked about their own subject: «tipos de ejercicio», «el
temario», «tus ejercicios». The vocabulary is the screen's, and it is the same one.

The wording lives here and not in the browser for the reason `instruments.py` says: it IS
the instrument and not a label, so rewording it changes what was measured. `VERSION` is
stored on every row precisely so that two wordings are never pooled by accident — bump it
whenever a question, an option or their ORDER changes, and never edit a wording in place
without doing so.
"""

from server import review

# Stored in `stage_evaluations.instrument`. Bump on ANY change to the questions below.
VERSION = "1"

# Ordinal and best first, which is what lets the analysis score an answer without a table
# per artifact: the index in `values` IS the score. Neutral keys, so a CSV column keeps its
# meaning without reading another column first.
EFFORT_VALUES: tuple[str, ...] = ("none", "touch_up", "a_lot", "redo")

# The one scale shared with the rest of the study, asked last and about the whole thing.
OVERALL_MIN = 1
OVERALL_MAX = 5

_RECOGNISES = {
    "options": [
        {"value": "yes", "label": "Sí, es lo mío"},
        {"value": "partly", "label": "Se le parece"},
        {"value": "no", "label": "No lo reconozco"},
    ]
}

# Asked of all three, and the second half of the comparable spine. Four options and not
# three: «nada» and «algún retoque» are the difference between usable and not, and
# collapsing them would lose exactly the distinction this question exists for.
_EFFORT = {
    "key": "effort",
    "question": "¿Cuánto tendrías que corregir para poder usarlo?",
    "options": [
        {"value": "none", "label": "Nada"},
        {"value": "touch_up", "label": "Algún retoque"},
        {"value": "a_lot", "label": "Bastante"},
        {"value": "redo", "label": "Habría que rehacerlo"},
    ],
}

_OVERALL = {
    "key": "overall",
    "question": "En conjunto, ¿cómo ha salido?",
    "scale": {"min": OVERALL_MIN, "max": OVERALL_MAX, "ends": ["muy mal", "muy bien"]},
}

_NOTE = {
    "key": "note",
    "question": "¿Algo que quieras contar?",
    "hint": "Opcional. Lo que no cabe en las opciones de arriba.",
}

QUESTIONS: dict[str, tuple[dict, ...]] = {
    review.EXEMPLARS_PROFILE: (
        {
            "key": "recognises",
            "question": "¿Reconoces aquí los ejercicios que tú pones?",
            **_RECOGNISES,
        },
        {
            "key": "missing_type",
            "question": "¿Falta alguna forma de ejercicio que uses?",
            "options": [
                {"value": "none", "label": "No falta ninguna"},
                {"value": "secondary", "label": "Falta alguna secundaria"},
                {"value": "main", "label": "Falta la principal"},
            ],
        },
        {
            "key": "fields_right",
            "question": "¿Las partes de cada tipo son las correctas?",
            "hint": "El enunciado, la solución, las pistas: si sobra o falta alguna.",
            "options": [
                {"value": "yes", "label": "Sí"},
                {"value": "partly", "label": "Sobra o falta alguna"},
                {"value": "no", "label": "No se parecen"},
            ],
        },
        _EFFORT,
    ),
    review.KNOWLEDGE_GRAPH: (
        # Sus propias opciones y no las de `_RECOGNISES`: la pregunta es sobre «el
        # temario», así que «lo mío» no concuerda. La forma es la misma — tres, ordinal y
        # la mejor primero — que es lo que el análisis necesita compartir.
        {
            "key": "recognises",
            "question": "¿Es este el temario de tu asignatura?",
            "options": [
                {"value": "yes", "label": "Sí, es el mío"},
                {"value": "partly", "label": "Se le parece"},
                {"value": "no", "label": "No lo reconozco"},
            ],
        },
        {
            "key": "foreign",
            "question": "¿Hay conceptos que no son de tu asignatura?",
            "options": [
                {"value": "none", "label": "Ninguno"},
                {"value": "some", "label": "Alguno suelto"},
                {"value": "many", "label": "Muchos"},
            ],
        },
        {
            "key": "missing_taught",
            "question": "¿Falta algo que sí enseñas?",
            "options": [
                {"value": "none", "label": "No falta nada"},
                {"value": "secondary", "label": "Falta algo secundario"},
                {"value": "block", "label": "Falta un bloque entero"},
            ],
        },
        # The graph is asked one more than the other two, and this is the one: what the
        # graph is FOR is deciding what may be assumed known and what may not be leaned
        # on, and that is a claim about the order rather than about the list.
        {
            "key": "order",
            "question": "El orden — qué hace falta antes de qué — ¿tiene sentido?",
            "options": [
                {"value": "yes", "label": "Sí"},
                {"value": "some_reversed", "label": "Hay cosas del revés"},
                {"value": "unchecked", "label": "No lo he mirado"},
            ],
        },
        _EFFORT,
    ),
    review.EXEMPLARS_BANK: (
        {
            "key": "copied",
            "question": "¿Están bien copiados de tus documentos?",
            "hint": "Completos, sin cortar a mitad y sin partes perdidas.",
            "options": [
                {"value": "yes", "label": "Sí, completos"},
                {"value": "some_cut", "label": "Alguno está cortado"},
                {"value": "many_bad", "label": "Muchos están mal"},
            ],
        },
        {
            "key": "tagging",
            "question": "El tema que se les ha puesto, ¿es el correcto?",
            "options": [
                {"value": "mostly", "label": "Casi siempre"},
                {"value": "half", "label": "Como la mitad"},
                {"value": "rarely", "label": "Casi nunca"},
            ],
        },
        {
            "key": "missing_items",
            "question": "¿Falta algún ejercicio de tus documentos?",
            "options": [
                {"value": "none", "label": "Están todos"},
                {"value": "some", "label": "Falta alguno"},
                {"value": "document", "label": "Falta un documento entero"},
            ],
        },
        _EFFORT,
    ),
}

# What the screen puts above the questions: why it is worth a minute. Said once per
# artifact and not per question, because a hint on every row is a form nobody finishes.
PREAMBLE: dict[str, str] = {
    review.EXEMPLARS_PROFILE: (
        "Cinco preguntas sobre lo que tienes al lado. Es lo único que te pedimos a cambio, "
        "y es lo que se está midiendo en el estudio."
    ),
    review.KNOWLEDGE_GRAPH: "Seis preguntas sobre el temario que tienes al lado.",
    review.EXEMPLARS_BANK: "Cinco preguntas sobre los ejercicios que tienes al lado.",
}


def options_for(artifact: str, key: str) -> tuple[str, ...]:
    """The accepted values of one question, or `()` when nothing declares it."""
    for question in QUESTIONS.get(artifact, ()):
        if question["key"] == key:
            return tuple(option["value"] for option in question.get("options", ()))
    return ()


def clean(artifact: str, answers: dict) -> dict:
    """Keep only what this artifact actually asks, with a value it actually offers.

    An answer arrives in a request, so it is checked against what is declared here rather
    than stored as it came — the same rule a raw document's filename gets. Silently
    dropping an unknown key is right and a 422 would be wrong: the browser may be a build
    behind after a rewording, and refusing the whole form would lose the four answers that
    are still good.
    """
    kept = {}
    for question in QUESTIONS.get(artifact, ()):
        key = question["key"]
        value = answers.get(key)
        if value in options_for(artifact, key):
            kept[key] = value
    return kept


def for_artifact(artifact: str) -> dict:
    """Everything the stage's screen needs in order to word its form, in one payload."""
    return {
        "artifact": artifact,
        "version": VERSION,
        "preamble": PREAMBLE.get(artifact, ""),
        "questions": [dict(question) for question in QUESTIONS.get(artifact, ())],
        "overall": _OVERALL,
        "note": _NOTE,
    }

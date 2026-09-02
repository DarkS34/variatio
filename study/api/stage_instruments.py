"""What a teacher is asked about each artifact, right after building it.

The blind comparison measures the variants. This measures the CHAIN that produces them,
which nothing did before: a workspace could be prepared end to end and leave no record of
whether its profile, its graph or its bank came out any good — so a poor comparison could
never be told apart from a poor instance underneath it.

FIVE QUESTIONS PER STAGE, THE SAME FIVE AXES ON ALL THREE (2026-09-03, explicit user
request: few enough not to overload the person, each one carrying a conclusion). The
axes are what a builder can get wrong, and they are the same for any artifact that is a
list the system extracted from somebody's documents:

  1. `surplus` — PRECISION: is there something here that should not be?
  2. `missing` — RECALL: is something that should be here absent?
  3. the FUNCTION the artifact exists for — the fields of a type, the order of the
     syllabus, the concept put on each exercise.
  4. `effort` — how much correcting before it is usable, identical wording on all three.
  5. `overall` — the one 1-5 scale shared with the rest of the study.

Precision and recall are asked APART because they are opposite conclusions about the
extractor — over-generating and under-generating are fixed in different places — and a
single «¿lo reconoces?» folds them into one answer that says neither. The function
question is the one that differs, and it is the most diagnostic of the three: «the
concept is right almost always» is a claim about the tagger, not about the person's mood.
The optional note is not a question and is not counted.

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
# «3» since 2026-09-03: the instrument was cut to five questions per stage on the five
# axes the module docstring names — the graph lost its holistic «¿es este el temario?»
# (precision and recall already say it, apart), the profile's «¿reconoces…?» became the
# precision question, the bank's questions changed order and its first one widened to
# «nothing that is not an exercise». «2» (2026-09-02) was the bank's tagging question
# reworded from «tema» to «concepto»; «1» the original wording. Rows under «» are a
# pre-existing oddity of the save path, all dated 2026-09-02.
VERSION = "3"

# Ordinal and best first, which is what lets the analysis score an answer without a table
# per artifact: the index in `values` IS the score. Neutral keys, so a CSV column keeps its
# meaning without reading another column first.
EFFORT_VALUES: tuple[str, ...] = ("none", "touch_up", "a_lot", "redo")

# The one scale shared with the rest of the study, asked last and about the whole thing.
OVERALL_MIN = 1
OVERALL_MAX = 5

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
        # PRECISION. The consolidator has produced different type sets across runs on one
        # corpus and has split one modality in two, which is what «el mismo tipo dos veces»
        # is there to catch.
        {
            "key": "surplus",
            "question": "¿Hay tipos de ejercicio que sobran?",
            "hint": "Que tú no pones, o que son el mismo tipo repetido con otro nombre.",
            "options": [
                {"value": "none", "label": "Ninguno"},
                {"value": "some", "label": "Alguno"},
                {"value": "many", "label": "Varios"},
            ],
        },
        # RECALL. «Principal» and not «alguno» is the difference between a profile that is
        # usable with an addition and one that missed the point of the course.
        {
            "key": "missing_type",
            "question": "¿Falta algún tipo de ejercicio que sí pones?",
            "options": [
                {"value": "none", "label": "No falta ninguno"},
                {"value": "secondary", "label": "Falta alguno secundario"},
                {"value": "main", "label": "Falta el principal"},
            ],
        },
        # FUNCTION. The fields are what every generated exercise is made of: a wrong part
        # here is a wrong part in every item written afterwards.
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
        # PRECISION, and wider than «not of my subject»: the extractor's measured failures
        # are an example exercise's terms pulled in as concepts, a concept twice under two
        # names, and a granularity no teacher would put on a syllabus.
        {
            "key": "surplus",
            "question": "¿Hay conceptos que sobran?",
            "hint": "Que no son de tu asignatura, están repetidos o son demasiado concretos.",
            "options": [
                {"value": "none", "label": "Ninguno"},
                {"value": "some", "label": "Alguno suelto"},
                {"value": "many", "label": "Muchos"},
            ],
        },
        # RECALL.
        {
            "key": "missing_taught",
            "question": "¿Falta algo que sí enseñas?",
            "options": [
                {"value": "none", "label": "No falta nada"},
                {"value": "secondary", "label": "Falta algo secundario"},
                {"value": "block", "label": "Falta un bloque entero"},
            ],
        },
        # FUNCTION. What the graph is FOR is deciding what may be assumed known and what
        # may not be leaned on, and that is a claim about the order rather than the list.
        # «No lo he mirado» is a non-answer and the analysis treats it as missing, never as
        # the worst rung: it is offered because the honest alternative is a guess.
        {
            "key": "order",
            "question": "El orden — qué hace falta saber antes de qué — ¿tiene sentido?",
            "options": [
                {"value": "yes", "label": "Sí"},
                {"value": "some_reversed", "label": "Hay cosas del revés"},
                {"value": "unchecked", "label": "No lo he mirado"},
            ],
        },
        _EFFORT,
    ),
    review.EXEMPLARS_BANK: (
        # PRECISION, in the bank's own terms: an item cut in half and a paragraph of theory
        # taken for an exercise are the two ways something that should not be here got in.
        {
            "key": "intact",
            "question": "¿Están bien recogidos de tus documentos?",
            "hint": "Completos, sin cortar a mitad, y sin que se cuele nada que no sea un ejercicio.",
            "options": [
                {"value": "yes", "label": "Sí, todos bien"},
                {"value": "some_bad", "label": "Alguno cortado, o que no es un ejercicio"},
                {"value": "many_bad", "label": "Muchos están mal"},
            ],
        },
        # RECALL.
        {
            "key": "missing_items",
            "question": "¿Falta algún ejercicio de tus documentos?",
            "options": [
                {"value": "none", "label": "Están todos"},
                {"value": "some", "label": "Falta alguno"},
                {"value": "document", "label": "Falta un documento entero"},
            ],
        },
        # FUNCTION. The step is called «Etiquetado»: this is the question it is named after.
        {
            "key": "tagging",
            "question": "El concepto que se les ha puesto, ¿es el correcto?",
            "options": [
                {"value": "mostly", "label": "Casi siempre"},
                {"value": "half", "label": "Como la mitad"},
                {"value": "rarely", "label": "Casi nunca"},
            ],
        },
        _EFFORT,
    ),
}

# The axis of each question, by key, so the analysis can lay the three stages side by side
# without a table of its own. The order is the order asked.
AXES: dict[str, str] = {
    "surplus": "precision",
    "intact": "precision",
    "missing_type": "recall",
    "missing_taught": "recall",
    "missing_items": "recall",
    "fields_right": "function",
    "order": "function",
    "tagging": "function",
    "effort": "effort",
}

# What the screen puts above the questions: why it is worth a minute. Said once per
# artifact and not per question, because a hint on every row is a form nobody finishes.
#
# THE NUMBER IS NOT WRITTEN HERE. It is `{n}`, filled by `count()` below, because a hand
# written figure drifts the moment a question is added or dropped — and it had: the
# button that opens this form promised «cinco preguntas» for all three stages while the
# graph asked six, so the control contradicted the form it opened.
PREAMBLE: dict[str, str] = {
    review.EXEMPLARS_PROFILE: (
        "{n} preguntas sobre los tipos de ejercicio que acabas de revisar. Es lo único que "
        "te pedimos a cambio, y es lo que se está midiendo en el estudio."
    ),
    review.KNOWLEDGE_GRAPH: "{n} preguntas sobre el temario que acabas de revisar.",
    review.EXEMPLARS_BANK: "{n} preguntas sobre los ejercicios que acabas de revisar.",
}

# Spelled out, because the preamble is prose and «5 preguntas» reads as a form field. Only
# the range an instrument can plausibly reach; anything outside it falls back to the digit
# rather than to nothing.
_SPELLED: dict[int, str] = {
    2: "Dos",
    3: "Tres",
    4: "Cuatro",
    5: "Cinco",
    6: "Seis",
    7: "Siete",
    8: "Ocho",
    9: "Nueve",
    10: "Diez",
}


def count(artifact: str) -> int:
    """How many questions this stage's form actually asks.

    `overall` is one of them: it is on the form, it is the last thing answered, and it is
    what «contestada» means — so a count that left it out would be short by one wherever
    a person is told how much is left.
    """
    return len(QUESTIONS.get(artifact, ())) + 1


def preamble(artifact: str) -> str:
    """The prose above the questions, with its own count filled in."""
    n = count(artifact)
    return PREAMBLE.get(artifact, "").replace("{n}", _SPELLED.get(n, str(n)))


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
        "preamble": preamble(artifact),
        # What the button that OPENS this form has to say, and it may not count for
        # itself: a constant in the browser is exactly what drifted from the instrument.
        "count": count(artifact),
        "questions": [dict(question) for question in QUESTIONS.get(artifact, ())],
        "overall": _OVERALL,
        "note": _NOTE,
    }

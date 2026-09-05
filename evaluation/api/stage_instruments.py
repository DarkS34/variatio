"""What a teacher is asked about each artifact, right after building it.

The blind comparison measures the variants. This measures the CHAIN that produces them,
which nothing did before: a workspace could be prepared end to end and leave no record of
whether its profile, its graph or its bank came out any good — so a poor comparison could
never be told apart from a poor instance underneath it.

A LIKERT SCALE, FIVE STATEMENTS PER STAGE, THE SAME FIVE AXES ON ALL THREE (2026-09-04,
explicit user request, over the five multiple-choice questions of 2026-09-03). Every item
is a STATEMENT the person agrees or disagrees with on one five-point scale — «totalmente
en desacuerdo» to «totalmente de acuerdo» — and the same scale is drawn once for the whole
form. What that buys over per-question options is a number on every axis that means the
same thing everywhere: a 4 on precision and a 4 on effort are the same amount of agreement,
so the memoria can average, compare across stages and compare across people without a
table that translates «alguno suelto» into a rank first. The axes are what a builder can
get wrong, and they are the same for any artifact that is a list the system extracted from
somebody's documents:

  1. `precision` — is what is here right? (nothing that should not be)
  2. `recall` — is everything that should be here present?
  3. `function` — does the artifact do what it exists for: the fields of a type, the
     order of the syllabus, the concept put on each exercise.
  4. `effort` — could it be used without correcting much; identical wording on all three.
  5. `overall` — «en conjunto, ha salido bien», the one column shared with the rest of
     the evaluation.

EVERY STATEMENT IS WORDED SO THAT AGREEING IS THE GOOD ANSWER. Reverse-scored items were
considered and left out: they guard against a person ticking the same column all the way
down, at the cost of a scale the analysis has to flip item by item, and on a form of five
statements read beside the artifact they describe the guard is not worth the trap. So the
value IS the score, 5 being best, and «lo usaría sin apenas corregir» is stated rather than
«tendría que rehacerlo». Precision and recall are still asked APART because they are
opposite conclusions about the extractor — over-generating and under-generating are fixed
in different places. The graph's order statement no longer offers «no lo he mirado»: the
middle of the scale is what somebody who has not looked leaves it on, and the hint says so.
The optional note is not a statement and is not counted.

Not one statement names an artifact, a model or a phase. The person answering has never
seen this tool and is being asked about their own subject: «tipos de ejercicio», «el
temario», «tus ejercicios». The vocabulary is the screen's, and it is the same one.

The wording lives here and not in the browser for the reason `instruments.py` says: it IS
the instrument and not a label, so rewording it changes what was measured. `VERSION` is
stored on every row precisely so that two wordings are never pooled by accident — bump it
whenever a statement, the scale or their ORDER changes, and never edit a wording in place
without doing so.
"""

from server import review

# Stored in `stage_evaluations.instrument`. Bump on ANY change to the statements below.
# «4» since 2026-09-04: the five questions became five Likert statements on one shared
# agreement scale, with the keys renamed to the axis they measure — so nothing under «3»
# (options such as «none» / «touch_up») is ever pooled with a 1-5 under «4». «3»
# (2026-09-03) cut the instrument to five questions per stage on the five axes; «2»
# (2026-09-02) reworded the bank's tagging question from «tema» to «concepto»; «1» was the
# original wording. Rows under «» are a pre-existing oddity of the save path, all dated
# 2026-09-02.
VERSION = "4"

# The one scale, for every statement and for `overall` alike. The index is the score — 1 is
# the worst rung and 5 the best — and the labels are the classic five, said once at the top
# of the form rather than beside every row.
SCALE_MIN = 1
SCALE_MAX = 5
SCALE_LABELS: tuple[str, ...] = (
    "Totalmente en desacuerdo",
    "En desacuerdo",
    "Ni de acuerdo ni en desacuerdo",
    "De acuerdo",
    "Totalmente de acuerdo",
)
SCALE_VALUES: tuple[int, ...] = tuple(range(SCALE_MIN, SCALE_MAX + 1))

# `overall` is a column of its own and the rest are JSON, so the two names survive for
# the readers that validate the column; they are the same scale.
OVERALL_MIN = SCALE_MIN
OVERALL_MAX = SCALE_MAX

# The rungs that count as agreement — «de acuerdo» and «totalmente de acuerdo» — which is
# the reading the panel gives beside the raw counts on `effort`: «lo usarían».
AGREE_FROM = 4

# The axis of each key, in the order asked. One key per axis on every stage, so the CSV
# has one column per axis and the analysis lays the three stages side by side with no
# table of its own.
AXES: dict[str, str] = {
    "precision": "precision",
    "recall": "recall",
    "function": "function",
    "effort": "effort",
}

# Asked of all three with the same words, and the first half of the comparable spine.
_EFFORT = {
    "key": "effort",
    "axis": "effort",
    "statement": "Lo podría usar tal cual, sin apenas corregir nada.",
}

# The second half: the one column shared with the rest of the evaluation, asked last.
_OVERALL = {
    "key": "overall",
    "axis": "overall",
    "statement": "En conjunto, ha salido bien.",
}

_NOTE = {
    "key": "note",
    "question": "¿Algo que quieras contar?",
    "hint": "Opcional. Lo que no cabe en la escala de arriba.",
}

QUESTIONS: dict[str, tuple[dict, ...]] = {
    review.EXEMPLARS_PROFILE: (
        # PRECISION. The consolidator has produced different type sets across runs on one
        # corpus and has split one modality in two, which is what «repetido con otro
        # nombre» is there to catch.
        {
            "key": "precision",
            "axis": "precision",
            "statement": "Todos los tipos de ejercicio que aparecen son tipos que pongo de verdad.",
            "hint": "Baja la nota si hay alguno que no pones, o el mismo tipo repetido con otro nombre.",
        },
        # RECALL. The hint separates a secondary omission from the main modality missing,
        # which is the difference between a profile usable with an addition and one that
        # missed the point of the course.
        {
            "key": "recall",
            "axis": "recall",
            "statement": "No falta ningún tipo de ejercicio de los que pongo.",
            "hint": "Que falte el principal pesa mucho más que que falte uno secundario.",
        },
        # FUNCTION. The fields are what every generated exercise is made of: a wrong part
        # here is a wrong part in every item written afterwards.
        {
            "key": "function",
            "axis": "function",
            "statement": "Las partes de cada tipo son las correctas.",
            "hint": "El enunciado, la solución, las pistas: ni sobra ni falta ninguna.",
        },
        _EFFORT,
    ),
    review.KNOWLEDGE_GRAPH: (
        # PRECISION, and wider than «not of my subject»: the extractor's measured failures
        # are an example exercise's terms pulled in as concepts, a concept twice under two
        # names, and a granularity no teacher would put on a syllabus.
        {
            "key": "precision",
            "axis": "precision",
            "statement": "Todos los conceptos que aparecen son de mi asignatura.",
            "hint": "Baja la nota si hay conceptos que no son tuyos, repetidos o demasiado concretos.",
        },
        # RECALL.
        {
            "key": "recall",
            "axis": "recall",
            "statement": "Está todo lo que enseño.",
            "hint": "Que falte un bloque entero pesa mucho más que que falte algo secundario.",
        },
        # FUNCTION. What the graph is FOR is deciding what may be assumed known and what
        # may not be leaned on, and that is a claim about the order rather than the list.
        # There is no «no lo he mirado» any more: the middle of the scale is where somebody
        # who has not looked leaves it, and the hint says so.
        {
            "key": "function",
            "axis": "function",
            "statement": "El orden —qué hace falta saber antes de qué— tiene sentido.",
            "hint": "Si no lo has mirado, déjalo en el punto medio.",
        },
        _EFFORT,
    ),
    review.EXEMPLARS_BANK: (
        # PRECISION, in the bank's own terms: an item cut in half and a paragraph of theory
        # taken for an exercise are the two ways something that should not be here got in.
        {
            "key": "precision",
            "axis": "precision",
            "statement": "Los ejercicios están bien recogidos de mis documentos.",
            "hint": "Completos, sin cortar a mitad, y sin que se cuele nada que no sea un ejercicio.",
        },
        # RECALL.
        {
            "key": "recall",
            "axis": "recall",
            "statement": "Están todos los ejercicios de mis documentos.",
            "hint": "Que falte un documento entero pesa mucho más que que falte alguno suelto.",
        },
        # FUNCTION. The step is called «Etiquetado»: this is the statement it is named after.
        {
            "key": "function",
            "axis": "function",
            "statement": "El concepto que se les ha puesto es el correcto.",
            "hint": "Piensa en cuántos lo llevan bien: casi todos, la mitad, casi ninguno.",
        },
        _EFFORT,
    ),
}

# What the screen puts above the statements: why it is worth a minute, and how to answer.
# Said once per artifact and not per statement, because a hint on every row is a form
# nobody finishes.
#
# THE NUMBER IS NOT WRITTEN HERE. It is `{n}`, filled by `count()` below, because a hand
# written figure drifts the moment a statement is added or dropped — and it had: the
# button that opens this form promised «cinco preguntas» for all three stages while the
# graph asked six, so the control contradicted the form it opened.
PREAMBLE: dict[str, str] = {
    review.EXEMPLARS_PROFILE: (
        "{n} afirmaciones sobre los tipos de ejercicio que acabas de revisar: di cuánto "
        "estás de acuerdo con cada una. Es lo único que te pedimos a cambio, y es lo que "
        "se está midiendo en el estudio."
    ),
    review.KNOWLEDGE_GRAPH: (
        "{n} afirmaciones sobre el temario que acabas de revisar: di cuánto estás de "
        "acuerdo con cada una."
    ),
    review.EXEMPLARS_BANK: (
        "{n} afirmaciones sobre los ejercicios que acabas de revisar: di cuánto estás de "
        "acuerdo con cada una."
    ),
}

# Spelled out, because the preamble is prose and «5 afirmaciones» reads as a form field.
# Only the range an instrument can plausibly reach; anything outside it falls back to the
# digit rather than to nothing.
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
    """How many statements this stage's form actually asks.

    `overall` is one of them: it is on the form, it is the last thing answered, and it is
    what «contestada» means — so a count that left it out would be short by one wherever
    a person is told how much is left.
    """
    return len(QUESTIONS.get(artifact, ())) + 1


def preamble(artifact: str) -> str:
    """The prose above the statements, with its own count filled in."""
    n = count(artifact)
    return PREAMBLE.get(artifact, "").replace("{n}", _SPELLED.get(n, str(n)))


def scale_values(artifact: str, key: str) -> tuple[int, ...]:
    """The accepted values of one statement — the whole scale — or `()` when nothing declares it."""
    for question in QUESTIONS.get(artifact, ()):
        if question["key"] == key:
            return SCALE_VALUES
    return ()


def as_score(value) -> int | None:
    """Read one answer as a rung of the scale, or None when it is not one.

    The browser sends an integer, but a JSON round trip or an older bundle may hand over
    the digit as a string, and `True` must not pass for 1: only an int or a digit string
    inside the scale is a score.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, int) and SCALE_MIN <= value <= SCALE_MAX:
        return value
    return None


def clean(artifact: str, answers: dict) -> dict:
    """Keep only what this artifact actually asks, with a value on the scale it offers.

    An answer arrives in a request, so it is checked against what is declared here rather
    than stored as it came — the same rule a raw document's filename gets. Silently
    dropping an unknown key is right and a 422 would be wrong: the browser may be a build
    behind after a rewording, and refusing the whole form would lose the four answers that
    are still good.
    """
    kept = {}
    for question in QUESTIONS.get(artifact, ()):
        key = question["key"]
        score = as_score(answers.get(key))
        if score is not None:
            kept[key] = score
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
        # Drawn once, over every statement: the same five rungs for all of them.
        "scale": {"min": SCALE_MIN, "max": SCALE_MAX, "labels": list(SCALE_LABELS)},
        "questions": [dict(question) for question in QUESTIONS.get(artifact, ())],
        "overall": dict(_OVERALL),
        "note": _NOTE,
    }

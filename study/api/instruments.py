"""What the evaluator is asked, and how the wording changes with who is asking it.

Two instruments, and the order between them is the design. The **triage** is one question
per card, answered BEFORE the reveal, and it is what gives the study a quality signal for
all three architectures rather than for the one whose name was already known. The
**rubric** is four scales about the system's variant, answered after the reveal and
deliberately optional, so a person in a hurry still leaves a complete datum.

A teacher and a student are NOT asked the same thing — «¿La pondrías en clase?» is a
question about teaching, and asking it of somebody who does not teach produces an answer,
which is worse than producing none. What the two share is the SHAPE, three ordered options
best first, so the arithmetic downstream stays one function.

The wording lives here rather than in the browser because it IS the instrument and not a
label: rewording it changes what was measured, so it has to be one edit in one file, which
the API then serves.
"""

from server.db.models import STUDENT, TEACHER

# Ordinal and best first, which is what lets `store` score them without a per-profile table.
# Neutral keys on purpose: `as_is` would be a lie in a student's row, and a CSV column whose
# meaning depends on another column is a CSV nobody can read six months later.
TRIAGE_VALUES: tuple[str, ...] = ("yes", "partly", "no")

TRIAGE: dict[str, dict] = {
    TEACHER: {
        "question": "¿La pondrías en clase?",
        "hint": "Sin pensarlo mucho: es la primera impresión, no una nota.",
        "options": [
            {"value": "yes", "label": "Tal cual"},
            {"value": "partly", "label": "Con retoques"},
            {"value": "no", "label": "No"},
        ],
    },
    STUDENT: {
        "question": "¿Te serviría para practicar?",
        "hint": "Sin pensarlo mucho: es la primera impresión, no una nota.",
        "options": [
            {"value": "yes", "label": "Sí, mucho"},
            {"value": "partly", "label": "A medias"},
            {"value": "no", "label": "No"},
        ],
    },
}

# The keys never change: renaming one strands every session already judged. What varies per
# profile is only the prose.
RATING_SCALES: tuple[str, ...] = ("originality", "complexity", "concept_fit", "soundness")

# `complexity` is the one scale whose best answer is the middle. Carried as data so the
# person doing the scoring can read the rule, rather than only the arithmetic downstream.
RATING_TARGET: dict[str, int] = {"complexity": 3}

_TEACHER_RUBRIC = {
    "originality": {
        "label": "Originalidad",
        "question": "¿El escenario es original, o es el típico de libro de texto?",
        "ends": ["de libro de texto", "muy original"],
    },
    "complexity": {
        "label": "Exigencia",
        "question": "¿La exigencia encaja con el nivel del curso?",
        "ends": ["trivial", "desbordado"],
    },
    "concept_fit": {
        "label": "Ajuste al concepto",
        "question": "¿Practica de verdad los conceptos pedidos, o solo los menciona?",
        "ends": ["solo los menciona", "los practica"],
    },
    "soundness": {
        "label": "Buen planteamiento",
        "question": "¿Está bien planteado: autosuficiente, sin ambigüedad y resoluble?",
        "ends": ["flojo", "impecable"],
    },
}

# The same four scales, asked from the desk instead of the front of the room. Two of them a
# student judges BETTER: whether the demand is right for where they actually are, and
# whether the statement holds up once you sit down to solve it.
_STUDENT_RUBRIC = {
    "originality": {
        "label": "Originalidad",
        "question": "¿Habías visto ya un ejercicio así, o te sorprende?",
        "ends": ["visto mil veces", "me sorprende"],
    },
    "complexity": {
        "label": "Dificultad",
        "question": "¿Está a tu nivel ahora mismo?",
        "ends": ["se me queda corto", "no sabría ni empezar"],
    },
    "concept_fit": {
        "label": "Ajuste al tema",
        "question": "¿Va de lo que dice ir, o se va por las ramas?",
        "ends": ["se va por las ramas", "va justo a eso"],
    },
    "soundness": {
        "label": "Buen planteamiento",
        "question": "¿Se entiende qué hay que hacer, sin partes ambiguas ni datos que falten?",
        "ends": ["confuso", "clarísimo"],
    },
}

RUBRIC: dict[str, dict] = {TEACHER: _TEACHER_RUBRIC, STUDENT: _STUDENT_RUBRIC}

# The third way a session can end, and the one that is not a judgement. Worded about the
# SUBJECT and not about the person, which also keeps it gender-neutral: the installation
# has no way of knowing, and what the study wants is the match between this panel and these
# three items.
DECLINE_LABEL = "No tengo criterio para juzgar esto"
DECLINE_HINT = "Queda registrado que la saltaste; no cuenta como preferencia."


def resolve(profile: str | None) -> str:
    """Return the profile whose wording to use, defaulting an unset one to the teacher's.

    Every account of an installation older than the question is NULL, and the study's panel
    reports that per account so it can be corrected — what it must not do is refuse to draw
    the screen because a column is empty.
    """
    return profile if profile in TRIAGE else TEACHER


def for_profile(profile: str | None) -> dict:
    """Everything the evaluation screen needs in order to word itself, in one payload."""
    resolved = resolve(profile)
    return {
        "profile": resolved,
        "triage": TRIAGE[resolved],
        "rubric": [
            {"key": key, **RUBRIC[resolved][key], "target": RATING_TARGET.get(key)}
            for key in RATING_SCALES
        ],
        "decline": {"label": DECLINE_LABEL, "hint": DECLINE_HINT},
    }

"""What the evaluator is asked, and how the wording changes with who is asking it.

Two instruments, and the order between them is the design:

1. The **triage** — one question per card, answered BEFORE the reveal. It is what turns
   the comparison into per-arm data: today the only scored thing in a session is the
   system's own variant, scored by somebody who already knows it is the system's, which
   can neither be compared between architectures nor called blind.
2. The **rubric** — four scales about the system's variant, answered after the reveal and
   deliberately optional. Everything blind is collected before the reveal, so a person in a
   hurry still leaves a complete datum and the reveal reads as what it is: the reward for
   finishing, not a gate in front of more work.

A teacher and a student are NOT asked the same thing. «¿La pondrías en clase?» is a
question about teaching and a student does not teach; asking it anyway produces an answer,
which is worse than producing none. What the two share is the SHAPE — three ordered
options, best first — so the arithmetic downstream stays one function and the difference
lives where it belongs, in the words.

The wording lives here rather than in the browser because it is the instrument and not a
label: rewording it changes what was measured, and that must be one edit in one file, which
the API then serves. `ARM_LABELS` set the precedent.
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

# The four scales, unchanged as keys since the study started recording them: renaming one
# would strand every session already judged. What varies per profile is only the prose.
RATING_SCALES: tuple[str, ...] = ("originality", "complexity", "concept_fit", "soundness")

# `complexity` is the one whose best answer is the middle. It is carried as data rather than
# hard-coded in the browser because the rule «el objetivo es 3» used to live only in a
# comment next to the arithmetic, where the person doing the scoring could not read it.
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

# Same four scales, asked from the desk instead of the front of the room. Two of them a
# student judges BETTER than a teacher does — whether the demand is right for where they
# actually are, and whether the statement holds up once you sit down to solve it, which is
# the moment an ambiguity stops being hypothetical.
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

# Every session ends in one of three ways, and the third is not a judgement. «No me veo
# capacitado» is the answer of somebody the panel put in front of a subject they do not
# teach — which, with evaluators drawn from different subjects, is a real state and not an
# escape hatch. Recording it beats the alternative, which is a shrug entered as a preference.
#
# Worded as a statement about the SUBJECT and not about the person: «no me veo capacitado»
# says something about them (and says it in the masculine, which the installation has no
# way of knowing), while «no tengo criterio sobre esto» says something about the match
# between this panel and these three items — which is the fact the study actually wants.
DECLINE_LABEL = "No tengo criterio para juzgar esto"
DECLINE_HINT = "Queda registrado que la saltaste; no cuenta como preferencia."


# NULL is a teacher's wording. An installation that predates the profile has every account
# unset, and the study's own panel says so per account so it can be corrected — what it must
# not do is refuse to draw the screen because a column is empty.
def resolve(profile: str | None) -> str:
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

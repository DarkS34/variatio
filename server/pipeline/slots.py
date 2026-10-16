"""The two raw slots of a workspace: what each holds, what it feeds, and the job that reads it.

The chain reads them — a build waits for a live transcription of the slot it reads
(`gates.py`, `readings.py`) — and so does step 1, which lists, writes and transcribes their
documents (`server/raw/documents.py`). `approvals.RAW_SOURCE` stays the one table of which
slot feeds which artifact.
"""

from . import approvals

CORPUS = "corpus"
EXEMPLARS = "exemplars"

SLOTS: dict[str, dict] = {
    CORPUS: {
        "kind": CORPUS,
        "label": "Corpus del dominio",
        "purpose": (
            "Los apuntes y el material teórico de la asignatura. De aquí se extrae el "
            "grafo de conocimiento: conceptos, dominios y relaciones."
        ),
        "feeds": [a for a, s in approvals.RAW_SOURCE.items() if s == CORPUS],
    },
    EXEMPLARS: {
        "kind": EXEMPLARS,
        "label": "Ejemplares en bruto",
        "purpose": (
            "Ejercicios, exámenes o prácticas ya resueltos. De aquí se infiere el perfil "
            "de contenido y se extrae el banco de ejemplos."
        ),
        "feeds": [a for a, s in approvals.RAW_SOURCE.items() if s == EXEMPLARS],
    },
}

TRANSCRIBE_JOB = "transcribe"


def slot_feeding(artifact: str | None) -> str | None:
    """Name the raw slot an artifact is built from, or `None` for one built from no slot."""
    return approvals.RAW_SOURCE.get(artifact) if artifact else None

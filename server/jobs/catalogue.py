"""What a job and an event are, and the three tables that classify a job kind.

Deliberately not called `models`: under `server/` that already means the ML model
(`model_pulls.py`, `required_models`) and the ORM row (`db/models.py`).
"""

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Literal

JobKind = Literal[
    "build_profile",
    "build_kg",
    "build_bank",
    "transcribe",
    "describe_concepts",
    "index",
    "tag",
    "review_taggability",
    "generate",
    "evaluate",
]

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]

JOB_LABELS: dict[str, str] = {
    "build_profile": "Construir el perfil de ejemplares",
    "build_kg": "Construir el grafo de conocimiento",
    "build_bank": "Extraer el banco de ejemplos",
    "transcribe": "Transcribir los documentos",
    "describe_concepts": "Generar descripciones de conceptos",
    "index": "Indexar conceptos y banco",
    "tag": "Etiquetar el banco",
    "review_taggability": "Revisar la etiquetabilidad",
    "generate": "Generar ítems",
    "evaluate": "Evaluación comparativa",
}

# A build runs out of process: it lasts hours and needs a cancel that really stops it, and
# Python cannot kill a thread. Everything else yields often enough to cancel cooperatively.
SUBPROCESS_KINDS: frozenset[str] = frozenset({"build_profile", "build_kg", "build_bank"})

# Artifact each job kind produces, which is what puts a stage into the «building» state.
# `review_taggability` is absent on purpose: it patches the graph's non-taggable list in
# place, and marking the graph as building would hide the screen — the button that launched
# the review included.
JOB_ARTIFACT: dict[str, str] = {
    "build_profile": "exemplars_profile",
    "build_kg": "knowledge_graph",
    "build_bank": "exemplars_bank",
    "tag": "exemplars_bank",
}


@dataclass
class Job:
    """One unit of work in the queue, with the workspace and the person it belongs to.

    Several jobs run side by side and they belong to different instances and different
    people, so `workspace` is what every handler resolves its paths from and `user_id` is
    what attributes the variants a run produces.

    `backends` and `queue_position` are the runner's: stamped at submission, restamped
    whenever the queue moves, and carried by every event through `to_dict()`.
    """

    kind: str
    params: dict = field(default_factory=dict)
    workspace: str = ""
    user_id: int | None = None
    user_name: str | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    result: dict | None = None
    backends: list[str] = field(default_factory=list)
    queue_position: int = 0

    @property
    def label(self) -> str:
        """The label this kind of job is known by, falling back to the kind itself."""
        return JOB_LABELS.get(self.kind, self.kind)

    @property
    def artifact(self) -> str | None:
        """The artifact this job rewrites, or `None` when it writes none."""
        return JOB_ARTIFACT.get(self.kind)

    def to_dict(self) -> dict:
        """Serialise for the event stream, with the two derived fields and the elapsed time."""
        data = asdict(self)
        data["label"] = self.label
        data["artifact"] = self.artifact
        data["elapsed_ms"] = round(
            ((self.finished_at or time.time()) - self.started_at) * 1000
        ) if self.started_at else None
        return data


@dataclass
class Event:
    """One line of the run stream, stamped with the workspace the socket filters on.

    The stamp is the bus's, never the subscriber's: it is what a browser cannot choose for
    itself, and therefore what keeps one instance's tokens out of another's screen.
    """

    seq: int
    ts: float
    job_id: str | None
    kind: str
    payload: dict
    workspace: str | None = None

    def to_dict(self) -> dict:
        """Flatten to the shape the socket sends, the payload spread over the envelope."""
        return {
            "seq": self.seq,
            "ts": self.ts,
            "job_id": self.job_id,
            "kind": self.kind,
            **self.payload,
        }

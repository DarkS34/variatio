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

# `build` runs out of process: a multi-hour job needs a cancel button that really
# stops it, and Python cannot kill a thread. Everything else yields often enough
# (between items, between stream tokens) for cooperative cancellation to be instant.
SUBPROCESS_KINDS: frozenset[str] = frozenset({"build_profile", "build_kg", "build_bank"})

# Artifact each job kind produces, for the "building" state of the chain. A taggability
# review is deliberately absent: it patches the graph's non-taggable list in place and
# leaves everything else untouched, so it must not put the knowledge graph into the
# "building" state — that would hide the whole screen behind rebuild copy that does not
# apply and would hide the very button that launched it.
JOB_ARTIFACT: dict[str, str] = {
    "build_profile": "exemplars_profile",
    "build_kg": "knowledge_graph",
    "build_bank": "exemplars_bank",
    "tag": "exemplars_bank",
}


# The queue serialises per backend rather than one job at a time, so several of these can
# be running side by side and they belong to different instances and different people.
# `workspace` is what every handler resolves its paths from — a handler that read a
# process-wide workspace would write one user's build into another's directory — and
# `user_id` is what attributes the variants a run produces.
#
# `backends` and `queue_position` are the runner's, written into the job so that every
# event carrying `to_dict()` says which lanes this job holds and how many jobs are still
# in front of it. Both are stamped at submission and restamped whenever the queue moves.
@dataclass
class Job:
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
        return JOB_LABELS.get(self.kind, self.kind)

    @property
    def artifact(self) -> str | None:
        return JOB_ARTIFACT.get(self.kind)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["label"] = self.label
        data["artifact"] = self.artifact
        data["elapsed_ms"] = round(
            ((self.finished_at or time.time()) - self.started_at) * 1000
        ) if self.started_at else None
        return data


@dataclass
class Event:
    seq: int
    ts: float
    job_id: str | None
    kind: str
    payload: dict
    # Who the event belongs to. One process serves one workspace today, so the bus stamps
    # it rather than every publisher passing it; what matters is that the socket has
    # something to filter on that the browser cannot choose for itself.
    workspace: str | None = None

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "job_id": self.job_id,
            "kind": self.kind,
            **self.payload,
        }

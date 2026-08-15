import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Literal

JobKind = Literal[
    "build_profile",
    "build_kg",
    "build_bank",
    "describe_concepts",
    "index",
    "tag",
    "generate",
    "evaluate",
]

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]

JOB_LABELS: dict[str, str] = {
    "build_profile": "Construir el perfil de ejemplares",
    "build_kg": "Construir el grafo de conocimiento",
    "build_bank": "Extraer el banco de ejemplos",
    "describe_concepts": "Generar descripciones de conceptos",
    "index": "Indexar conceptos y banco",
    "tag": "Etiquetar el banco",
    "generate": "Generar ítems",
    "evaluate": "Evaluación comparativa",
}

# `build` runs out of process: a multi-hour job needs a cancel button that really
# stops it, and Python cannot kill a thread. Everything else yields often enough
# (between items, between stream tokens) for cooperative cancellation to be instant.
SUBPROCESS_KINDS: frozenset[str] = frozenset({"build_profile", "build_kg", "build_bank"})

# Artifact each job kind produces, for the "building" state of the chain.
JOB_ARTIFACT: dict[str, str] = {
    "build_profile": "exemplars_profile",
    "build_kg": "knowledge_graph",
    "build_bank": "exemplars_bank",
    "tag": "exemplars_bank",
}


@dataclass
class Job:
    kind: str
    params: dict = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    result: dict | None = None

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

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "job_id": self.job_id,
            "kind": self.kind,
            **self.payload,
        }

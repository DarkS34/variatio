"""The three generation architectures under comparison, behind one contract.

`naive` (a commercial model with an average user's prompt), `rag` (a flat vector index
over the bank, no graph at all) and `system` (this pipeline, untouched). They receive the
same commission and return the same shape, so a fourth arm is one more file.

This package is not part of the system it measures, and its position says so: `study`
imports `variant_generator`, never the reverse, and nothing under `variant_generator/`
names the study at all. The evaluation observes the pipeline from outside it.
"""

from dataclasses import dataclass, field
from pathlib import Path

ARMS: tuple[str, ...] = ("naive", "rag", "system")

ARM_LABELS: dict[str, str] = {
    "naive": "Modelo comercial",
    "rag": "Solo RAG sobre el banco",
    "system": "Este sistema",
}

def rag_index_path(ws) -> Path:
    """Where the rag arm's flat index over the bank is cached, inside the workspace."""
    return ws.cache_dir / "embeddings" / "eval_rag_bank.npz"


OK = "ok"
FAILED = "failed"
UNAVAILABLE = "unavailable"


class ArmUnavailable(RuntimeError):
    """The arm could not even be attempted (no API key, provider down, quota spent)."""


@dataclass(frozen=True)
class Commission:
    """What the evaluator asked for. Identical for the three arms, by construction.

    `think` is the one field the evaluator does NOT get to set: the session draws it at
    random from its own seed, so across enough sessions the reasoning mode is a measured
    condition instead of a habit. It is identical for the three arms within a session,
    which is what keeps it out of the comparison between them.
    """

    concepts: list[str]
    item_type: str
    fixed: dict[str, object] = field(default_factory=dict)
    curriculum: list[str] = field(default_factory=list)
    instructions: str = ""
    think: bool = True
    # The scope ruling, screened ONCE for the session and carried here so the `system` arm
    # reuses it instead of paying the judge a second time. Untyped on purpose: naming
    # `admissibility.Ruling` would put a pipeline type in the study's own contract.
    ruling: object | None = None


@dataclass
class ArmResult:
    arm: str
    status: str
    item: dict | None
    raw_response: str
    prompt: str
    model: str
    provider: str
    exemplar_ids: list[str]
    elapsed_ms: int
    error: str | None = None
    checks: dict | None = None
    retried: int = 0

    def to_dict(self) -> dict:
        return {
            "arm": self.arm,
            "status": self.status,
            "item": self.item,
            "raw_response": self.raw_response,
            "prompt": self.prompt,
            "model": self.model,
            "provider": self.provider,
            "exemplar_ids": list(self.exemplar_ids),
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
            "checks": self.checks,
            "retried": self.retried,
        }


@dataclass
class EvaluationSession:
    """One comparison: the statistical unit of the study.

    `shuffle` is the arm shown at each position, so the reveal is a lookup and the
    blinding is auditable after the fact from `seed` alone. `think` comes out of that same
    seed and is recorded next to it because it is the second condition of the experiment:
    whether the local arms reasoned before answering.
    """

    id: str
    created_at: float
    concepts: list[str]
    item_type: str
    fixed: dict[str, object]
    curriculum: list[str]
    instructions: str
    seed: int
    shuffle: list[str]
    arms: dict[str, ArmResult]
    think: bool = True
    job_id: str | None = None
    # Which three items these are, and who handed them over. A session generated on its own
    # is its own set; a copy an administrator assigned carries the source's, which is the
    # only way two people's judgements of the same exercises can ever be compared.
    set_id: str | None = None
    assigned_by: int | None = None
    # One answer per POSITION, given blind, before anything is revealed.
    triage: dict[str, str] = field(default_factory=dict)
    choice: int | None = None
    choice_arm: str | None = None
    chosen_at: float | None = None
    opened_at: float | None = None
    declined_at: float | None = None
    evaluator_note: str | None = None
    rating: dict | None = None

    # Two different questions, and collapsing them is what would corrupt the counts.
    # `decided` is «hay una preferencia registrada» and is what every per-arm number is
    # computed over; `finished` is «esta sesión ya no admite juicio», which a decline also
    # satisfies without ever having expressed a preference.
    @property
    def decided(self) -> bool:
        return self.chosen_at is not None

    @property
    def declined(self) -> bool:
        return self.declined_at is not None

    @property
    def finished(self) -> bool:
        return self.decided or self.declined

    def arm_at(self, position: int) -> str:
        return self.shuffle[position - 1]

    def position_of(self, arm: str) -> int:
        return self.shuffle.index(arm) + 1

    # What the evaluator answered, re-keyed by architecture. Derived and never stored: the
    # stored form is by position, because that is what they actually saw.
    def triage_by_arm(self) -> dict[str, str]:
        return {
            self.arm_at(int(position)): value
            for position, value in self.triage.items()
            if 1 <= int(position) <= len(self.shuffle)
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "job_id": self.job_id,
            "set_id": self.set_id or self.id,
            "assigned_by": self.assigned_by,
            "concepts": list(self.concepts),
            "item_type": self.item_type,
            "fixed": dict(self.fixed),
            "curriculum": list(self.curriculum),
            "instructions": self.instructions,
            "seed": self.seed,
            "shuffle": list(self.shuffle),
            "think": self.think,
            "arms": {name: result.to_dict() for name, result in self.arms.items()},
            "triage": dict(self.triage),
            "choice": self.choice,
            "choice_arm": self.choice_arm,
            "chosen_at": self.chosen_at,
            "opened_at": self.opened_at,
            "declined_at": self.declined_at,
            "evaluator_note": self.evaluator_note,
            "rating": self.rating,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationSession":
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            concepts=list(data.get("concepts") or []),
            item_type=data.get("item_type") or "",
            fixed=dict(data.get("fixed") or {}),
            curriculum=list(data.get("curriculum") or []),
            instructions=data.get("instructions") or "",
            seed=int(data.get("seed") or 0),
            shuffle=list(data.get("shuffle") or []),
            # Sessions recorded before the reasoning became a condition all ran with it on.
            think=bool(data.get("think", True)),
            arms={
                name: ArmResult(**payload) for name, payload in (data.get("arms") or {}).items()
            },
            job_id=data.get("job_id"),
            # A session recorded before sets existed is its own: nobody had been handed a
            # copy of anybody else's, because there was no way to hand one over.
            set_id=data.get("set_id") or data["id"],
            assigned_by=data.get("assigned_by"),
            triage=dict(data.get("triage") or {}),
            choice=data.get("choice"),
            choice_arm=data.get("choice_arm"),
            chosen_at=data.get("chosen_at"),
            opened_at=data.get("opened_at"),
            declined_at=data.get("declined_at"),
            evaluator_note=data.get("evaluator_note"),
            rating=data.get("rating"),
        )


def run_arm(arm: str, commission: Commission, context) -> ArmResult:
    from .arms import naive, rag, system

    runners = {"naive": naive.run, "rag": rag.run, "system": system.run}
    if arm not in runners:
        raise ValueError(f"Unknown evaluation arm '{arm}'; expected one of {list(runners)}")
    return runners[arm](commission, context)


__all__ = [
    "ARMS",
    "ARM_LABELS",
    "ArmResult",
    "ArmUnavailable",
    "Commission",
    "EvaluationSession",
    "FAILED",
    "OK",
    "UNAVAILABLE",
    "rag_index_path",
    "run_arm",
]

"""The three generation architectures under comparison, behind one contract.

`naive` (a commercial model with an average user's prompt), `rag` (a flat vector index
over the bank, no graph at all) and `system` (this pipeline, untouched). They receive the
same commission and return the same shape, so a fourth arm is one more file.

Nothing in the pipeline imports this package: the evaluation observes the system, it is
not part of it.
"""

from dataclasses import dataclass, field

ARMS: tuple[str, ...] = ("naive", "rag", "system")

ARM_LABELS: dict[str, str] = {
    "naive": "Modelo comercial",
    "rag": "Solo RAG sobre el banco",
    "system": "Este sistema",
}

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
    choice: int | None = None
    choice_arm: str | None = None
    chosen_at: float | None = None
    evaluator_note: str | None = None
    rating: dict | None = None

    @property
    def decided(self) -> bool:
        return self.chosen_at is not None

    def arm_at(self, position: int) -> str:
        return self.shuffle[position - 1]

    def position_of(self, arm: str) -> int:
        return self.shuffle.index(arm) + 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "job_id": self.job_id,
            "concepts": list(self.concepts),
            "item_type": self.item_type,
            "fixed": dict(self.fixed),
            "curriculum": list(self.curriculum),
            "instructions": self.instructions,
            "seed": self.seed,
            "shuffle": list(self.shuffle),
            "think": self.think,
            "arms": {name: result.to_dict() for name, result in self.arms.items()},
            "choice": self.choice,
            "choice_arm": self.choice_arm,
            "chosen_at": self.chosen_at,
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
            choice=data.get("choice"),
            choice_arm=data.get("choice_arm"),
            chosen_at=data.get("chosen_at"),
            evaluator_note=data.get("evaluator_note"),
            rating=data.get("rating"),
        )


def run_arm(arm: str, commission: Commission, context) -> ArmResult:
    from . import naive, rag, system

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
    "run_arm",
]

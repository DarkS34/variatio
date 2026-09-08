"""The three generation architectures under comparison, behind one contract.

`naive` (a commercial model with an average user's prompt), `rag` (a flat vector index
over the raw documents read with a plain extractor, no graph, no bank) and `system` (this
pipeline, untouched). They receive the same commission and return the same shape, so a
fourth arm is one more file.

A SESSION IS TWO OF THEM, since 2026-09-08: the system's proposal is always one card, and
the other is ONE rival drawn from `RIVALS` by the session's seed. Three cards asked the
evaluator to rank a field; two ask the question the evaluation exists to answer — does the
system beat this alternative — and the answer is a coin that either way falls on a rival
whose identity the seed records. Sessions recorded before that date hold three arms, and
everything below reads the session's own `shuffle` for how many cards it has.

The boundary is the point, and `tests/evaluation/test_evaluation_boundary.py` pins both halves of
it: `evaluation` imports `variatio` and never the reverse, and this module never imports
`evaluation.api`, which is what keeps `import evaluation` free of FastAPI and SQLAlchemy for a
runtime-only consumer.
"""

import random
from dataclasses import dataclass, field
from pathlib import Path

ARMS: tuple[str, ...] = ("naive", "rag", "system")

SYSTEM = "system"

# The two alternatives the system is compared against, one per session. Their order is the
# palette's and the CSV's, never a preference: which one a session gets is the seed's.
RIVALS: tuple[str, ...] = ("naive", "rag")

ARM_LABELS: dict[str, str] = {
    "naive": "Modelo comercial",
    "rag": "Solo RAG sobre los documentos",
    "system": "Este sistema",
}

def draw_session(seed: int) -> tuple[list[str], bool]:
    """Draw everything a session decides before it runs: its two arms in order, and `think`.

    ONE generator over the seed, consumed in a fixed sequence — the rival, the order, the
    reasoning mode — so the whole session is reproducible from that number alone and the
    job can ask what a seed will need (the rag index, say) before anything is generated.
    The rival is a coin over `RIVALS`, the order a coin over the pair: over enough sessions
    each rival meets the system as often as the other and sits on the left as often as on
    the right, which is what makes the position and the rival measurable conditions rather
    than habits.
    """
    draw = random.Random(int(seed))
    order = [SYSTEM, draw.choice(RIVALS)]
    draw.shuffle(order)
    think = draw.random() < 0.5
    return order, think


def rag_index_path(ws, slot: str) -> Path:
    """Where the rag arm's flat index over one raw slot is cached, inside the workspace.

    Under `embeddings/` so the panel's "vaciar la caché" takes it with the pipeline's own;
    the plain readings it is built from live under `rag_text/` and stay, being seconds.
    """
    return ws.cache_dir / "embeddings" / f"eval_rag_{slot}.npz"


OK = "ok"
FAILED = "failed"
UNAVAILABLE = "unavailable"


class ArmUnavailable(RuntimeError):
    """The arm could not even be attempted (no API key, provider down, quota spent)."""


@dataclass(frozen=True)
class Commission:
    """What the evaluator asked for. Identical for the arms of a session, by construction.

    `think` is the one field the evaluator does NOT get to set: the session draws it at
    random from its own seed, so across enough sessions the reasoning mode is a measured
    condition instead of a habit. It is identical for the three arms within a session,
    which is what keeps it out of the comparison between them.

    `ruling` is the scope verdict, screened ONCE for the session so the `system` arm reuses
    it instead of paying the judge a second time. Untyped on purpose: naming
    `admissibility.Ruling` would put a pipeline type in the evaluation's own contract.

    `model` is the writer of the TWO LOCAL arms — the installation's own setting
    (`evaluation.local_model`, resolved by `run.evaluate` through `evaluation.config`), never
    the evaluator's choice. It is one model for both, which is what keeps the comparison
    about architectures; the commercial arm keeps its own chain. `effort` is what those two
    arms pass as `think`: the drawn boolean, or the level the installation declared when
    that model's effort is locked (`entrypoints.resolve_generation_effort`). The boolean stays
    the recorded condition; the level is the installation's.
    """

    concepts: list[str]
    item_type: str
    fixed: dict[str, object] = field(default_factory=dict)
    curriculum: list[str] = field(default_factory=list)
    instructions: str = ""
    think: bool = True
    ruling: object | None = None
    model: str = ""
    effort: bool | str = True


@dataclass
class ArmResult:
    """What one architecture produced, and what it cost, in the shape all three share.

    `tagging` is the graph's reading of the proposal, run over the session's arms alike once they
    are all in: `concepts`, the `primary` one it practises, `rule` and `off_limits` —
    whatever it brought in from the set the commission put out of bounds. Under the
    `mentions` rule (a curriculum was given) that is whether the tagger says the exercise
    is ABOUT it or the text merely NAMES it; under `practises` (no curriculum) only the
    primary concept can be there. A record without `rule` was written under `mentions`.
    It is `None` on a record written before the pass existed and on an arm that produced
    no item.
    """

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
    tagging: dict | None = None

    def to_dict(self) -> dict:
        """Render the result as the JSON the session's trace stores."""
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
            "tagging": self.tagging,
        }


@dataclass
class EvaluationSession:
    """One comparison: the statistical unit of the evaluation.

    `shuffle` is the arm shown at each position — and, since the session became two cards,
    also WHICH arms the session holds: `system` and one rival for anything recorded from
    2026-09-08, the three for anything before. So the reveal is a lookup, the blinding is
    auditable after the fact from `seed` alone, and `cards` is the one reading of how many
    positions there are. `think` comes out of that same seed and is recorded next to it
    because it is the second condition of the experiment: whether the local arms reasoned
    before answering.

    `set_id` groups the sessions holding the same items and `assigned_by` says who
    handed them over, which is the only way two people's judgements of one set of exercises
    can be compared. `triage` is stored BY POSITION, because that is what the evaluator
    actually saw; `triage_by_arm` re-keys it from `shuffle` at read time.
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
    set_id: str | None = None
    assigned_by: int | None = None
    triage: dict[str, str] = field(default_factory=dict)
    choice: int | None = None
    choice_arm: str | None = None
    chosen_at: float | None = None
    opened_at: float | None = None
    declined_at: float | None = None
    evaluator_note: str | None = None
    rating: dict | None = None

    @property
    def cards(self) -> int:
        """Return how many positions this session shows, which is what `shuffle` lists."""
        return len(self.shuffle)

    @property
    def rival(self) -> str | None:
        """Return the one arm the system was compared against, or None on a three-card session.

        A three-way session has two rivals and no duel; the pairwise arithmetic in
        `api.store` excludes it on this reading, and the CSV leaves the column blank.
        """
        others = [arm for arm in self.shuffle if arm != SYSTEM]
        return others[0] if len(others) == 1 and SYSTEM in self.shuffle else None

    @property
    def decided(self) -> bool:
        """Say whether a preference was registered, which every per-arm number counts over."""
        return self.chosen_at is not None

    @property
    def declined(self) -> bool:
        """Say whether the evaluator declared themselves unable to judge these items."""
        return self.declined_at is not None

    @property
    def finished(self) -> bool:
        """Say whether the session still admits a judgement.

        Deliberately not the same question as `decided`: a decline ends the session without
        ever expressing a preference, and collapsing the two corrupts the counts.
        """
        return self.decided or self.declined

    def arm_at(self, position: int) -> str:
        """Return which architecture was shown at this 1-based position."""
        return self.shuffle[position - 1]

    def position_of(self, arm: str) -> int:
        """Return the 1-based position this architecture was shown at."""
        return self.shuffle.index(arm) + 1

    def triage_by_arm(self) -> dict[str, str]:
        """Re-key the blind per-card answers by architecture, from `shuffle`.

        Derived and never stored: the stored form is by position, because that is what the
        evaluator actually saw.
        """
        return {
            self.arm_at(int(position)): value
            for position, value in self.triage.items()
            if 1 <= int(position) <= len(self.shuffle)
        }

    def to_dict(self) -> dict:
        """Render the whole session as the JSON stored in the row's `trace`."""
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
        """Rebuild a session from its stored trace, defaulting what older records lack."""
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
            # A record with no `think` predates the condition and ran with reasoning on.
            think=bool(data.get("think", True)),
            arms={
                name: ArmResult(**payload) for name, payload in (data.get("arms") or {}).items()
            },
            job_id=data.get("job_id"),
            # A session nobody was handed a copy of is its own set.
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
    """Run one architecture over the commission, raising ValueError for an unknown arm.

    The arms are imported inside the call because each of them imports this module back
    for the contract above.
    """
    from .arms import naive, rag, system

    runners = {"naive": naive.run, "rag": rag.run, "system": system.run}
    if arm not in runners:
        raise ValueError(f"Unknown evaluation arm '{arm}'; expected one of {list(runners)}")
    return runners[arm](commission, context)


__all__ = [
    "ARMS",
    "ARM_LABELS",
    "RIVALS",
    "SYSTEM",
    "ArmResult",
    "ArmUnavailable",
    "Commission",
    "EvaluationSession",
    "FAILED",
    "OK",
    "UNAVAILABLE",
    "draw_session",
    "rag_index_path",
    "run_arm",
]

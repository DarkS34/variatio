"""Which waiting job goes first: three classes by duration and by who waits, and aging.

A turn of the tutor lasts about 30 s and a person waits for it in a chat; a batch of exercises
lasts minutes and a person waits on a progress bar; a build lasts minutes to hours and nobody
waits for it at that moment (`catalogue.JOB_CLASS`). The short job goes first: it lowers
everybody's mean wait and hardly delays the long one. Inside a class, order of arrival.

AGING keeps anybody from waiting for ever: a job that has waited past its class's term counts
as the class above. B rises after `QUEUE_PROMOTE_B_AFTER_SECONDS`; C rises to B after
`QUEUE_PROMOTE_C_AFTER_SECONDS` and to A after B's term on top, so a build waits 690 s at most
behind the classes above it with the defaults.

On the local lane, background jobs hold at most `LOCAL_MAX_BACKGROUND_JOBS` slots, counted by
the kind's own class even after aging: the cap keeps room for the interactive ones, and aging
must not get round it. With Ollama the lane holds one job and the cap never acts.

What the order does not fix: with one slot, a build already running keeps the tutor waiting
until it ends. That is operational — builds go outside class hours.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from variatio import config

from .catalogue import BACKGROUND, BATCH, DEFAULT_CLASS, INTERACTIVE, JOB_CLASS, Job

# The classes in the order they go out.
RANK = {INTERACTIVE: 0, BATCH: 1, BACKGROUND: 2}


@dataclass(frozen=True)
class Rules:
    """The queue's three settings, read once per pass of the dispatcher."""

    promote_b: float
    promote_c: float
    local_background: int


def rules() -> Rules:
    """Read the rules live: the panel changes them while the process runs."""
    return Rules(
        promote_b=_number("QUEUE_PROMOTE_B_AFTER_SECONDS", 90, floor=0),
        promote_c=_number("QUEUE_PROMOTE_C_AFTER_SECONDS", 600, floor=0),
        local_background=int(_number("LOCAL_MAX_BACKGROUND_JOBS", 2, floor=1)),
    )


def class_of(kind: str) -> str:
    """Return the class a kind belongs to; one nobody classified is background."""
    return JOB_CLASS.get(kind, DEFAULT_CLASS)


def is_background(job: Job) -> bool:
    """Whether the job's own kind is background, whatever its waiting has made of it."""
    return class_of(job.kind) == BACKGROUND


def rank(job: Job, now: float, rules: Rules) -> int:
    """Return the rank a waiting job counts as now, 0 being A: its class, raised by its wait."""
    current = RANK[class_of(job.kind)]
    waited = max(0.0, now - job.created_at)
    if current == RANK[BACKGROUND]:
        if waited < rules.promote_c:
            return current
        waited -= rules.promote_c
        current = RANK[BATCH]
    if current == RANK[BATCH] and waited >= rules.promote_b:
        current = RANK[INTERACTIVE]
    return current


def order(waiting: Iterable[Job], now: float, rules: Rules) -> list[Job]:
    """Sort jobs given in order of arrival into the order they go out.

    The sort is stable, so inside one rank the order of arrival holds.
    """
    return sorted(waiting, key=lambda job: rank(job, now, rules))


def _number(name: str, default: float, floor: float) -> float:
    """Read one setting as a number no lower than `floor`, or its default if it is unreadable."""
    try:
        return max(floor, float(getattr(config, name)))
    except (AttributeError, TypeError, ValueError):
        return default

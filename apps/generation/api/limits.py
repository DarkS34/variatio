"""What a commission may ask for: its size, one batch at a time, and a student's day.

A commission is one live batch per account and subject (`generation_busy`), and a student's is
bounded twice more: its size (`GENERATION_STUDENT_MAX_ITEMS`) and the exercises asked for in
the day across every subject (`GENERATION_STUDENT_DAILY_ITEMS`, `usage`). A teacher has
neither bound. `admit` is what `POST /api/jobs` hands a `generate` to
(`server.routers.jobs.ADMISSIONS`, registered at install); `GET /api/jobs/allowance` tells the
form where its stepper stops.
"""

import threading
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DbSession

from server import auth, singletons
from server.db.models import VIEWER
from server.jobs.catalogue import Job
from variatio import config, entrypoints

from . import usage

router = APIRouter(prefix="/api", tags=["generations"], dependencies=[auth.VIEW])

# What a second live batch of one account in one subject is refused with.
GENERATION_BUSY = "generation_busy"

# Held from a commission's checks to its queueing and its count: two presses of one account at
# once must not both find the subject free of its batch, or both under the day's limit.
_COMMISSIONING = threading.Lock()


def admit(
    db: DbSession, access: auth.Access, params: dict, queue: Callable[[], Job]
) -> Job:
    """Check a commission against its bounds, queue it, and charge a student's day.

    The size is checked before the lock, since it needs nothing shared; the batch already
    running and the day's count are checked under it, with the queueing and the charge.
    """
    student = access.role == VIEWER
    count = check(params, student)
    with _COMMISSIONING:
        _refuse_second_batch(access)
        if student:
            _refuse_over_the_day(db, access, count)
        job = queue()
        if student:
            # Counted as asked and committed before the lock goes, so the next press reads it.
            usage.record(db, access.user.id, count)
            db.commit()
    return job


def check(params: dict, student: bool = False) -> int:
    """Refuse a commission naming something the installation does not offer; return its size.

    Checked here as well as in the handler, and for the same reason the raw slots check a
    filename twice: what arrives in a request is checked against what the installation
    actually holds, never sanitised and used. Here it is a 422 the screen can show; there
    it is the last word, because the offered list is edited while jobs sit in the queue.

    Only what can be answered without a model and without an index is checked here. The
    concepts, the fixed fields and the curriculum are the generator's, because deciding
    them needs the knowledge graph and the exemplars profile — a `RuntimeContext`, which
    on a cold workspace is minutes. What must not wait for that is the COUNT: it is the
    one parameter that decides how much a single request spends, and unbounded it let a
    commission empty the day's quota before anything could refuse it. A student's count has a
    lower ceiling of its own. The size returned is what the handler will write (one when the
    commission names none) and what a student's day is charged.
    """
    try:
        entrypoints.resolve_generation_model(params.get("model"))
    except entrypoints.UnofferedModelError as error:
        raise HTTPException(422, str(error)) from None

    count = 1
    if params.get("n") is not None:
        try:
            count = int(params["n"])
        except (TypeError, ValueError):
            raise HTTPException(422, "El número de ítems tiene que ser un entero.") from None
        if count < 1:
            raise HTTPException(422, f"Hay que pedir al menos un ítem; pediste {count}.")
        if count > config.GENERATION_MAX_ITEMS:
            raise HTTPException(
                422,
                f"Como mucho se pueden pedir {config.GENERATION_MAX_ITEMS} ítems de una vez; "
                f"pediste {count}.",
            )
        ceiling = max_items(student)
        if count > ceiling:
            raise HTTPException(
                422,
                f"Como alumno puedes pedir como mucho {ceiling} ejercicios de una vez; "
                f"pediste {count}.",
            )

    instructions = params.get("instructions") or ""
    if len(instructions) > config.GENERATION_INSTRUCTIONS_MAX_CHARS:
        raise HTTPException(
            422,
            f"Las instrucciones no pueden pasar de "
            f"{config.GENERATION_INSTRUCTIONS_MAX_CHARS} caracteres; llevan {len(instructions)}.",
        )
    return count


def max_items(student: bool) -> int:
    """Return how many exercises one commission may ask for: a student's ceiling is lower."""
    if not student:
        return config.GENERATION_MAX_ITEMS
    return min(config.GENERATION_STUDENT_MAX_ITEMS, config.GENERATION_MAX_ITEMS)


def _refuse_second_batch(access: auth.Access) -> None:
    """Refuse a commission while this account has another batch queued or running here."""
    live = [*singletons.runner.running(access.ws.slug), *singletons.runner.pending(access.ws.slug)]
    if any(job.kind == "generate" and job.user_id == access.user.id for job in live):
        raise HTTPException(
            409,
            "Ya tienes un lote de ejercicios en marcha en esta asignatura. Espera a que termine, "
            "o detenlo, antes de pedir otro.",
            headers={"X-Error-Code": GENERATION_BUSY},
        )


def _refuse_over_the_day(db: DbSession, access: auth.Access, count: int) -> None:
    """Refuse a student's commission that would pass the exercises of their day."""
    refused = usage.refusal(
        db, access.user.id, config.GENERATION_STUDENT_DAILY_ITEMS, count
    )
    if refused is None:
        return
    headers = {}
    if refused.code is not None:
        headers["X-Error-Code"] = refused.code
    if refused.retry_after is not None:
        headers["Retry-After"] = str(refused.retry_after)
    raise HTTPException(refused.status, refused.message, headers=headers or None)


# Mounted before the queue's router (`server/app.py`): there `/jobs/{job_id}` would read
# "allowance" as a job id.
@router.get("/jobs/allowance")
def allowance(access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)) -> dict:
    """Answer how many exercises this account may ask for here: per commission and per day.

    What the generate form draws its quantity's ceiling from. `daily_items` is null without a
    daily limit, which is a teacher's case always; `used_today` counts across every subject.
    """
    student = access.role == VIEWER
    limit = config.GENERATION_STUDENT_DAILY_ITEMS if student else None
    return {
        "max_items": max_items(student),
        "daily_items": limit,
        "used_today": usage.used_today(db, access.user.id) if limit else 0,
    }

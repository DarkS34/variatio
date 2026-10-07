"""The job queue: submitting work, watching it, and replaying what it said.

Declares `auth.VIEW` for the whole router, submitting and cancelling included, and decides
by kind inside: a student of the subject (`viewer`) queues a commission or a comparison
(`STUDENT_KINDS`) and cancels their own; everything else — a build, a transcription, an
indexing — takes a teacher, and a refusal says `role_too_low`.

A commission is one live batch per account and subject (`generation_busy`), and a
student's is bounded twice more: its size (`GENERATION_STUDENT_MAX_ITEMS`) and the exercises
asked for in the day across every subject (`GENERATION_STUDENT_DAILY_ITEMS`,
`generation_usage`). A teacher has neither bound.

The chain's gates are enforced here and not merely drawn in the UI, so a stale artifact
cannot be silently consumed. A job is only ever visible to the workspace it was submitted
for: without that the id is a twelve-hex guess away from another instance's event log. A
private job (`catalogue.PRIVATE_KINDS`) is visible to its author alone, and answers anybody
else the same 404 as a job that does not exist, as a generated exercise does.
"""

import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from variatio import config, entrypoints
from variatio.core import inference
from variatio.core.workspace import Workspace

from .. import approvals, auth, features, generation_usage, raw_data, singletons
from ..db.models import EDITOR, VIEWER
from ..jobs import lanes
from ..jobs.catalogue import JOB_ARTIFACT, JOB_LABELS, STUDENT_KINDS, SUBPROCESS_KINDS

router = APIRouter(prefix="/api", tags=["jobs"], dependencies=[auth.VIEW])

# What the chain requires before a job kind is allowed to run.
GATES: dict[str, str | None] = {
    "build_profile": None,
    "build_kg": None,
    "build_bank": approvals.EXEMPLARS_BANK,
    "describe_concepts": None,
    "index": None,
    "tag": approvals.EXEMPLARS_BANK,
    "generate": "__all__",
    "evaluate": "__all__",
}

# The job kinds that belong to an optional function (`server/features.py`): queued here only
# by an account the function is open to, and named as a lane's holder only to such an account
# (`routers/pipeline.py`). The tutor's kinds are not in `JOB_LABELS` at all, so this route
# never queues them; `tutor.api.install` adds them here for the second use.
FEATURE_OF: dict[str, str] = {"evaluate": features.EVALUATION}

# What a second live batch of one account in one subject is refused with.
GENERATION_BUSY = "generation_busy"

# Held from a commission's checks to its queueing and its count: two presses of one account at
# once must not both find the subject free of its batch, or both under the day's limit.
_COMMISSIONING = threading.Lock()

# `GATES` answers "are the UPSTREAM of X approved?", which is the question for building X.
# Taggability asks a different one — that a SPECIFIC artifact is approved — and cannot
# reuse `EXEMPLARS_BANK` as a gate: that would demand the graph be approved, and the review
# is what happens before approving it. Hence a table of its own.
NEEDS_APPROVED: dict[str, str] = {
    "review_taggability": approvals.EXEMPLARS_PROFILE,
}


class JobBody(BaseModel):
    """What to run, with what parameters, and whether to skip the chain's gates.

    `force` is a teacher's: a student's commission always waits for the construction to be
    closed, because what it would read is a subject still being corrected.
    """

    kind: str
    params: dict = {}
    force: bool = False


def gate_error(ws: Workspace, kind: str) -> str | None:
    """Say in Spanish which steps have to be settled before `kind` may run, or nothing.

    It names the STATE and not a button: "Aprobar" is not a control any more — a stage is
    closed by moving on from it — so "aprueba primero" sent people looking for something
    that is not on the screen.
    """
    needed = NEEDS_APPROVED.get(kind)
    if needed is not None:
        if singletons.approvals(ws).state(needed)["status"] != "approved":
            return f"Antes hay que dar por bueno: {approvals.LABELS[needed]}."

    gate = GATES.get(kind)
    if gate is None:
        return None
    state = singletons.approvals(ws)
    if gate == "__all__":
        if not state.generation_unlocked():
            pending = _pending_labels(ws)
            return f"Para crear ejercicios hay que dar antes por buenos: {', '.join(pending)}."
        return None
    if not state.gate_open(gate):
        blockers = _unapproved_upstream(state, gate)
        return f"Antes hay que dar por bueno: {', '.join(blockers)}."
    return None


def transcribing_slot(slug: str, kind: str) -> str | None:
    """Name the raw slot `kind` would read that is being transcribed right now, or nothing.

    Only the three builds read a slot (`SUBPROCESS_KINDS`); `tag` rewrites the bank from
    what is already in it. A transcription and a build of the same slot both write the
    same page cache, document by document, so they must not run at once — and the queue
    does not keep them apart, since on a hybrid engine they may sit on different lanes.
    This is NOT the transcription becoming a gate: a slot nobody is reading builds whether
    its pages are cached or not.
    """
    if kind not in SUBPROCESS_KINDS:
        return None
    slot = raw_data.slot_feeding(JOB_ARTIFACT.get(kind))
    if slot is None or singletons.transcribing(slug, slot) is None:
        return None
    return slot


def transcription_error(ws: Workspace, kind: str) -> str | None:
    """Say in Spanish that the slot this build reads is being transcribed, or nothing."""
    slot = transcribing_slot(ws.slug, kind)
    if slot is None:
        return None
    label = raw_data.SLOTS[slot]["label"]
    return f"Se está leyendo «{label}»: espera a que termine antes de construir."


def _pending_labels(ws: Workspace) -> list[str]:
    """Name the stages of the chain that are not approved yet."""
    return [
        s["label"] for s in singletons.pipeline_snapshot(ws) if s["status"] != "approved"
    ]


def _unapproved_upstream(state, gate: str) -> list[str]:
    """Name the artifacts `gate` depends on that are not approved yet."""
    return [
        approvals.LABELS[up]
        for up in approvals.UPSTREAM[gate]
        if state.state(up)["status"] != "approved"
    ]


def _check_params(kind: str, params: dict, student: bool = False) -> int:
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
    commission names none) and what a student's day is charged; zero for any other kind.
    """
    if kind != "generate":
        return 0
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
    refused = generation_usage.refusal(
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


def _mine(job_id: str, access: auth.Access):
    """Load a job this account may see here, or 404.

    One of another instance does not exist here, and neither does another account's private
    job: the same sentence for both, because a 403 would confirm that the id names one.
    """
    job = singletons.runner.get(job_id)
    if job is None or job.workspace != access.ws.slug or not job.seen_by(access.user.id):
        raise HTTPException(404, f"No existe el trabajo '{job_id}'")
    return job


@router.post("/jobs")
def submit(
    body: JobBody, access: auth.Access = auth.VIEW, db: DbSession = Depends(auth.db)
) -> dict:
    """Queue one job, answering its position behind whatever is already on its lanes."""
    if body.kind not in JOB_LABELS:
        raise HTTPException(422, f"Trabajo desconocido: '{body.kind}'")

    teacher = auth.at_least(access, EDITOR)
    if body.kind not in STUDENT_KINDS and not teacher:
        raise HTTPException(
            403,
            "Ese trabajo es de quien da clase en la asignatura.",
            headers={"X-Error-Code": auth.ROLE_TOO_LOW},
        )

    # A kind that belongs to an optional function is that function's: this route must not be
    # a way round the dependency its own router declares. Generating is everybody's, but a
    # subject's teachers may close it to its students.
    feature = FEATURE_OF.get(body.kind) or (features.GENERATE if body.kind == "generate" else None)
    refused = feature and features.refusal(db, access.user, feature, access.workspace, access.role)
    if refused:
        raise HTTPException(403, refused, headers={"X-Error-Code": features.OFF_CODE})

    # Without an engine no job can succeed: every kind calls a model. `force` skips the
    # chain's gates, which are a teacher's decision, and never this, which is impossible.
    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia "
            f"'{inference.engine_name()}'. Arráncalo y vuelve a intentarlo.",
        )

    if not (body.force and teacher):
        error = gate_error(access.ws, body.kind)
        if error:
            raise HTTPException(409, error)

    # Outside `force`: the gates are the person's decision, two jobs writing one page
    # cache is not.
    error = transcription_error(access.ws, body.kind)
    if error:
        raise HTTPException(409, error)

    student = access.role == VIEWER
    count = _check_params(body.kind, body.params, student)

    with _COMMISSIONING:
        if body.kind == "generate":
            _refuse_second_batch(access)
            if student:
                _refuse_over_the_day(db, access, count)
        job = singletons.runner.submit(
            body.kind,
            body.params,
            workspace=access.ws.slug,
            user_id=access.user.id,
            user_name=access.user.name,
            redacted=student,
        )
        if body.kind == "generate" and student:
            # Counted as asked and committed before the lock goes, so the next press reads it.
            generation_usage.record(db, access.user.id, count)
            db.commit()
    return {
        "job": job.to_dict(),
        "since": singletons.bus.last_seq,
        "queue_position": singletons.runner.queue_position(job.id),
    }


@router.get("/jobs")
def listing(limit: int = Query(50, ge=1, le=200), access: auth.Access = auth.VIEW) -> dict:
    """Answer the most recent jobs of this workspace that this account may see."""
    jobs = singletons.runner.all(limit, workspace=access.ws.slug, for_user=access.user.id)
    return {"jobs": [j.to_dict() for j in jobs]}


# Declared above `/jobs/{job_id}`: FastAPI matches in declaration order, so the other way
# round "current" would be read as a job id and answer "no existe el trabajo 'current'".
@router.get("/jobs/current")
def current(access: auth.Access = auth.VIEW) -> dict:
    """Answer this workspace's oldest running job, its queue, and whether a lane is held.

    `job` is the oldest run of YOUR workspace and not of the installation: with one job
    per lane there can be two at once, and blanking yours because somebody else's started
    first on the other lane would report "nada en ejecución" while your build runs.
    Whether a lane is held at all stays global — the machine is shared. Another account's
    private job is neither `job` nor in `queued`: what it is doing is its author's.
    """
    me = access.user.id
    running = singletons.runner.running()
    ours = [j for j in running if j.workspace == access.ws.slug and j.seen_by(me)]
    holders = [singletons.runner.current_in(backend) for backend in lanes.BACKENDS]
    held = [job for job in holders if job is not None]
    return {
        "job": ours[0].to_dict() if ours else None,
        "queued": [
            {**j.to_dict(), "queue_position": singletons.runner.queue_position(j.id)}
            for j in singletons.runner.pending(access.ws.slug)
            if j.seen_by(me)
        ],
        "engine_busy": bool(held),
        "engine_busy_elsewhere": any(j.workspace != access.ws.slug for j in held),
        "last_seq": singletons.bus.last_seq,
    }


# Declared above `/jobs/{job_id}`, for `current`'s reason.
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
        "used_today": generation_usage.used_today(db, access.user.id) if limit else 0,
    }


@router.get("/jobs/{job_id}")
def detail(job_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one job of this workspace, with how many are ahead of it."""
    job = _mine(job_id, access)
    return {"job": job.to_dict(), "queue_position": singletons.runner.queue_position(job_id)}


@router.delete("/jobs/{job_id}")
def cancel(job_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Ask one job of this workspace to stop at its next checkpoint.

    A student stops their own jobs and no other; a teacher stops any job they can see — every
    build, and their own commissions. Another account's private job is a 404 to both.
    """
    job = _mine(job_id, access)
    if job.user_id != access.user.id and not auth.at_least(access, EDITOR):
        raise HTTPException(
            403,
            "Solo puedes detener tus propios trabajos.",
            headers={"X-Error-Code": auth.ROLE_TOO_LOW},
        )
    return {"cancelled": singletons.runner.cancel(job_id)}


@router.get("/events")
def events(since: int = 0, access: auth.Access = auth.VIEW) -> dict:
    """Replay this workspace's events since `since`, saying whether any were lost.

    The router-level dependency already guarantees membership; the filter is passed
    explicitly anyway so "you may only replay your own events" is visible where the
    replay happens rather than inferred two files away.
    """
    replayed, gap = singletons.bus.replay(
        since, workspace=access.ws.slug, user_id=access.user.id
    )
    return {"events": replayed, "gap": gap, "last_seq": singletons.bus.last_seq}

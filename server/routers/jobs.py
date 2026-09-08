"""The job queue: submitting work, watching it, and replaying what it said.

Declares `auth.VIEW` for the whole router; submitting and cancelling add `auth.EDIT`.

The chain's gates are enforced here and not merely drawn in the UI, so a stale artifact
cannot be silently consumed. A job is only ever visible to the workspace it was submitted
for: without that the id is a twelve-hex guess away from another instance's event log.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from variatio import config, entrypoints
from variatio.core import inference
from variatio.core.workspace import Workspace

from .. import approvals, auth, singletons
from ..jobs import lanes
from ..jobs.catalogue import JOB_LABELS

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
}

# `GATES` answers "are the UPSTREAM of X approved?", which is the question for building X.
# Taggability asks a different one — that a SPECIFIC artifact is approved — and cannot
# reuse `EXEMPLARS_BANK` as a gate: that would demand the graph be approved, and the review
# is what happens before approving it. Hence a table of its own.
NEEDS_APPROVED: dict[str, str] = {
    "review_taggability": approvals.EXEMPLARS_PROFILE,
}


class JobBody(BaseModel):
    """What to run, with what parameters, and whether to skip the chain's gates."""

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


def _check_params(kind: str, params: dict) -> None:
    """Refuse a commission naming something the installation does not offer.

    Checked here as well as in the handler, and for the same reason the raw slots check a
    filename twice: what arrives in a request is checked against what the installation
    actually holds, never sanitised and used. Here it is a 422 the screen can show; there
    it is the last word, because the offered list is edited while jobs sit in the queue.

    Only what can be answered without a model and without an index is checked here. The
    concepts, the fixed fields and the curriculum are the generator's, because deciding
    them needs the knowledge graph and the exemplars profile — a `RuntimeContext`, which
    on a cold workspace is minutes. What must not wait for that is the COUNT: it is the
    one parameter that decides how much a single request spends, and unbounded it let a
    commission empty the day's quota before anything could refuse it.
    """
    if kind != "generate":
        return
    try:
        entrypoints.resolve_generation_model(params.get("model"))
    except entrypoints.UnofferedModelError as error:
        raise HTTPException(422, str(error)) from None

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

    instructions = params.get("instructions") or ""
    if len(instructions) > config.GENERATION_INSTRUCTIONS_MAX_CHARS:
        raise HTTPException(
            422,
            f"Las instrucciones no pueden pasar de "
            f"{config.GENERATION_INSTRUCTIONS_MAX_CHARS} caracteres; llevan {len(instructions)}.",
        )


def _mine(job_id: str, access: auth.Access):
    """Load a job of this workspace, or 404 — one of another instance does not exist here."""
    job = singletons.runner.get(job_id)
    if job is None or job.workspace != access.ws.slug:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'")
    return job


@router.post("/jobs", dependencies=[auth.EDIT])
def submit(body: JobBody, access: auth.Access = auth.VIEW) -> dict:
    """Queue one job, answering its position behind whatever is already on its lanes."""
    if body.kind not in JOB_LABELS:
        raise HTTPException(422, f"Trabajo desconocido: '{body.kind}'")

    # Without an engine no job can succeed: every kind calls a model. `force` skips the
    # chain's gates, which are the user's decision, and never this, which is impossible.
    if not inference.is_available():
        raise HTTPException(
            503,
            f"No hay conexión con el motor de inferencia "
            f"'{inference.engine_name()}'. Arráncalo y vuelve a intentarlo.",
        )

    if not body.force:
        error = gate_error(access.ws, body.kind)
        if error:
            raise HTTPException(409, error)

    _check_params(body.kind, body.params)

    job = singletons.runner.submit(
        body.kind,
        body.params,
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    return {
        "job": job.to_dict(),
        "since": singletons.bus.last_seq,
        "queue_position": singletons.runner.queue_position(job.id),
    }


@router.get("/jobs")
def listing(limit: int = Query(50, ge=1, le=200), access: auth.Access = auth.VIEW) -> dict:
    """Answer the most recent jobs of this workspace."""
    return {
        "jobs": [j.to_dict() for j in singletons.runner.all(limit, workspace=access.ws.slug)]
    }


# Declared above `/jobs/{job_id}`: FastAPI matches in declaration order, so the other way
# round "current" would be read as a job id and answer "no existe el trabajo 'current'".
@router.get("/jobs/current")
def current(access: auth.Access = auth.VIEW) -> dict:
    """Answer this workspace's oldest running job, its queue, and whether a lane is held.

    `job` is the oldest run of YOUR workspace and not of the installation: with one job
    per lane there can be two at once, and blanking yours because somebody else's started
    first on the other lane would report "nada en ejecución" while your build runs.
    Whether a lane is held at all, and by what, stays global — the machine is shared.
    """
    running = singletons.runner.running()
    ours = [j for j in running if j.workspace == access.ws.slug]
    holders = [singletons.runner.current_in(backend) for backend in lanes.BACKENDS]
    held = [job for job in holders if job is not None]
    return {
        "job": ours[0].to_dict() if ours else None,
        "queued": [
            {**j.to_dict(), "queue_position": singletons.runner.queue_position(j.id)}
            for j in singletons.runner.pending(access.ws.slug)
        ],
        "engine_busy": bool(held),
        "engine_busy_elsewhere": any(j.workspace != access.ws.slug for j in held),
        "last_seq": singletons.bus.last_seq,
    }


@router.get("/jobs/{job_id}")
def detail(job_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one job of this workspace, with how many are ahead of it."""
    job = _mine(job_id, access)
    return {"job": job.to_dict(), "queue_position": singletons.runner.queue_position(job_id)}


@router.get("/jobs/{job_id}/events")
def job_events(
    job_id: str,
    since: int = 0,
    limit: int = Query(5000, ge=1, le=50000),
    access: auth.Access = auth.VIEW,
) -> dict:
    """Replay one job's events, for a screen that arrived after they were emitted."""
    _mine(job_id, access)
    return {
        "events": singletons.bus.job_events(
            access.ws.slug, job_id, since=since, limit=limit
        )
    }


@router.delete("/jobs/{job_id}", dependencies=[auth.EDIT])
def cancel(job_id: str, access: auth.Access = auth.VIEW) -> dict:
    """Ask one job of this workspace to stop at its next checkpoint."""
    _mine(job_id, access)
    return {"cancelled": singletons.runner.cancel(job_id)}


@router.get("/events")
def events(since: int = 0, access: auth.Access = auth.VIEW) -> dict:
    """Replay this workspace's events since `since`, saying whether any were lost.

    The router-level dependency already guarantees membership; the filter is passed
    explicitly anyway so "you may only replay your own events" is visible where the
    replay happens rather than inferred two files away.
    """
    replayed, gap = singletons.bus.replay(since, workspace=access.ws.slug)
    return {"events": replayed, "gap": gap, "last_seq": singletons.bus.last_seq}

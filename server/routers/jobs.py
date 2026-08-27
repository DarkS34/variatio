from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from variatio.core import inference
from variatio.core.workspace import Workspace

from .. import auth, review, runtime
from ..jobs import lanes
from ..jobs.models import JOB_LABELS

router = APIRouter(prefix="/api", tags=["jobs"], dependencies=[auth.VIEW])

# What the chain requires before a job kind is allowed to run. Gates are enforced
# here, not just drawn in the UI, so a stale artifact cannot be silently consumed.
GATES: dict[str, str | None] = {
    "build_profile": None,
    "build_kg": None,
    "build_bank": review.EXEMPLARS_BANK,
    "describe_concepts": None,
    "index": None,
    "warm_models": None,
    "tag": review.EXEMPLARS_BANK,
    "generate": "__all__",
    "evaluate": "__all__",
}

# `GATES` answers "are the UPSTREAM of X approved?", which is the question for building
# X. Taggability needs a different one: that a SPECIFIC artifact is approved. It cannot
# reuse `EXEMPLARS_BANK` as its gate — that would demand the graph be approved, and this
# is reviewed BEFORE approving it — so it gets its own table.
NEEDS_APPROVED: dict[str, str] = {
    "review_taggability": review.EXEMPLARS_PROFILE,
}


class JobBody(BaseModel):
    kind: str
    params: dict = {}
    force: bool = False


def gate_error(ws: Workspace, kind: str) -> str | None:
    needed = NEEDS_APPROVED.get(kind)
    if needed is not None:
        if runtime.review_state(ws).state(needed)["status"] != "approved":
            return f"Aprueba primero: {review.LABELS[needed]}."

    gate = GATES.get(kind)
    if gate is None:
        return None
    state = runtime.review_state(ws)
    if gate == "__all__":
        if not state.generation_unlocked():
            pending = [
                s["label"]
                for s in runtime.pipeline_snapshot(ws)
                if s["status"] != "approved"
            ]
            return f"Para generar hay que aprobar antes: {', '.join(pending)}."
        return None
    if not state.gate_open(gate):
        blockers = [
            review.LABELS[up]
            for up in review.UPSTREAM[gate]
            if state.state(up)["status"] != "approved"
        ]
        return f"Aprueba primero: {', '.join(blockers)}."
    return None


# A job is only visible to the workspace it was submitted for. Without this the id is a
# twelve-hex guess away from another instance's event log, which is precisely the leak the
# WebSocket was fixed for in phase 2.
def _mine(job_id: str, access: auth.Access):
    job = runtime.runner.get(job_id)
    if job is None or job.workspace != access.ws.slug:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'")
    return job


@router.post("/jobs", dependencies=[auth.EDIT])
def submit(body: JobBody, access: auth.Access = auth.VIEW) -> dict:
    if body.kind not in JOB_LABELS:
        raise HTTPException(422, f"Trabajo desconocido: '{body.kind}'")

    # Without an engine no job can succeed: every kind calls a model. It used to be accepted,
    # enqueued and blow up inside, leaving a failure in the history where there should have
    # been a disabled button. `force` skips the chain's gates — which are the user's decision
    # — and not this, which is an impossibility.
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

    job = runtime.runner.submit(
        body.kind,
        body.params,
        workspace=access.ws.slug,
        user_id=access.user.id,
        user_name=access.user.name,
    )
    return {
        "job": job.to_dict(),
        "since": runtime.bus.last_seq,
        "queue_position": runtime.runner.queue_position(job.id),
    }


@router.get("/jobs")
def listing(limit: int = Query(50, ge=1, le=200), access: auth.Access = auth.VIEW) -> dict:
    return {
        "jobs": [j.to_dict() for j in runtime.runner.all(limit, workspace=access.ws.slug)]
    }


# `job` is the oldest run of YOUR workspace, not the oldest run of the installation: with
# one job per lane there can be two at once, and blanking yours because somebody else's
# started first on the other lane would report «nada en ejecución» while your build runs.
# What stays global is whether a lane is held at all, and by what.
@router.get("/jobs/current")
def current(access: auth.Access = auth.VIEW) -> dict:
    running = runtime.runner.running()
    ours = [j for j in running if j.workspace == access.ws.slug]
    holders = [runtime.runner.current_in(backend) for backend in lanes.BACKENDS]
    held = [job for job in holders if job is not None]
    return {
        "job": ours[0].to_dict() if ours else None,
        "queued": [
            {**j.to_dict(), "queue_position": runtime.runner.queue_position(j.id)}
            for j in runtime.runner.pending(access.ws.slug)
        ],
        "engine_busy": bool(held),
        "engine_busy_elsewhere": any(j.workspace != access.ws.slug for j in held),
        "last_seq": runtime.bus.last_seq,
    }


@router.get("/jobs/{job_id}")
def detail(job_id: str, access: auth.Access = auth.VIEW) -> dict:
    job = _mine(job_id, access)
    return {"job": job.to_dict(), "queue_position": runtime.runner.queue_position(job_id)}


@router.get("/jobs/{job_id}/events")
def job_events(
    job_id: str,
    since: int = 0,
    limit: int = Query(5000, ge=1, le=50000),
    access: auth.Access = auth.VIEW,
) -> dict:
    _mine(job_id, access)
    return {
        "events": runtime.bus.job_events(
            access.ws.slug, job_id, since=since, limit=limit
        )
    }


@router.delete("/jobs/{job_id}", dependencies=[auth.EDIT])
def cancel(job_id: str, access: auth.Access = auth.VIEW) -> dict:
    _mine(job_id, access)
    return {"cancelled": runtime.runner.cancel(job_id)}


# The router-level dependency already guarantees membership, but the filter is passed
# explicitly anyway: "you may only replay your own events" should be visible where the
# replay happens, not inferred two files away.
@router.get("/events")
def events(since: int = 0, access: auth.Access = auth.VIEW) -> dict:
    replayed, gap = runtime.bus.replay(since, workspace=access.ws.slug)
    return {"events": replayed, "gap": gap, "last_seq": runtime.bus.last_seq}

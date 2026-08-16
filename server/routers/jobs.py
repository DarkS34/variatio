from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from variant_generator.workspace import Workspace

from .. import auth, review, runtime
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
    "tag": review.EXEMPLARS_BANK,
    "generate": "__all__",
    "evaluate": "__all__",
}


class JobBody(BaseModel):
    kind: str
    params: dict = {}
    force: bool = False


def gate_error(ws: Workspace, kind: str) -> str | None:
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


@router.get("/jobs/current")
def current(access: auth.Access = auth.VIEW) -> dict:
    running = runtime.runner.current()
    mine = running is not None and running.workspace == access.ws.slug
    queued = runtime.runner.pending(access.ws.slug)
    return {
        "job": running.to_dict() if mine else None,
        "queued": [
            {**j.to_dict(), "queue_position": runtime.runner.queue_position(j.id)}
            for j in queued
        ],
        "engine_busy": running is not None,
        "engine_busy_elsewhere": running is not None and not mine,
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

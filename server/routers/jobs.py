from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

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


def gate_error(kind: str) -> str | None:
    gate = GATES.get(kind)
    if gate is None:
        return None
    if gate == "__all__":
        if not runtime.review_state.generation_unlocked():
            pending = [
                s["label"]
                for s in runtime.pipeline_snapshot()
                if s["status"] != "approved"
            ]
            return f"Para generar hay que aprobar antes: {', '.join(pending)}."
        return None
    if not runtime.review_state.gate_open(gate):
        blockers = [
            review.LABELS[up]
            for up in review.UPSTREAM[gate]
            if runtime.review_state.state(up)["status"] != "approved"
        ]
        return f"Aprueba primero: {', '.join(blockers)}."
    return None


@router.post("/jobs", dependencies=[auth.EDIT])
def submit(body: JobBody) -> dict:
    if body.kind not in JOB_LABELS:
        raise HTTPException(422, f"Trabajo desconocido: '{body.kind}'")
    if not body.force:
        error = gate_error(body.kind)
        if error:
            raise HTTPException(409, error)

    job = runtime.runner.submit(body.kind, body.params)
    return {"job": job.to_dict(), "since": runtime.bus.last_seq}


@router.get("/jobs")
def listing(limit: int = Query(50, ge=1, le=200)) -> dict:
    return {"jobs": [j.to_dict() for j in runtime.runner.all(limit)]}


@router.get("/jobs/current")
def current() -> dict:
    job = runtime.runner.current()
    return {
        "job": job.to_dict() if job else None,
        "queued": [j.to_dict() for j in runtime.runner.pending()],
        "last_seq": runtime.bus.last_seq,
    }


@router.get("/jobs/{job_id}")
def detail(job_id: str) -> dict:
    job = runtime.runner.get(job_id)
    if job is None:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'")
    return {"job": job.to_dict()}


@router.get("/jobs/{job_id}/events")
def job_events(job_id: str, since: int = 0, limit: int = Query(5000, ge=1, le=50000)) -> dict:
    if runtime.runner.get(job_id) is None:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'")
    return {"events": runtime.bus.job_events(job_id, since=since, limit=limit)}


@router.delete("/jobs/{job_id}", dependencies=[auth.EDIT])
def cancel(job_id: str) -> dict:
    if runtime.runner.get(job_id) is None:
        raise HTTPException(404, f"No existe el trabajo '{job_id}'")
    return {"cancelled": runtime.runner.cancel(job_id)}


# The router-level dependency already guarantees membership of the workspace the bus
# serves, but the filter is passed explicitly anyway: "you may only replay your own
# events" should be visible where the replay happens, not inferred two files away.
@router.get("/events")
def events(since: int = 0, access: auth.Access = Depends(auth.require_member())) -> dict:
    replayed, gap = runtime.bus.replay(since, workspace=access.workspace.slug)
    return {"events": replayed, "gap": gap, "last_seq": runtime.bus.last_seq}

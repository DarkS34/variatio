from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import review, runtime, storage

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# The job that moves each stage forward, so the UI never has to hardcode it.
NEXT_JOB = {
    review.EXEMPLARS_PROFILE: "build_profile",
    review.KNOWLEDGE_GRAPH: "build_kg",
    review.EXEMPLARS_BANK: "build_bank",
}


class RestoreBody(BaseModel):
    snapshot_id: str


def _check(artifact: str) -> None:
    if artifact not in review.ARTIFACTS:
        raise HTTPException(404, f"Artefacto desconocido: '{artifact}'")


@router.get("")
def get_pipeline() -> dict:
    stages = runtime.pipeline_snapshot()
    for stage in stages:
        stage["build_job"] = NEXT_JOB[stage["artifact"]]
    current = runtime.runner.current()
    return {
        "stages": stages,
        "generation_unlocked": all(s["status"] == "approved" for s in stages),
        "current_job": current.to_dict() if current else None,
        "queued": len(runtime.runner.pending()),
    }


@router.post("/{artifact}/approve")
def approve(artifact: str) -> dict:
    _check(artifact)
    try:
        runtime.review_state.approve(artifact)
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    runtime.bus.publish(None, "pipeline.changed", {"artifact": artifact, "action": "approve"})
    return get_pipeline()


@router.post("/{artifact}/reopen")
def reopen(artifact: str) -> dict:
    _check(artifact)
    runtime.review_state.reopen(artifact)
    runtime.bus.publish(None, "pipeline.changed", {"artifact": artifact, "action": "reopen"})
    return get_pipeline()


@router.get("/{artifact}/history")
def history(artifact: str) -> dict:
    _check(artifact)
    return {"artifact": artifact, "snapshots": storage.history(artifact)}


@router.post("/{artifact}/restore")
def restore(artifact: str, body: RestoreBody) -> dict:
    _check(artifact)
    target = review.canonical_path(artifact)
    try:
        storage.restore(artifact, body.snapshot_id, target)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    from .. import deps

    runtime.review_state.invalidate(artifact)
    deps.invalidate(f"'{artifact}' restaurado desde una copia")
    runtime.bus.publish(None, "pipeline.changed", {"artifact": artifact, "action": "restore"})
    return get_pipeline()

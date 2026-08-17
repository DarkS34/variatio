from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from variant_generator.stages import build_phases as phases_of

from .. import auth, deps, review, runtime, storage

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"], dependencies=[auth.VIEW])

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


# The chain of one workspace. `current_job` is deliberately the *global* one: there is a
# single GPU, so "somebody is building something" is true for everyone and hiding it would
# leave a queued job looking stuck. Which artifacts are marked as building is scoped,
# because that is a statement about this instance's files.
def pipeline_payload(access: auth.Access) -> dict:
    chain = runtime.pipeline_snapshot(access.ws)
    for stage in chain:
        stage["build_job"] = NEXT_JOB[stage["artifact"]]
    current = runtime.runner.current()
    mine = current is not None and current.workspace == access.ws.slug
    return {
        "stages": chain,
        "generation_unlocked": all(s["status"] == "approved" for s in chain),
        "current_job": current.to_dict() if mine else None,
        "queued": len(runtime.runner.pending(access.ws.slug)),
        # Somebody else is holding the one GPU: the honest reason a job of yours has not
        # started, and something no per-workspace number can express.
        "engine_busy": current is not None,
        "engine_busy_elsewhere": current is not None and not mine,
    }


@router.get("")
def get_pipeline(access: auth.Access = auth.VIEW) -> dict:
    return pipeline_payload(access)


# The phase plan each builder declares, which is what the progress bar is a drawing of:
# one section per phase, as wide as its weight. It says nothing about time — a weight is a
# share of the work, and what a share costs depends on the models, which change.
#
# Declared before `/{artifact}/…` so «phases» is read as itself and not as an artifact.
@router.get("/phases")
def build_phases() -> dict:
    return {
        "artifacts": {
            artifact: [
                {"key": key, "label": label, "weight": weight}
                for key, label, weight in phases_of(artifact)
            ]
            for artifact in review.ARTIFACTS
        }
    }


@router.post("/{artifact}/approve", dependencies=[auth.EDIT])
def approve(artifact: str, access: auth.Access = auth.VIEW) -> dict:
    _check(artifact)
    try:
        runtime.review_state(access.ws).approve(artifact)
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    runtime.bus.publish(
        access.ws.slug, None, "pipeline.changed", {"artifact": artifact, "action": "approve"}
    )
    return pipeline_payload(access)


@router.post("/{artifact}/reopen", dependencies=[auth.EDIT])
def reopen(artifact: str, access: auth.Access = auth.VIEW) -> dict:
    _check(artifact)
    runtime.review_state(access.ws).reopen(artifact)
    runtime.bus.publish(
        access.ws.slug, None, "pipeline.changed", {"artifact": artifact, "action": "reopen"}
    )
    return pipeline_payload(access)


@router.get("/{artifact}/history")
def history(artifact: str, access: auth.Access = auth.VIEW) -> dict:
    _check(artifact)
    return {"artifact": artifact, "snapshots": storage.history(access.ws, artifact)}


@router.post("/{artifact}/restore", dependencies=[auth.EDIT])
def restore(artifact: str, body: RestoreBody, access: auth.Access = auth.VIEW) -> dict:
    _check(artifact)
    target = review.canonical_path(access.ws, artifact)
    try:
        storage.restore(access.ws, artifact, body.snapshot_id, target)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    runtime.review_state(access.ws).invalidate(artifact)
    deps.invalidate(access.ws.slug, f"'{artifact}' restaurado desde una copia")
    runtime.bus.publish(
        access.ws.slug, None, "pipeline.changed", {"artifact": artifact, "action": "restore"}
    )
    return pipeline_payload(access)

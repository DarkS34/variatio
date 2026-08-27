from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from variatio import admissibility, taggability
from variatio.instance.exemplars_profile import ExemplarsProfile
from variatio.stages import _artifacts
from variatio.stages import build_phases as phases_of

from .. import auth, deps, review, runtime, storage
from ..editors import kg_edit
from ..jobs import lanes as jobs_lanes

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


# What each lane is doing, globally. The machine and the quota belong to the whole
# installation, so «busy» and the label of what is holding it are said to everyone — a
# queued job of yours that looks stuck has an honest reason, and no per-workspace number
# can express it. What is scoped is `mine`, `queued` and `ahead`: those are statements
# about your own work.
def _lane_payload(backend: str, slug: str) -> dict:
    holder = runtime.runner.current_in(backend)
    waiting = [j for j in runtime.runner.pending() if backend in j.backends]
    mine = [j for j in waiting if j.workspace == slug]
    ahead = None
    if mine:
        first = [j.id for j in waiting].index(mine[0].id)
        ahead = first + (1 if holder is not None else 0)
    return {
        "busy": holder is not None,
        "mine": holder is not None and holder.workspace == slug,
        "label": holder.label if holder is not None else None,
        "queued": len(mine),
        "ahead": ahead,
    }


# The chain of one workspace, and what the machine is doing behind it. The two halves are
# scoped differently on purpose: whether a lane is held, and by which job, is said to
# everyone — the machine is shared, so "somebody is building something" is true for
# everyone and hiding it would leave a queued job looking stuck — while `current_job`, the
# waiting counts and the artifacts marked as building are statements about this instance
# and never leave it.
def pipeline_payload(access: auth.Access) -> dict:
    chain = runtime.pipeline_snapshot(access.ws)
    for stage in chain:
        stage["build_job"] = NEXT_JOB[stage["artifact"]]
    slug = access.ws.slug
    waiting = runtime.runner.pending(slug)
    running = runtime.runner.running()
    # The oldest running job of THIS workspace. It used to be the oldest running job full
    # stop, blanked when it belonged elsewhere — which with two lanes would blank your own
    # run for as long as somebody else's older one is on the other lane.
    ours = [j for j in running if j.workspace == slug]
    current = ours[0] if ours else None
    lanes = {backend: _lane_payload(backend, slug) for backend in jobs_lanes.BACKENDS}
    ahead = None
    if waiting:
        first = set(waiting[0].backends)
        blocking = sum(1 for j in running if first & set(j.backends))
        ahead = blocking + runtime.runner.queue_position(waiting[0].id) - 1
    return {
        "stages": chain,
        "generation_unlocked": all(s["status"] == "approved" for s in chain),
        "current_job": current.to_dict() if current is not None else None,
        "queued": len(waiting),
        "queue_length": len(running) + len(runtime.runner.pending()),
        "queue_ahead": ahead,
        "lanes": lanes,
        # Somebody else is holding a lane: the honest reason a job of yours has not
        # started. Read off the lanes and not off `current`, because a job that reserves
        # nothing occupies neither and is holding nobody back.
        "engine_busy": any(lane["busy"] for lane in lanes.values()),
        "engine_busy_elsewhere": any(
            lane["busy"] and not lane["mine"] for lane in lanes.values()
        ),
    }


@router.get("")
def get_pipeline(access: auth.Access = auth.VIEW) -> dict:
    return pipeline_payload(access)


# The phase plan each builder declares, which is what the progress bar is a drawing of:
# one section per phase, as wide as its weight. It says nothing about time — a weight is a
# share of the work, and what a share costs depends on the models, which change.
#
# Declared before `/{artifact}/…` so «phases» is read as itself and not as an artifact.
# Some jobs build no artifact and still have a phase plan: the taggability review patches
# a list of the graph in place. `useArtifactRun` cannot find them — it is keyed by artifact
# —, so their plan is published by job kind.
JOB_PHASES = {"review_taggability": taggability.BUILD_PHASES}


def _plan(phases) -> list[dict]:
    return [{"key": key, "label": label, "weight": weight} for key, label, weight in phases]


@router.get("/phases")
def build_phases() -> dict:
    return {
        "artifacts": {artifact: _plan(phases_of(artifact)) for artifact in review.ARTIFACTS},
        "jobs": {kind: _plan(phases) for kind, phases in JOB_PHASES.items()},
    }


def _scope_payload(knowledge_graph, profile, content_context, item_type: str) -> dict:
    target_type = profile.item_type(item_type)
    found = admissibility.owners(knowledge_graph, target_type, profile, content_context, [])
    return {
        "slots": [
            {"key": s.key, "label": s.label, "example": s.example} for s in admissibility.CATALOG
        ],
        "owners": [
            {"key": o.key, "label": o.label, "where": o.where} for o in found if o.key != "context"
        ],
        "facts": [
            {"key": key, "value": value}
            for key, value in (
                ("subject", content_context.subject),
                ("educational_level", content_context.educational_level),
                ("language_of_instruction", content_context.language_of_instruction),
            )
            if value
        ],
    }


# The terms each owner decides never leave the server: the screen says WHO decides a thing,
# never which values it may take, which is why this takes no `concepts` and its answer does
# not change with the commission.
#
# Deliberately NOT `deps.get_context(access.ws)`: that registry builds a PipelineContext,
# which raises the embedder, the tagger and the generator and costs minutes. Three file
# reads are the whole job here.
@router.get("/scope")
def scope(item_type: str, access: auth.Access = auth.VIEW) -> dict:
    profile_path = _artifacts.exemplars_profile_path(access.ws)
    if profile_path is None:
        raise HTTPException(404, "El perfil de ejemplares no está construido")
    profile = ExemplarsProfile(profile_path)
    if item_type not in profile.item_types:
        raise HTTPException(404, f"Modalidad desconocida: '{item_type}'")
    try:
        knowledge_graph = kg_edit.load_graph(access.ws)
    except kg_edit.KGError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _scope_payload(
        knowledge_graph,
        profile,
        _artifacts.load_content_context(access.ws),
        item_type,
    )


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

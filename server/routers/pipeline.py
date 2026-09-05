"""The chain of one workspace: its three stages, its approvals and its history.

Declares `auth.VIEW` for the whole router; approving, reopening and restoring add
`auth.EDIT`.

ROUTE ORDER IS LOAD-BEARING. `/phases` and `/scope` are declared ABOVE the
`/{artifact}/…` routes: FastAPI matches in declaration order, and the other way round the
wildcard reads «phases» as an artifact and answers «Artefacto desconocido». Do not reorder.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from variatio.runtime import screening
from variatio.instance import locale
from variatio.instance.exemplars_profile import ExemplarsProfile
from variatio.entrypoints import TAGGABILITY_PHASES, _artifacts
from variatio.entrypoints import build_phases as phases_of

from .. import approvals, auth, deps, singletons, storage
from ..editors import kg_edit
from ..jobs import lanes as jobs_lanes

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"], dependencies=[auth.VIEW])

# The job that moves each stage forward, so the UI never has to hardcode it.
NEXT_JOB = {
    approvals.EXEMPLARS_PROFILE: "build_profile",
    approvals.KNOWLEDGE_GRAPH: "build_kg",
    approvals.EXEMPLARS_BANK: "build_bank",
}


class RestoreBody(BaseModel):
    """Which snapshot of `.history/` is being put back."""

    snapshot_id: str


def _check(artifact: str) -> None:
    """Raise 404 unless the path names one of the three artifacts of the chain."""
    if artifact not in approvals.ARTIFACTS:
        raise HTTPException(404, f"Artefacto desconocido: '{artifact}'")


def _lane_payload(backend: str, slug: str) -> dict:
    """Report one lane globally, and this workspace's own place in its queue.

    The machine and the quota belong to the installation, so `busy` and the label of what
    is holding the lane are said to everyone: a queued job of yours that looks stuck has
    an honest reason, and no per-workspace number can express it. `mine`, `queued` and
    `ahead` are the scoped half.

    `busy` means «this lane is FULL» and not «something is running on it» — it is what
    every reader uses to predict a wait, and on a lane of capacity 4 a third job waits for
    nothing. `running` and `capacity` report the activity itself; at capacity 1 the two
    readings coincide, so a single-engine installation is unchanged.
    """
    holders = singletons.runner.holders_in(backend)
    room = jobs_lanes.capacity(backend)
    waiting = [j for j in singletons.runner.pending() if backend in j.backends]
    mine = [j for j in waiting if j.workspace == slug]
    ahead = None
    if mine:
        # How many jobs have to finish before mine starts: everything already holding a
        # slot, plus everything queued in front of it, less the room there is. At capacity
        # 1 this is exactly the old «those in front, plus one if the lane is held».
        first = [j.id for j in waiting].index(mine[0].id)
        ahead = max(0, len(holders) + first + 1 - room)
    return {
        "busy": len(holders) >= room,
        "running": len(holders),
        "capacity": room,
        "mine": any(j.workspace == slug for j in holders),
        "label": holders[0].label if holders else None,
        "queued": len(mine),
        "ahead": ahead,
    }


def _queue_ahead(waiting: list, running: list) -> int | None:
    """Count what has to finish before this workspace's first queued job starts.

    Clamped at zero: the dispatcher can start `waiting[0]` between the two reads, and
    `queue_position` then answers 0 — «-1 por delante» is not a count.
    """
    if not waiting:
        return None
    first = set(waiting[0].backends)
    blocking = sum(1 for j in running if first & set(j.backends))
    return max(0, blocking + singletons.runner.queue_position(waiting[0].id) - 1)


def pipeline_payload(access: auth.Access) -> dict:
    """Answer one workspace's chain, and what the shared machine is doing behind it.

    The two halves are scoped differently on purpose: whether a lane is held, and by which
    job, is said to everyone — the machine is shared, so «somebody is building something»
    is true for everyone and hiding it leaves a queued job looking stuck — while
    `current_job`, the waiting counts and the artifacts marked as building are statements
    about this instance and never leave it.
    """
    chain = singletons.pipeline_snapshot(access.ws)
    for stage in chain:
        stage["build_job"] = NEXT_JOB[stage["artifact"]]
    slug = access.ws.slug
    waiting = singletons.runner.pending(slug)
    running = singletons.runner.running()
    # The oldest running job of THIS workspace: the oldest of the installation would blank
    # your own run for as long as somebody else's older one holds the other lane.
    ours = [j for j in running if j.workspace == slug]
    current = ours[0] if ours else None
    lanes = {backend: _lane_payload(backend, slug) for backend in jobs_lanes.BACKENDS}
    ahead = _queue_ahead(waiting, running)
    return {
        "stages": chain,
        "generation_unlocked": all(s["status"] == "approved" for s in chain),
        "current_job": current.to_dict() if current is not None else None,
        "queued": len(waiting),
        "queue_length": len(running) + len(singletons.runner.pending()),
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
    """Answer this workspace's chain and the state of the queue."""
    return pipeline_payload(access)


# Some jobs build no artifact and still have a phase plan: the taggability review patches
# a list of the graph in place. `useArtifactRun` is keyed by artifact and cannot find them,
# so their plan is published by job kind instead.
JOB_PHASES = {"review_taggability": TAGGABILITY_PHASES}


def _plan(phases) -> list[dict]:
    """Render one builder's `(key, label, weight)` triples for the progress bar."""
    return [{"key": key, "label": label, "weight": weight} for key, label, weight in phases]


@router.get("/phases")
def build_phases() -> dict:
    """Answer the phase plan of every builder, which is what the progress bar draws.

    A weight is a share of the WORK and says nothing about time: what a share costs
    depends on the models, and this project changes those to find out what they do.
    """
    return {
        "artifacts": {artifact: _plan(phases_of(artifact)) for artifact in approvals.ARTIFACTS},
        "jobs": {kind: _plan(phases) for kind, phases in JOB_PHASES.items()},
    }


def _scope_payload(knowledge_graph, profile, content_context, item_type: str, wording) -> dict:
    """Render the admissibility catalogue: the four slots and who owns each of them.

    Worded in the WORKSPACE's language and not the account's: what it names are the judge's
    own slots and the controls it points at, and the judge reads this instance's prompts.
    """
    target_type = profile.item_type(item_type)
    found = screening.owners(
        knowledge_graph, target_type, profile, content_context, [], wording
    )
    return {
        "slots": [
            {"key": s.key, "label": s.label, "example": s.example}
            for s in screening.catalog(wording)
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


@router.get("/scope")
def scope(item_type: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer what «Instrucciones adicionales» may not re-decide, for one modality.

    The owners' TERMS never leave the server: the payload names the control that decides
    a thing, never the values it may take, which is why this takes no `concepts` and its
    answer does not change with the commission.

    Deliberately NOT `deps.get_context(access.ws)`: that registry builds a
    `RuntimeContext`, which raises the embedder, the tagger and the generator and costs
    minutes. Three file reads are the whole job here.
    """
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
        locale.wording(access.ws),
    )


@router.post("/{artifact}/approve", dependencies=[auth.EDIT])
def approve(artifact: str, access: auth.Access = auth.VIEW) -> dict:
    """Mark one artifact approved, opening whatever it gates."""
    _check(artifact)
    try:
        singletons.approvals(access.ws).approve(artifact)
    except FileNotFoundError as exc:
        raise HTTPException(409, str(exc)) from exc
    singletons.bus.publish(
        access.ws.slug, None, "pipeline.changed", {"artifact": artifact, "action": "approve"}
    )
    return pipeline_payload(access)


@router.post("/{artifact}/reopen", dependencies=[auth.EDIT])
def reopen(artifact: str, access: auth.Access = auth.VIEW) -> dict:
    """Take one artifact back out of approval so it can be edited again."""
    _check(artifact)
    singletons.approvals(access.ws).reopen(artifact)
    singletons.bus.publish(
        access.ws.slug, None, "pipeline.changed", {"artifact": artifact, "action": "reopen"}
    )
    return pipeline_payload(access)


@router.get("/{artifact}/history")
def history(artifact: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one artifact's snapshots, the undo behind every destructive edit."""
    _check(artifact)
    return {"artifact": artifact, "snapshots": storage.history(access.ws, artifact)}


@router.post("/{artifact}/restore", dependencies=[auth.EDIT])
def restore(artifact: str, body: RestoreBody, access: auth.Access = auth.VIEW) -> dict:
    """Put one snapshot back in place, invalidating the warm context with it."""
    _check(artifact)
    target = approvals.canonical_path(access.ws, artifact)
    try:
        storage.restore(access.ws, artifact, body.snapshot_id, target)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    singletons.approvals(access.ws).invalidate(artifact)
    deps.invalidate(access.ws.slug, f"'{artifact}' restaurado desde una copia")
    singletons.bus.publish(
        access.ws.slug, None, "pipeline.changed", {"artifact": artifact, "action": "restore"}
    )
    return pipeline_payload(access)

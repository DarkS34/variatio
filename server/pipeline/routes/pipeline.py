"""The chain of one workspace: its three stages, its approvals and its history.

Declares `auth.VIEW` for the whole router; approving, reopening and restoring add
`auth.EDIT`, and so does reading a stage's history, whose snapshots are the construction's.

ROUTE ORDER IS LOAD-BEARING. `/phases` and `/scope` are declared ABOVE the
`/{artifact}/…` routes: FastAPI matches in declaration order, and the other way round the
wildcard reads "phases" as an artifact and answers "Artefacto desconocido". Do not reorder.
"""


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from variatio.runtime import screening
from variatio.loaders import locale
from variatio.loaders.exemplars_profile import ExemplarsProfile
from variatio.entrypoints import TAGGABILITY_PHASES, _artifacts
from variatio.entrypoints import build_phases as phases_of

from ... import auth, singletons
from ...core import contexts
from ...editors import kg_edit
from .. import approvals, storage
from ..view import pipeline_payload

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"], dependencies=[auth.VIEW])


class RestoreBody(BaseModel):
    """Which snapshot of `.history/` is being put back."""

    snapshot_id: str


def _check(artifact: str) -> None:
    """Raise 404 unless the path names one of the three artifacts of the chain."""
    if artifact not in approvals.ARTIFACTS:
        raise HTTPException(404, f"Artefacto desconocido: '{artifact}'")


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
    """Answer what "Instrucciones adicionales" may not re-decide, for one modality.

    The owners' TERMS never leave the server: the payload names the control that decides
    a thing, never the values it may take, which is why this takes no `concepts` and its
    answer does not change with the commission.

    Deliberately NOT `contexts.get_context(access.ws)`: that registry builds a
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


@router.get("/{artifact}/history", dependencies=[auth.EDIT])
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
    contexts.invalidate(access.ws.slug, f"'{artifact}' restaurado desde una copia")
    singletons.bus.publish(
        access.ws.slug, None, "pipeline.changed", {"artifact": artifact, "action": "restore"}
    )
    return pipeline_payload(access)

"""What follows a build on its own, and how far it may go.

A phase that HAS to happen should not be a button. Once the graph is built the descriptions
have to be written — without them no concept has a vector and tagging does not exist —, the
concepts that work as labels have to be decided, and the indices warmed, so the build that
leaves all three pending chains them.

What is NOT chained is whatever depends on an artifact that may not exist yet. Each link
declares its condition, and the condition is what the LINK ITSELF reads: describing needs
the graph and nothing else, the taggability review needs an approved profile, indexing
needs a profile and a bank. If a condition does not hold the link is skipped, the log says
so and the chain goes on with the next one. In a freshly created workspace — graph first,
no profile yet — the descriptions are written and the other two are skipped.

A link that fails or is cancelled cuts the chain: `advance` is only called after a job that
finished well.
"""

from loguru import logger

from variatio import entrypoints
from variatio.core.workspace import Workspace

from .. import approvals, installation
from .catalogue import JOB_LABELS, Job

# What each job drags behind it. Only the graph build has a chain: it is the only one
# whose result leaves three mandatory derivations undone.
CHAINS: dict[str, tuple[str, ...]] = {
    "build_kg": ("describe_concepts", "review_taggability", "index"),
}


def _graph_exists(ws: Workspace) -> str | None:
    """Why describing cannot follow, or `None` when it can.

    THE GRAPH AND NOT THE PROFILE. `entrypoints.describe_concepts` builds its describer from the
    graph and the subject context alone — `approvals.UPSTREAM[KNOWLEDGE_GRAPH]` is empty and
    `entrypoints/descriptions._describer` exists to keep it that way — so gating it on the profile
    withheld the one derivation this chain calls mandatory in exactly the state it was
    written for: a workspace whose graph is its first artifact. It costs nothing extra
    either, since the embedder writes whatever is missing at the next `initialize`; the
    chain only moves that call earlier, which is what a chain is for.
    """
    if entrypoints.knowledge_graph_path(ws) is None:
        return "esta asignatura todavía no tiene grafo de conocimiento"
    return None


def _profile_approved(ws: Workspace) -> str | None:
    """Why the taggability review cannot follow, or `None` when it can.

    Taggability is judged against the profile's modalities and against real items, so the
    gate is `routers/jobs.NEEDS_APPROVED`'s: an approved profile. Built but unapproved is a
    skip, not an error.
    """
    reason = _profile_exists(ws)
    if reason is not None:
        return reason
    if approvals.Approvals(ws).state(approvals.EXEMPLARS_PROFILE)["status"] != "approved":
        return "el perfil de ejemplares aún no está aprobado"
    return None


def _indexable(ws: Workspace) -> str | None:
    """Why indexing cannot follow, or `None` when it can."""
    reason = _profile_exists(ws)
    if reason is not None:
        return reason
    if not ws.exemplars_bank_path.is_file():
        return "todavía no hay banco de ejemplares que indexar"
    return None


def _profile_exists(ws: Workspace) -> str | None:
    """Why a link that reads the exemplars profile cannot follow, or `None` when it can."""
    if entrypoints.exemplars_profile_path(ws) is None:
        return "esta asignatura todavía no tiene perfil de ejemplares"
    return None


REQUIRES = {
    "describe_concepts": _graph_exists,
    "review_taggability": _profile_approved,
    "index": _indexable,
}


def advance(runner, job: Job) -> None:
    """Queue the next link of the chain this job belongs to, skipping what cannot run yet.

    Only ever the next one: each job carries the rest of its chain in `params`, so the
    condition of every link is read when that link's turn comes and not before.
    """
    remaining = list(job.params.get("chain") or CHAINS.get(job.kind) or ())
    if not remaining:
        return

    ws = installation.workspace_for(job.workspace)
    while remaining:
        kind = remaining.pop(0)
        blocked = REQUIRES.get(kind, lambda _ws: None)(ws)
        label = JOB_LABELS.get(kind, kind)
        if blocked is not None:
            logger.info(f"[cadena] «{label}» se salta: {blocked}")
            continue
        runner.submit(
            kind,
            {"chain": remaining},
            workspace=job.workspace,
            user_id=job.user_id,
            user_name=job.user_name,
        )
        logger.info(f"[cadena] «{label}» encolado tras «{job.label}»")
        return

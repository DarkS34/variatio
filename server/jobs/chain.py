"""What follows a build on its own, and how far it may go.

A phase that HAS to happen should not be a button. Once the graph is built the descriptions
have to be written — without them no concept has a vector and tagging does not exist —, the
concepts that work as labels have to be decided, and the indices warmed, so the build that
leaves all three pending chains them.

What is NOT chained is whatever depends on an artifact that may not exist yet. Each link
declares its condition; if it does not hold the link is skipped, the log says so and the
chain goes on with the next one. In a freshly created workspace — graph first, no profile
yet — all three are skipped and the build ends at the graph.

A link that fails or is cancelled cuts the chain: `advance` is only called after a job that
finished well.
"""

from loguru import logger

from variatio import stages
from variatio.core.workspace import Workspace

from .. import review, settings
from .models import JOB_LABELS, Job

# What each job drags behind it. Only the graph build has a chain: it is the only one
# whose result leaves three mandatory derivations undone.
CHAINS: dict[str, tuple[str, ...]] = {
    "build_kg": ("describe_concepts", "review_taggability", "index"),
}


def _profile_exists(ws: Workspace) -> str | None:
    """Why describing cannot follow, or `None` when it can."""
    if stages.exemplars_profile_path(ws) is None:
        return "esta asignatura todavía no tiene perfil de ejemplares"
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
    if review.ReviewState(ws).state(review.EXEMPLARS_PROFILE)["status"] != "approved":
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


REQUIRES = {
    "describe_concepts": _profile_exists,
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

    ws = settings.workspace_for(job.workspace)
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

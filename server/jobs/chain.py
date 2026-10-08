"""What follows a job on its own, and how far it may go.

A phase that HAS to happen should not be a button. Two jobs leave mandatory work behind:

- The graph build. Without descriptions no concept has a vector and nothing can be tagged,
  so the build chains them.
- The taggability review, which heads every collection of the bank (2026-10-08, when the
  types of exercise and the bank became one step). The concepts that work as labels are
  decided against the APPROVED profile, the bank is extracted and tagged with them, and the
  indices are warmed: the teacher presses «Recoger el banco» once and the three run in
  order. The review is skipped inside its own handler when nothing it reads has changed
  (`server/taggability.py`); the chain goes on either way.

Each link declares its condition, and the condition is what the LINK ITSELF reads:
describing needs the graph, collecting the bank needs the profile and the graph approved and
a document to read, indexing needs a profile and a bank. If a condition does not hold the
link is skipped, the log says so and the chain goes on with the next one. The route that
queues the head checks the gates of every link first (`routers/jobs.gate_error`), so a skip
here is what a forced job or a state that moved while queued leaves.

A link that fails or is cancelled cuts the chain: `advance` is only called after a job that
finished well.
"""

from loguru import logger

from variatio import entrypoints
from variatio.core.workspace import Workspace

from .. import approvals, installation
from .catalogue import JOB_LABELS, Job

# What each job drags behind it.
CHAINS: dict[str, tuple[str, ...]] = {
    "build_kg": ("describe_concepts",),
    "review_taggability": ("build_bank", "index"),
}


def links(kind: str) -> tuple[str, ...]:
    """Return what a job of `kind` queues behind it when it heads its chain."""
    return CHAINS.get(kind, ())


def remaining(job: Job) -> tuple[str, ...]:
    """Return the links still to come after this job, as it carries them or as its kind does."""
    return tuple(job.params.get("chain") or links(job.kind))


def _graph_exists(ws: Workspace) -> str | None:
    """Why describing cannot follow, or `None` when it can.

    THE GRAPH AND NOT THE PROFILE. `entrypoints.describe_concepts` builds its describer from the
    graph and the subject context alone — `approvals.UPSTREAM[KNOWLEDGE_GRAPH]` is empty and
    `entrypoints/descriptions._describer` exists to keep it that way — so gating it on the profile
    withheld the one derivation this chain calls mandatory in exactly the state it was
    written for: a workspace whose graph is its first artifact.
    """
    if entrypoints.knowledge_graph_path(ws) is None:
        return "esta asignatura todavía no tiene grafo de conocimiento"
    return None


def _bank_buildable(ws: Workspace) -> str | None:
    """Why the bank cannot be collected after the review, or `None` when it can.

    The bank is extracted with the profile's schema and tagged with the graph's concepts, so
    both have to be approved — `GATES["build_bank"]`'s question — and its slot has to hold a
    document to extract from.
    """
    if not approvals.Approvals(ws).gate_open(approvals.EXEMPLARS_BANK):
        return "los tipos de ejercicio o el temario aún no están dados por buenos"
    if not approvals.raw_documents(ws, approvals.RAW_SOURCE[approvals.EXEMPLARS_BANK]):
        return "no hay ejercicios de los que recoger el banco"
    return None


def _indexable(ws: Workspace) -> str | None:
    """Why indexing cannot follow, or `None` when it can."""
    if entrypoints.exemplars_profile_path(ws) is None:
        return "esta asignatura todavía no tiene perfil de ejemplares"
    if not ws.exemplars_bank_path.is_file():
        return "todavía no hay banco de ejemplares que indexar"
    return None


REQUIRES = {
    "describe_concepts": _graph_exists,
    "build_bank": _bank_buildable,
    "index": _indexable,
}


def advance(runner, job: Job) -> None:
    """Queue the next link of the chain this job belongs to, skipping what cannot run yet.

    Only ever the next one: each job carries the rest of its chain in `params`, so the
    condition of every link is read when that link's turn comes and not before.
    """
    pending = list(remaining(job))
    if not pending:
        return

    ws = installation.workspace_for(job.workspace)
    while pending:
        kind = pending.pop(0)
        blocked = REQUIRES.get(kind, lambda _ws: None)(ws)
        label = JOB_LABELS.get(kind, kind)
        if blocked is not None:
            logger.info(f"[cadena] «{label}» se salta: {blocked}")
            continue
        runner.submit(
            kind,
            {"chain": pending},
            workspace=job.workspace,
            user_id=job.user_id,
            user_name=job.user_name,
        )
        logger.info(f"[cadena] «{label}» encolado tras «{job.label}»")
        return

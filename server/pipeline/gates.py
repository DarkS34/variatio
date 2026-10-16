"""What must be settled before a job kind may run: the chain's gates and a live transcription.

The route checks every link of a chain before queueing its head: a link the runner queues
has no route, so a closed gate behind the head would be skipped in silence.
"""

from variatio.core.workspace import Workspace

from .. import raw_data, singletons
from ..jobs.catalogue import JOB_ARTIFACT, SUBPROCESS_KINDS
from . import approvals
from . import chain as job_chain

# What the chain requires before a job kind is allowed to run.
GATES: dict[str, str | None] = {
    "build_profile": None,
    "build_kg": None,
    "build_bank": approvals.EXEMPLARS_BANK,
    "describe_concepts": None,
    "index": None,
    "tag": approvals.EXEMPLARS_BANK,
    "generate": "__all__",
    "evaluate": "__all__",
}

# `GATES` answers "are the UPSTREAM of X approved?", which is the question for building X.
# Taggability asks a different one — that a SPECIFIC artifact is approved, the profile its
# verdict is judged against — hence a table of its own. The graph's approval it needs too,
# since the review heads the bank's collection, comes from the link behind it: `build_bank`'s
# gate, which `gate_error` reads for every link of the chain.
NEEDS_APPROVED: dict[str, str] = {
    "review_taggability": approvals.EXEMPLARS_PROFILE,
}


def gate_error(ws: Workspace, kind: str) -> str | None:
    """Say in Spanish which steps have to be settled before `kind` may run, or nothing.

    Every link `kind` chains is checked too (`chain.links`): queued by the runner and
    not by this route, a link whose gate is closed would be skipped in silence, and
    «Recoger el banco» would decide the labels and collect nothing.

    It names the STATE and not a button: "Aprobar" is not a control any more — a stage is
    closed by moving on from it — so "aprueba primero" sent people looking for something
    that is not on the screen.
    """
    for link in (kind, *job_chain.links(kind)):
        error = _gate_error_of(ws, link)
        if error is not None:
            return error
    return None


def _gate_error_of(ws: Workspace, kind: str) -> str | None:
    """Say which steps have to be settled before one kind of job may run, or nothing."""
    needed = NEEDS_APPROVED.get(kind)
    if needed is not None:
        if singletons.approvals(ws).state(needed)["status"] != "approved":
            return f"Antes hay que dar por bueno: {approvals.LABELS[needed]}."

    gate = GATES.get(kind)
    if gate is None:
        return None
    state = singletons.approvals(ws)
    if gate == "__all__":
        if not state.generation_unlocked():
            pending = _pending_labels(ws)
            return f"Para crear ejercicios hay que dar antes por buenos: {', '.join(pending)}."
        return None
    if not state.gate_open(gate):
        blockers = _unapproved_upstream(state, gate)
        return f"Antes hay que dar por bueno: {', '.join(blockers)}."
    return None


def transcribing_slot(slug: str, kind: str) -> str | None:
    """Name the raw slot `kind` or a link it chains would read, while it is transcribed.

    Only the three builds read a slot (`SUBPROCESS_KINDS`); `tag` rewrites the bank from
    what is already in it. A transcription and a build of the same slot both write the
    same page cache, document by document, so they must not run at once — and the queue
    does not keep them apart, since on a hybrid engine they may sit on different lanes.
    The links count because the taggability review heads the bank's collection: refusing
    only the build would let the review run and the build behind it collide.
    This is NOT the transcription becoming a gate: a slot nobody is reading builds whether
    its pages are cached or not.
    """
    for link in (kind, *job_chain.links(kind)):
        if link not in SUBPROCESS_KINDS:
            continue
        slot = raw_data.slot_feeding(JOB_ARTIFACT.get(link))
        if slot is not None and singletons.transcribing(slug, slot) is not None:
            return slot
    return None


def transcription_error(ws: Workspace, kind: str) -> str | None:
    """Say in Spanish that the slot this build reads is being transcribed, or nothing."""
    slot = transcribing_slot(ws.slug, kind)
    if slot is None:
        return None
    label = raw_data.SLOTS[slot]["label"]
    return f"Se está leyendo «{label}»: espera a que termine antes de construir."


def _pending_labels(ws: Workspace) -> list[str]:
    """Name the stages of the chain that are not approved yet."""
    return [
        s["label"] for s in singletons.pipeline_snapshot(ws) if s["status"] != "approved"
    ]


def _unapproved_upstream(state, gate: str) -> list[str]:
    """Name the artifacts `gate` depends on that are not approved yet."""
    return [
        approvals.LABELS[up]
        for up in approvals.UPSTREAM[gate]
        if state.state(up)["status"] != "approved"
    ]

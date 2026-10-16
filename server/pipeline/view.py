"""One workspace's chain and the state of the shared queue, as `/api/pipeline` answers them.

The routes that change a stage answer with it too (the bank's, the syllabus's, the
profile's and the generation's), so the bar follows from the answer.
"""

from collections.abc import Callable

from sqlalchemy.exc import SQLAlchemyError

from .. import auth, singletons
from ..auth import features
from ..db.session import session_scope
from ..jobs import lanes as jobs_lanes
from ..jobs.catalogue import FEATURE_OF, Job
from . import approvals
from .gates import transcribing_slot

# The job that moves each stage forward, so the UI never has to hardcode it. The bank's is
# the taggability review, the head of its collection (`chain.py`): collecting it, or
# collecting it again, decides the labels before extracting with them.
NEXT_JOB = {
    approvals.EXEMPLARS_PROFILE: "build_profile",
    approvals.KNOWLEDGE_GRAPH: "build_kg",
    approvals.EXEMPLARS_BANK: "review_taggability",
}


def pipeline_payload(access: auth.Access) -> dict:
    """Answer one workspace's chain, and what the shared machine is doing behind it.

    The two halves are scoped differently on purpose: whether a lane is held, and by which
    job, is said to everyone — the machine is shared, so "somebody is building something"
    is true for everyone and hiding it leaves a queued job looking stuck; only the name of a
    job of a function closed to the account, or of another account's private job, stays
    back — while `current_job`, the waiting counts and the artifacts marked as building are
    statements about this instance and never leave it. Inside the instance they count what
    the account may see (`Job.seen_by`): another student's commission is neither the
    `current_job` nor the one a wait is measured against.
    """
    chain = singletons.pipeline_snapshot(access.ws)
    slug = access.ws.slug
    me = access.user.id
    for stage in chain:
        stage["build_job"] = NEXT_JOB[stage["artifact"]]
        # The slot this stage's build reads, while a transcription of it is live: what
        # the build button turns into "espera a que termine". A key, not a sentence, so
        # the client names the slot in its own language.
        stage["transcribing_slot"] = transcribing_slot(slug, stage["build_job"])
    waiting = [j for j in singletons.runner.pending(slug) if j.seen_by(me)]
    running = singletons.runner.running()
    # The oldest running job of THIS workspace: the oldest of the installation would blank
    # your own run for as long as somebody else's older one holds the other lane.
    ours = [j for j in running if j.workspace == slug and j.seen_by(me)]
    current = ours[0] if ours else None
    nameable = _nameable_for(access)
    lanes = {
        backend: _lane_payload(backend, slug, me, nameable) for backend in jobs_lanes.BACKENDS
    }
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


def _nameable_for(access: auth.Access) -> Callable[[Job], bool]:
    """Build the test of whether a lane's holder may be named to this account.

    Another account's private job is never named (`Job.seen_by`). A job of an optional
    function (`catalogue.FEATURE_OF`: a comparison, a tutor's turn) is named only to an account
    that function is open to: to anybody else the lane is busy with something, which is the
    whole of what their wait needs. The database is read at most once per function and per
    payload, and only when such a job holds a lane; a read that fails names nothing, because
    this payload also answers writes that already happened.
    """
    known: dict[str, bool] = {}

    def nameable(job: Job) -> bool:
        """Say whether this job may be named to the account asking."""
        if not job.seen_by(access.user.id):
            return False
        feature = FEATURE_OF.get(job.kind)
        if feature is None:
            return True
        if feature not in known:
            try:
                with session_scope() as session:
                    known[feature] = features.enabled(
                        session, access.user, feature, access.workspace
                    )
            except SQLAlchemyError:
                known[feature] = False
        return known[feature]

    return nameable


def _lane_payload(
    backend: str, slug: str, me: int, nameable: Callable[[Job], bool]
) -> dict:
    """Report one lane globally, and this workspace's own place in its queue.

    The machine and the quota belong to the installation, so `busy` and what is holding the
    lane are said to everyone: a queued job of yours that looks stuck has an honest reason,
    and no per-workspace number can express it. `mine`, `queued` and `ahead` are the scoped
    half. The holder travels as its `kind`, which the client names in the reader's language,
    and as the server's `label` beside it for an older client; both are left out when the
    holder belongs to a function closed to the account (`_nameable_for`).

    `busy` means "this lane is FULL" and not "something is running on it" — it is what
    every reader uses to predict a wait, and on a lane of capacity 4 a third job waits for
    nothing. `running` and `capacity` report the activity itself; at capacity 1 the two
    readings coincide, so a single-engine installation is unchanged.
    """
    holders = singletons.runner.holders_in(backend)
    room = jobs_lanes.capacity(backend)
    waiting = [j for j in singletons.runner.pending() if backend in j.backends]
    mine = [j for j in waiting if j.workspace == slug and j.seen_by(me)]
    ahead = None
    if mine:
        # How many jobs have to finish before mine starts: everything already holding a
        # slot, plus everything queued in front of it, less the room there is. At capacity
        # 1 this is exactly the old "those in front, plus one if the lane is held".
        first = [j.id for j in waiting].index(mine[0].id)
        ahead = max(0, len(holders) + first + 1 - room)
    named = holders[0] if holders and nameable(holders[0]) else None
    return {
        "busy": len(holders) >= room,
        "running": len(holders),
        "capacity": room,
        "mine": any(j.workspace == slug and j.seen_by(me) for j in holders),
        "kind": named.kind if named is not None else None,
        "label": named.label if named is not None else None,
        "queued": len(mine),
        "ahead": ahead,
    }


def _queue_ahead(waiting: list, running: list) -> int | None:
    """Count what has to finish before this workspace's first queued job starts.

    Clamped at zero: the dispatcher can start `waiting[0]` between the two reads, and
    `queue_position` then answers 0 — "-1 por delante" is not a count.
    """
    if not waiting:
        return None
    first = set(waiting[0].backends)
    blocking = sum(1 for j in running if first & set(j.backends))
    return max(0, blocking + singletons.runner.queue_position(waiting[0].id) - 1)

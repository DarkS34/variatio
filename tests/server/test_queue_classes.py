"""Who goes first in the queue, and what a commission may ask for.

Three classes by how long a kind lasts and who waits for it — a tutor's turn, then a batch,
then everything built in the background — with aging so nothing waits for ever, and a cap of
background jobs on the local lane that aging does not lift. Then the bounds of a commission:
one live batch per account and subject, and a student's size and day.

The runner here is never started: each test asks it what would go out next, with the clock
and the capacities it means, and starts jobs by hand. Nothing depends on the installation's
settings — every one a test reads is pinned.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import installation, singletons
from server.auth.deps import Access
from server.db.models import EDITOR, VIEWER, Base
from server.jobs import catalogue, lanes, priority
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from server.routers import jobs as jobs_router
from variatio import config

LOCAL = lanes.LOCAL
REMOTE = lanes.REMOTE
KINDS = ("tutor_turn", "generate", "evaluate", "build_kg", "tag", "transcribe", "algo_nuevo")


class Clock:
    """A clock the test moves by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def rules(monkeypatch):
    """The defaults of the plan, pinned: 90 s for a batch, 600 s for a build, two of them."""
    monkeypatch.setattr(config, "QUEUE_PROMOTE_B_AFTER_SECONDS", 90, raising=False)
    monkeypatch.setattr(config, "QUEUE_PROMOTE_C_AFTER_SECONDS", 600, raising=False)
    monkeypatch.setattr(config, "LOCAL_MAX_BACKGROUND_JOBS", 2, raising=False)
    monkeypatch.setitem(catalogue.JOB_CLASS, "tutor_turn", catalogue.INTERACTIVE)


@pytest.fixture
def runner(monkeypatch, rules):
    """A runner that queues, never dispatches, and puts every job on the local lane."""
    monkeypatch.setattr(lanes, "backends_for", lambda kind, params=None: frozenset({LOCAL}))
    queue = JobRunner(EventBus(buffer_size=500), {kind: lambda job, control: {} for kind in KINDS})
    queue._clock = Clock()
    return queue


def _queue(runner: JobRunner, kind: str, at: float | None = None, workspace: str = "aula"):
    if at is not None:
        runner._clock.now = at
    return runner.submit(kind, {}, workspace=workspace)


def _next(runner: JobRunner, local: int = 1, remote: int = 1) -> str | None:
    with runner._lock:
        return runner._next_ready({LOCAL: local, REMOTE: remote})


def _start(runner: JobRunner, job_id: str) -> None:
    """Do what the dispatcher does to a job it starts, without a thread to run it."""
    with runner._lock:
        job = runner._jobs[job_id]
        job.status = "running"
        for backend in job.backends:
            runner._holders.setdefault(backend, []).append(job.id)
        runner._restamp()


def _kinds_in_order(runner: JobRunner, local: int = 1) -> list[str]:
    """Start jobs one by one in the order the queue gives them, on a lane freed after each."""
    out = []
    while (job_id := _next(runner, local)) is not None:
        out.append(runner.get(job_id).kind)
        _start(runner, job_id)
        with runner._lock:
            runner._holders.clear()
    return out


# THE ORDER --------------------------------------------------------------------------------


def test_a_turn_overtakes_a_batch_and_a_build_and_a_batch_overtakes_a_build(runner):
    _queue(runner, "build_kg")
    _queue(runner, "generate")
    _queue(runner, "tutor_turn")

    assert _kinds_in_order(runner) == ["tutor_turn", "generate", "build_kg"]


def test_inside_a_class_the_order_of_arrival_holds(runner):
    first = _queue(runner, "generate")
    _queue(runner, "evaluate")

    assert _next(runner) == first.id


def test_a_batch_that_waited_its_term_overtakes_a_turn_just_arrived(runner):
    batch = _queue(runner, "generate", at=0)
    turn = _queue(runner, "tutor_turn", at=89)
    assert _next(runner) == turn.id

    runner._clock.now = 90
    assert _next(runner) == batch.id


def test_a_build_that_waited_690_seconds_overtakes_both(runner):
    build = _queue(runner, "build_kg", at=0)
    _queue(runner, "generate", at=600)
    _queue(runner, "tutor_turn", at=689)
    assert _next(runner) != build.id

    runner._clock.now = 690
    assert _kinds_in_order(runner) == ["build_kg", "generate", "tutor_turn"]


def test_a_kind_nobody_classified_is_background():
    assert priority.class_of("algo_nuevo") == catalogue.BACKGROUND
    assert priority.class_of("generate") == catalogue.BATCH


def test_aging_is_read_live_from_the_settings(runner, monkeypatch):
    batch = _queue(runner, "generate", at=0)
    _queue(runner, "tutor_turn", at=10)
    monkeypatch.setattr(config, "QUEUE_PROMOTE_B_AFTER_SECONDS", 5)

    assert _next(runner) == batch.id


# THE CAP OF BACKGROUND JOBS ON THE LOCAL LANE ---------------------------------------------


def test_a_third_background_job_waits_with_room_on_the_lane(runner):
    builds = [_queue(runner, kind) for kind in ("build_kg", "tag", "transcribe")]
    for job in builds[:2]:
        assert _next(runner, local=3) == job.id
        _start(runner, job.id)

    assert _next(runner, local=3) is None


def test_aging_does_not_lift_the_cap(runner):
    builds = [_queue(runner, kind, at=0) for kind in ("build_kg", "tag", "transcribe")]
    for job in builds[:2]:
        _start(runner, job.id)

    runner._clock.now = 100_000
    assert _next(runner, local=3) is None


def test_the_slot_the_cap_keeps_goes_to_a_batch(runner):
    builds = [_queue(runner, kind) for kind in ("build_kg", "tag", "transcribe")]
    for job in builds[:2]:
        _start(runner, job.id)
    batch = _queue(runner, "generate")

    assert _next(runner, local=3) == batch.id


def test_with_one_slot_the_cap_never_acts(runner):
    build = _queue(runner, "build_kg")

    assert _next(runner, local=1) == build.id


# WHERE A JOB STANDS -----------------------------------------------------------------------


def test_a_position_counts_what_goes_out_first(runner):
    holder = _queue(runner, "tag", at=0)
    _start(runner, holder.id)
    build = _queue(runner, "build_kg", at=1)
    batch = _queue(runner, "generate", at=2)
    turn = _queue(runner, "tutor_turn", at=3)

    positions = {job.kind: runner.queue_position(job.id) for job in (build, batch, turn)}
    assert positions == {"tutor_turn": 1, "generate": 2, "build_kg": 3}


def test_a_position_follows_aging(runner):
    holder = _queue(runner, "tag", at=0)
    _start(runner, holder.id)
    build = _queue(runner, "build_kg", at=0)
    batch = _queue(runner, "generate", at=600)
    turn = _queue(runner, "tutor_turn", at=690)

    assert [runner.queue_position(j.id) for j in (build, batch, turn)] == [1, 2, 3]


def test_a_position_counts_only_what_shares_a_lane(runner, monkeypatch):
    monkeypatch.setattr(
        lanes,
        "backends_for",
        lambda kind, params=None: frozenset({REMOTE if kind == "generate" else LOCAL}),
    )
    _queue(runner, "tutor_turn")
    batch = _queue(runner, "generate")

    assert runner.queue_position(batch.id) == 1


def test_the_pending_list_is_in_the_order_jobs_go_out(runner):
    _queue(runner, "build_kg")
    _queue(runner, "generate")
    _queue(runner, "tutor_turn")

    assert [job.kind for job in runner.pending()] == ["tutor_turn", "generate", "build_kg"]


# WHAT A COMMISSION MAY ASK FOR ------------------------------------------------------------

ANA = 1


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def queue(monkeypatch, runner):
    """The route over the runner above, with every gate of the chain open."""
    monkeypatch.setattr(singletons, "runner", runner)
    monkeypatch.setattr(jobs_router.inference, "is_available", lambda: True)
    monkeypatch.setattr(jobs_router, "gate_error", lambda ws, kind: None)
    monkeypatch.setattr(jobs_router, "transcription_error", lambda ws, kind: None)
    monkeypatch.setattr(jobs_router.entrypoints, "resolve_generation_model", lambda name: "m")
    monkeypatch.setattr(config, "GENERATION_MAX_ITEMS", 20)
    monkeypatch.setattr(config, "GENERATION_STUDENT_MAX_ITEMS", 5)
    monkeypatch.setattr(config, "GENERATION_STUDENT_DAILY_ITEMS", None)
    return runner


def _access(role: str, workspace: str = "aula", user_id: int = ANA) -> Access:
    return Access(
        user=SimpleNamespace(id=user_id, name="Ana", is_admin=False),
        workspace=SimpleNamespace(id=1, slug=workspace, name=workspace),
        role=role,
        ws=installation.workspace_for(workspace),
    )


def _commission(db, role: str, n: int, workspace: str = "aula") -> dict:
    return jobs_router.submit(
        jobs_router.JobBody(kind="generate", params={"n": n}),
        access=_access(role, workspace),
        db=db,
    )


def _refused(db, role: str, n: int, workspace: str = "aula") -> HTTPException:
    with pytest.raises(HTTPException) as refused:
        _commission(db, role, n, workspace)
    return refused.value


def _finish(queue: JobRunner, answer: dict) -> None:
    queue.cancel(answer["job"]["id"])


def test_one_live_batch_per_account_and_subject(queue, db):
    _commission(db, EDITOR, 3)

    refused = _refused(db, EDITOR, 3)
    assert refused.status_code == 409
    assert refused.headers == {"X-Error-Code": "generation_busy"}
    assert _commission(db, EDITOR, 3, workspace="otra")["job"]["kind"] == "generate"


def test_a_batch_that_ended_frees_the_subject(queue, db):
    _finish(queue, _commission(db, EDITOR, 3))

    assert _commission(db, EDITOR, 3)["job"]["kind"] == "generate"


def test_a_student_asks_for_five_at_most_and_a_teacher_for_twenty(queue, db):
    refused = _refused(db, VIEWER, 8)
    assert refused.status_code == 422
    assert "5" in refused.detail

    assert _commission(db, EDITOR, 20)["job"]["kind"] == "generate"


def test_a_students_day_counts_across_subjects(queue, db, monkeypatch):
    monkeypatch.setattr(config, "GENERATION_STUDENT_DAILY_ITEMS", 10)
    _finish(queue, _commission(db, VIEWER, 5))
    _finish(queue, _commission(db, VIEWER, 5, workspace="otra"))

    refused = _refused(db, VIEWER, 5)
    assert refused.status_code == 429
    assert refused.headers["X-Error-Code"] == "generation_daily_limit"
    assert int(refused.headers["Retry-After"]) > 0


def test_a_student_with_some_left_is_told_how_many(queue, db, monkeypatch):
    monkeypatch.setattr(config, "GENERATION_STUDENT_DAILY_ITEMS", 10)
    _finish(queue, _commission(db, VIEWER, 5))
    _finish(queue, _commission(db, VIEWER, 3))

    refused = _refused(db, VIEWER, 5)
    assert refused.status_code == 422
    assert "te quedan 2" in refused.detail
    assert _commission(db, VIEWER, 2)["job"]["kind"] == "generate"


def test_a_cancelled_batch_gives_nothing_back(queue, db, monkeypatch):
    monkeypatch.setattr(config, "GENERATION_STUDENT_DAILY_ITEMS", 5)
    _finish(queue, _commission(db, VIEWER, 5))

    assert _refused(db, VIEWER, 1).status_code == 429


def test_a_teacher_has_no_daily_limit(queue, db, monkeypatch):
    monkeypatch.setattr(config, "GENERATION_STUDENT_DAILY_ITEMS", 5)
    _finish(queue, _commission(db, EDITOR, 20))

    assert _commission(db, EDITOR, 20)["job"]["kind"] == "generate"


def test_the_allowance_says_what_the_form_may_offer(queue, db, monkeypatch):
    monkeypatch.setattr(config, "GENERATION_STUDENT_DAILY_ITEMS", 10)
    _finish(queue, _commission(db, VIEWER, 4))

    assert jobs_router.allowance(access=_access(VIEWER), db=db) == {
        "max_items": 5,
        "daily_items": 10,
        "used_today": 4,
    }
    assert jobs_router.allowance(access=_access(EDITOR), db=db) == {
        "max_items": 20,
        "daily_items": None,
        "used_today": 0,
    }


def test_a_students_ceiling_never_passes_everybodys(queue, db, monkeypatch):
    monkeypatch.setattr(config, "GENERATION_STUDENT_MAX_ITEMS", 50)

    assert jobs_router.max_items(student=True) == 20

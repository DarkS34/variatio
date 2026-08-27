"""Two lanes, one queue, and what may overtake what.

The point of the whole thing is the first test: a local job and a remote one run at the
same time. Everything else is the price of that — within a lane the order of arrival still
holds, a job that needs both lanes is not overtaken for ever by jobs that need one, and two
jobs running side by side do not write into each other's event stream.
"""

import threading
import time

import pytest
from loguru import logger

from server.jobs import lanes
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from variatio.core import progress

LOCAL = lanes.LOCAL
REMOTE = lanes.REMOTE

WAIT = 3.0


def _await(condition) -> bool:
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def _await_events(bus: EventBus, kind: str, count: int, match=None) -> list[dict]:
    found: list[dict] = []

    def enough() -> bool:
        found.clear()
        events, _ = bus.replay(0)
        found.extend(
            e for e in events if e["kind"] == kind and (match is None or match(e))
        )
        return len(found) >= count

    assert _await(enough), f"esperaba {count} evento(s) «{kind}», llegaron {len(found)}"
    return found


class Fixture:
    """A runner whose jobs block until the test lets them finish."""

    def __init__(self, bus: EventBus, reservations: dict[str, set[str]]):
        self.bus = bus
        self.started: dict[str, threading.Event] = {}
        self.release: dict[str, threading.Event] = {}
        self.finished: list[str] = []
        self._lock = threading.Lock()
        handlers = {kind: self._handler for kind in reservations}
        self.runner = JobRunner(bus, handlers)
        self.reservations = reservations
        for kind in reservations:
            self.started[kind] = threading.Event()
            self.release[kind] = threading.Event()

    def _handler(self, job, control) -> dict:
        self.started[job.kind].set()
        self.release[job.kind].wait(WAIT)
        with self._lock:
            self.finished.append(job.kind)
        return {"kind": job.kind}

    def submit(self, kind: str, workspace: str = "aula"):
        return self.runner.submit(kind, {}, workspace=workspace)

    def wait_started(self, kind: str) -> bool:
        return self.started[kind].wait(WAIT)

    def let_go(self, *kinds: str) -> None:
        for kind in kinds:
            self.release[kind].set()


@pytest.fixture
def make(monkeypatch):
    monkeypatch.setattr(EventBus, "_append_jsonl", lambda *a, **k: None)
    built: list[Fixture] = []

    def factory(reservations: dict[str, set[str]]) -> Fixture:
        monkeypatch.setattr(
            lanes,
            "backends_for",
            lambda kind, params=None: frozenset(reservations.get(kind, set())),
        )
        fixture = Fixture(EventBus(), reservations)
        fixture.runner.start()
        built.append(fixture)
        return fixture

    yield factory
    for fixture in built:
        for event in fixture.release.values():
            event.set()
        fixture.runner.shutdown(timeout=1.0)


# THE POINT -------------------------------------------------------------------------------


def test_two_jobs_of_disjoint_lanes_run_at_the_same_time(make):
    f = make({"aqui": {LOCAL}, "alla": {REMOTE}})
    f.submit("aqui")
    f.submit("alla")

    assert f.wait_started("aqui")
    assert f.wait_started("alla")
    assert {j.kind for j in f.runner.running()} == {"aqui", "alla"}
    assert f.runner.current_in(LOCAL).kind == "aqui"
    assert f.runner.current_in(REMOTE).kind == "alla"


def test_two_jobs_of_the_same_lane_do_not(make):
    f = make({"uno": {LOCAL}, "dos": {LOCAL}})
    f.submit("uno")
    second = f.submit("dos")

    assert f.wait_started("uno")
    assert not f.started["dos"].wait(0.4)
    assert second.status == "queued"
    assert f.runner.queue_position(second.id) == 1

    f.let_go("uno")
    assert f.wait_started("dos")


def test_a_job_that_reserves_nothing_never_waits(make):
    f = make({"pesado": {LOCAL, REMOTE}, "libre": set()})
    f.submit("pesado")
    assert f.wait_started("pesado")

    f.submit("libre")
    assert f.wait_started("libre")


# ORDER -----------------------------------------------------------------------------------


def test_the_order_of_arrival_holds_inside_a_lane(make):
    f = make({"a": {LOCAL}, "b": {LOCAL}, "c": {LOCAL}})
    f.submit("a")
    f.submit("b")
    f.submit("c")

    assert f.wait_started("a")
    f.let_go("a")
    assert f.wait_started("b")
    assert not f.started["c"].wait(0.2)
    f.let_go("b")
    assert f.wait_started("c")
    f.let_go("c")

    assert _await(lambda: len(f.finished) == 3)
    assert f.finished == ["a", "b", "c"]


# A job needing both lanes has to be able to get them. Without the claim a single-lane job
# arriving later would take the free lane every time and the two-lane job would starve.
def test_a_blocked_job_holds_its_lanes_against_what_is_behind_it(make):
    f = make({"local": {LOCAL}, "ambos": {LOCAL, REMOTE}, "remoto": {REMOTE}})
    f.submit("local")
    assert f.wait_started("local")

    both = f.submit("ambos")
    later = f.submit("remoto")
    assert not f.started["remoto"].wait(0.4)
    assert later.status == "queued"

    f.let_go("local")
    assert f.wait_started("ambos")
    assert not f.started["remoto"].wait(0.2)
    f.let_go("ambos")
    assert f.wait_started("remoto")
    assert both.status == "succeeded"


def test_a_queue_position_counts_only_what_shares_a_lane(make):
    f = make({"local": {LOCAL}, "otro_local": {LOCAL}, "remoto": {REMOTE}})
    f.submit("local")
    assert f.wait_started("local")

    queued_local = f.submit("otro_local")
    queued_remote = f.submit("remoto")
    assert f.wait_started("remoto")

    assert f.runner.queue_position(queued_local.id) == 1
    assert f.runner.queue_position(queued_remote.id) == 0
    assert queued_local.to_dict()["queue_position"] == 1
    assert queued_local.to_dict()["backends"] == [LOCAL]


# THE CLOCK -------------------------------------------------------------------------------


# Deliberate: the GPU is not released under a purely remote job, because the embedder and
# the guardrail are excluded from the lane calculation and both are local.
def test_the_idle_clock_counts_every_lane(make):
    f = make({"remoto": {REMOTE}})
    f.submit("remoto")
    assert f.wait_started("remoto")

    assert f.runner.idle_seconds() == 0.0
    assert f.runner.is_busy() is True


# ISOLATION -------------------------------------------------------------------------------


def test_two_concurrent_jobs_do_not_share_an_emitter(make):
    f = make({"aqui": {LOCAL}, "alla": {REMOTE}})
    barrier = threading.Barrier(2, timeout=WAIT)

    def handler(job, control) -> dict:
        f.started[job.kind].set()
        # Both inside their handler at once: whichever emitter a ContextVar leaked would
        # be the other one's.
        barrier.wait()
        progress.emit("marca", quien=job.kind)
        return {}

    f.runner.handlers = {"aqui": handler, "alla": handler}
    first = f.submit("aqui")
    second = f.submit("alla")
    assert f.wait_started("aqui")
    assert f.wait_started("alla")

    marks = _await_events(f.bus, "marca", 2)
    assert {e["job_id"]: e["quien"] for e in marks} == {
        first.id: "aqui",
        second.id: "alla",
    }


def test_two_concurrent_jobs_do_not_share_a_log_drawer(make):
    f = make({"aqui": {LOCAL}, "alla": {REMOTE}})
    barrier = threading.Barrier(2, timeout=WAIT)

    def handler(job, control) -> dict:
        f.started[job.kind].set()
        barrier.wait()
        logger.info(f"linea de {job.kind}")
        return {}

    f.runner.handlers = {"aqui": handler, "alla": handler}
    first = f.submit("aqui")
    second = f.submit("alla")
    assert f.wait_started("aqui")
    assert f.wait_started("alla")

    logs = _await_events(f.bus, "log", 2, match=lambda e: "linea de" in e["message"])
    assert {e["job_id"]: e["message"] for e in logs} == {
        first.id: "linea de aqui",
        second.id: "linea de alla",
    }

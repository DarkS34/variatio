"""Two lanes, one queue, and what may overtake what.

The point of the whole thing is the first test: a local job and a remote one run at the
same time. Everything else is the price of that — within a lane the order of arrival still
holds, a job that needs both lanes is not overtaken for ever by jobs that need one, and two
jobs running side by side do not write into each other's event stream.

A lane also has a CAPACITY, and the two lanes answer that differently: local is one and
cannot be raised, because the GPU is one, while remote is a setting, because Cerebras is a
rolling quota and the quota is administered call by call in the ledger. Every test here
pins the capacity it means rather than inheriting the installation's — the default is
whatever `CEREBRAS_MAX_CONCURRENT_JOBS` happens to be set to, and a test that reads it is
measuring the configuration instead of the queue.
"""

import threading
import time

import pytest
from loguru import logger

from server.jobs import lanes
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from variatio import config
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

    def factory(reservations: dict[str, set[str]], remote: int = 1) -> Fixture:
        monkeypatch.setattr(config, "CEREBRAS_MAX_CONCURRENT_JOBS", remote, raising=False)
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


# CAPACITY --------------------------------------------------------------------------------

# What the whole change is for: two people asking Cerebras for something at the same time
# get it at the same time. The quota they share is administered in the ledger, call by call.
def test_two_remote_jobs_run_at_the_same_time_when_the_lane_has_room(make):
    f = make({"suyo": {REMOTE}, "mio": {REMOTE}}, remote=2)
    f.submit("suyo", workspace="aula")
    f.submit("mio", workspace="taller")

    assert f.wait_started("suyo")
    assert f.wait_started("mio")
    assert {j.kind for j in f.runner.running()} == {"suyo", "mio"}
    assert len(f.runner.holders_in(REMOTE)) == 2


def test_the_remote_lane_still_stops_at_its_capacity(make):
    f = make({"a": {REMOTE}, "b": {REMOTE}, "c": {REMOTE}}, remote=2)
    f.submit("a")
    f.submit("b")
    third = f.submit("c")

    assert f.wait_started("a")
    assert f.wait_started("b")
    assert not f.started["c"].wait(0.4)
    assert third.status == "queued"

    f.let_go("a")
    assert f.wait_started("c")


# The GPU is one whatever the setting says: the capacity belongs to the remote lane alone,
# and raising it must not let two jobs onto the machine that would only swap weights.
def test_the_local_lane_has_no_capacity_to_raise(make):
    f = make({"uno": {LOCAL}, "dos": {LOCAL}}, remote=8)
    f.submit("uno")
    second = f.submit("dos")

    assert f.wait_started("uno")
    assert not f.started["dos"].wait(0.4)
    assert second.status == "queued"


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


# The same rule with room to spare: what a blocked job holds is ONE SLOT of each of its
# lanes, not the lane itself. With two remote slots and the two-lane job holding one, a
# remote job behind it still gets the other — and the two-lane job still gets its own back
# the moment the GPU frees up, which is the starvation the claim exists to prevent.
def test_a_blocked_job_holds_a_slot_and_not_the_whole_lane(make):
    f = make({"local": {LOCAL}, "ambos": {LOCAL, REMOTE}, "remoto": {REMOTE}}, remote=2)
    f.submit("local")
    assert f.wait_started("local")

    f.submit("ambos")
    f.submit("remoto")
    assert f.wait_started("remoto")

    f.let_go("local")
    assert f.wait_started("ambos")


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

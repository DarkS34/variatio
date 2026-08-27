"""What `GET /api/pipeline` says about each lane.

The rule the payload has to keep is the old one, now said twice: the machine is reported
globally — a lane is busy, and with what — while everything about *your* work is scoped to
your workspace. So `busy` and `label` speak about another instance's job and `mine`,
`queued` and `ahead` never do.
"""

import threading
import time
from types import SimpleNamespace

import pytest

from server import runtime
from server.jobs import lanes
from server.jobs.bus import EventBus
from server.jobs.runner import JobRunner
from server.routers.pipeline import pipeline_payload

LOCAL = lanes.LOCAL
REMOTE = lanes.REMOTE

CHAIN = [
    {"artifact": "exemplars_profile", "status": "approved"},
    {"artifact": "knowledge_graph", "status": "approved"},
    {"artifact": "exemplars_bank", "status": "approved"},
]

RESERVATIONS = {"local": {LOCAL}, "remoto": {REMOTE}}


@pytest.fixture
def stand(monkeypatch):
    monkeypatch.setattr(EventBus, "_append_jsonl", lambda *a, **k: None)
    monkeypatch.setattr(runtime, "pipeline_snapshot", lambda ws: [dict(s) for s in CHAIN])
    monkeypatch.setattr(
        lanes,
        "backends_for",
        lambda kind, params=None: frozenset(RESERVATIONS.get(kind, set())),
    )

    started: dict[str, threading.Event] = {k: threading.Event() for k in RESERVATIONS}
    release = threading.Event()

    def handler(job, control) -> dict:
        started[job.kind].set()
        release.wait(3.0)
        return {}

    runner = JobRunner(EventBus(), {kind: handler for kind in RESERVATIONS})
    monkeypatch.setattr(runtime, "runner", runner)
    runner.start()
    yield SimpleNamespace(runner=runner, started=started, release=release)
    release.set()
    runner.shutdown(timeout=1.0)


def _access(slug: str):
    return SimpleNamespace(ws=SimpleNamespace(slug=slug))


def _wait(event: threading.Event) -> None:
    assert event.wait(3.0)


def test_an_idle_installation_reports_both_lanes_free(stand):
    payload = pipeline_payload(_access("aula"))

    assert set(payload) >= {
        "stages",
        "generation_unlocked",
        "current_job",
        "queued",
        "queue_length",
        "queue_ahead",
        "engine_busy",
        "engine_busy_elsewhere",
        "lanes",
    }
    assert payload["lanes"] == {
        LOCAL: {"busy": False, "mine": False, "label": None, "queued": 0, "ahead": None},
        REMOTE: {"busy": False, "mine": False, "label": None, "queued": 0, "ahead": None},
    }
    assert payload["engine_busy"] is False
    assert payload["queue_length"] == 0


def test_a_busy_lane_is_reported_to_everyone_and_owned_by_one(stand):
    stand.runner.submit("local", {}, workspace="taller")
    _wait(stand.started["local"])

    mine = pipeline_payload(_access("aula"))
    theirs = pipeline_payload(_access("taller"))

    assert mine["lanes"][LOCAL]["busy"] is True
    assert mine["lanes"][LOCAL]["label"] == "local"
    assert mine["lanes"][LOCAL]["mine"] is False
    assert mine["current_job"] is None
    assert mine["engine_busy_elsewhere"] is True

    assert theirs["lanes"][LOCAL]["mine"] is True
    assert theirs["current_job"]["kind"] == "local"
    assert theirs["engine_busy_elsewhere"] is False

    # The other lane is free and says so, which is the whole reason the block exists.
    assert mine["lanes"][REMOTE]["busy"] is False


def test_what_is_waiting_is_counted_per_lane_and_only_mine(stand):
    stand.runner.submit("local", {}, workspace="taller")
    _wait(stand.started["local"])
    queued = stand.runner.submit("local", {}, workspace="aula")

    payload = pipeline_payload(_access("aula"))
    assert payload["lanes"][LOCAL]["queued"] == 1
    assert payload["lanes"][LOCAL]["ahead"] == 1
    assert payload["lanes"][REMOTE]["queued"] == 0
    assert payload["lanes"][REMOTE]["ahead"] is None
    assert payload["queued"] == 1
    assert payload["queue_length"] == 2
    assert queued.to_dict()["backends"] == [LOCAL]

    # And whoever is holding the lane has nothing waiting of their own.
    assert pipeline_payload(_access("taller"))["lanes"][LOCAL]["queued"] == 0


def test_a_job_on_the_free_lane_is_not_reported_as_waiting(stand):
    stand.runner.submit("local", {}, workspace="taller")
    _wait(stand.started["local"])
    stand.runner.submit("remoto", {}, workspace="aula")
    _wait(stand.started["remoto"])

    payload = pipeline_payload(_access("aula"))
    assert payload["lanes"][REMOTE]["busy"] is True
    assert payload["lanes"][REMOTE]["mine"] is True
    assert payload["lanes"][REMOTE]["queued"] == 0
    assert payload["queued"] == 0
    assert payload["queue_ahead"] is None
    assert payload["current_job"]["kind"] == "remoto"
    # Both lanes are busy and one of them is somebody else's.
    assert payload["engine_busy"] is True
    assert payload["engine_busy_elsewhere"] is True


def test_the_serialised_job_carries_its_lanes_and_its_place(stand):
    stand.runner.submit("local", {}, workspace="aula")
    _wait(stand.started["local"])
    second = stand.runner.submit("local", {}, workspace="aula")

    running = stand.runner.current().to_dict()
    assert running["backends"] == [LOCAL]
    assert running["queue_position"] == 0

    waiting = second.to_dict()
    assert waiting["backends"] == [LOCAL]
    assert waiting["queue_position"] == 1

    stand.release.set()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and second.status != "succeeded":
        time.sleep(0.02)
    assert second.to_dict()["queue_position"] == 0

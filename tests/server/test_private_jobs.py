"""A private job is its author's alone: a commission, a comparison, a tutor's turn.

With a class in a subject, the whole subject shares one event stream, and a commission
streamed every token of one student's statement into the other ninety-nine screens. So a
private job's events reach its author's socket and nobody else's, and the workspace's job
routes answer another account the same 404 as a job that does not exist — the rule the
exercises already keep. A build is the subject's, and every member still watches it.

A redacted job — one whose author is a student of the subject — also says nothing of the
bank while it runs: the prompt travels without its text and the chosen exemplars as ids.
"""

import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import auth, installation, singletons
from server.auth.deps import Access
from server.jobs import lanes
from server.jobs.bus import EventBus
from server.jobs.catalogue import PRIVATE_KINDS, Job
from server.jobs.runner import JobRunner
from server.routers import jobs as jobs_routes
from server.routers import ws as ws_routes
from server.routers.pipeline import pipeline_payload

ANA, LUIS = 1, 2


def _job(kind: str, user_id: int | None = ANA, **fields) -> Job:
    return Job(kind=kind, workspace="aula", user_id=user_id, **fields)


# THE BUS -----------------------------------------------------------------------------------


def test_a_private_jobs_events_reach_its_author_alone():
    bus = EventBus(buffer_size=50)
    bus.publish_job(_job("generate"), "token", {"text": "el enunciado de Ana"})

    mine, _ = bus.replay(0, workspace="aula", user_id=ANA)
    theirs, _ = bus.replay(0, workspace="aula", user_id=LUIS)
    nobody, _ = bus.replay(0, workspace="aula")

    assert [event["text"] for event in mine] == ["el enunciado de Ana"]
    assert theirs == []
    assert nobody == []


def test_a_builds_events_reach_every_member():
    bus = EventBus(buffer_size=50)
    bus.publish_job(_job("build_kg"), "step.started", {"id": "extract"})

    for user_id in (ANA, LUIS):
        events, _ = bus.replay(0, workspace="aula", user_id=user_id)
        assert [event["kind"] for event in events] == ["step.started"]


def test_a_private_job_with_no_author_is_seen_by_nobody():
    bus = EventBus(buffer_size=50)
    bus.publish_job(_job("evaluate", user_id=None), "job.queued", {})

    assert bus.replay(0, workspace="aula", user_id=ANA)[0] == []


def test_the_trusted_reader_still_sees_everything():
    """`workspace=None` is the CLI and the tests, which established their right already."""
    bus = EventBus(buffer_size=50)
    bus.publish_job(_job("generate"), "token", {"text": "x"})

    assert len(bus.replay(0)[0]) == 1


def test_the_stamp_is_the_filter_and_never_travels():
    event = EventBus(buffer_size=50).publish_job(_job("generate"), "token", {"text": "x"})

    assert event.private is True
    assert event.user_id == ANA
    assert "private" not in event.to_dict()
    assert "user_id" not in event.to_dict()


def test_the_tutors_turn_joins_the_private_kinds_when_it_is_installed():
    import server.app  # noqa: F401 - the composition root installs the tutor

    assert "tutor_turn" in PRIVATE_KINDS
    assert "tutor_criteria" not in PRIVATE_KINDS


# REDACTION ---------------------------------------------------------------------------------


def _publish_the_bank(bus: EventBus, job: Job) -> None:
    bus.publish_job(job, "few_shot", {
        "ids": ["C001"],
        "items": [{"id": "C001", "item": {"enunciado": "SOLUCIÓN DEL BANCO"}, "origin": "target"}],
        "concepts": ["Bucles"],
        "item_type": "ejercicio",
    })
    bus.publish_job(job, "prompt", {"index": 1, "text": "Ejemplo: SOLUCIÓN DEL BANCO"})


def test_a_redacted_job_names_its_exemplars_and_says_none_of_them():
    bus = EventBus(buffer_size=50)
    _publish_the_bank(bus, _job("generate", redacted=True))

    few_shot, prompt = bus.replay(0, workspace="aula", user_id=ANA)[0]

    assert few_shot["ids"] == ["C001"]
    assert few_shot["concepts"] == ["Bucles"]
    assert few_shot["item_type"] == "ejercicio"
    assert "items" not in few_shot
    # Still sent, because the screen starts a new item on it — but with nothing to read.
    assert prompt["kind"] == "prompt"
    assert prompt["index"] == 1
    assert "text" not in prompt


def test_the_record_on_disk_is_redacted_as_well():
    """The author reads it back through `GET /api/jobs/{id}/events`."""
    bus = EventBus(buffer_size=50)
    job = _job("generate", redacted=True)
    _publish_the_bank(bus, job)

    path = installation.workspace_for("aula").runs_dir / f"{job.id}.jsonl"
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert [line["kind"] for line in lines] == ["few_shot", "prompt"]
    assert "SOLUCIÓN DEL BANCO" not in path.read_text(encoding="utf-8")


def test_a_teachers_job_keeps_what_it_said():
    bus = EventBus(buffer_size=50)
    _publish_the_bank(bus, _job("generate"))

    few_shot, prompt = bus.replay(0, workspace="aula", user_id=ANA)[0]

    assert few_shot["items"][0]["item"]["enunciado"] == "SOLUCIÓN DEL BANCO"
    assert prompt["text"] == "Ejemplo: SOLUCIÓN DEL BANCO"


# THE ROUTES --------------------------------------------------------------------------------


@pytest.fixture
def queue(monkeypatch):
    """A runner whose jobs hold until the test ends, on lanes of room enough for all."""
    monkeypatch.setattr(EventBus, "_append_jsonl", lambda *a, **k: None)
    monkeypatch.setattr(lanes, "backends_for", lambda kind, params=None: frozenset())
    release = threading.Event()
    started: dict[str, threading.Event] = {}

    def handler(job, control) -> dict:
        started.setdefault(job.id, threading.Event()).set()
        release.wait(3.0)
        return {}

    bus = EventBus(buffer_size=200)
    runner = JobRunner(bus, {"generate": handler, "build_kg": handler})
    monkeypatch.setattr(singletons, "bus", bus)
    monkeypatch.setattr(singletons, "runner", runner)
    monkeypatch.setattr(
        singletons, "pipeline_snapshot", lambda ws: [{"artifact": "knowledge_graph", "status": "approved"}]
    )
    runner.start()
    yield SimpleNamespace(runner=runner, bus=bus, started=started)
    release.set()
    runner.shutdown(timeout=1.0)


def _access(user_id: int, role: str = "editor") -> Access:
    return Access(
        user=SimpleNamespace(id=user_id, name=f"cuenta {user_id}", username=f"u{user_id}"),
        workspace=SimpleNamespace(id=1, slug="aula", name="Aula"),
        role=role,
        ws=installation.workspace_for("aula"),
    )


def _client(user_id: int) -> TestClient:
    access = _access(user_id)
    app = FastAPI()
    app.include_router(jobs_routes.router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    return TestClient(app)


def _submit(queue, kind: str, user_id: int) -> Job:
    job = queue.runner.submit(kind, {}, workspace="aula", user_id=user_id)
    for _ in range(150):
        if job.status == "running":
            break
        threading.Event().wait(0.02)
    return job


def test_the_listing_leaves_out_another_accounts_commission(queue):
    hers = _submit(queue, "generate", ANA)
    build = _submit(queue, "build_kg", ANA)

    listed = {job["id"] for job in _client(LUIS).get("/api/jobs").json()["jobs"]}
    own = {job["id"] for job in _client(ANA).get("/api/jobs").json()["jobs"]}

    assert listed == {build.id}
    assert own == {hers.id, build.id}


@pytest.mark.parametrize("method,path", [
    ("get", "/api/jobs/{id}"),
    ("get", "/api/jobs/{id}/events"),
    ("delete", "/api/jobs/{id}"),
])
def test_another_accounts_commission_is_the_404_of_a_job_that_does_not_exist(queue, method, path):
    hers = _submit(queue, "generate", ANA)

    theirs = getattr(_client(LUIS), method)(path.format(id=hers.id))
    missing = getattr(_client(LUIS), method)(path.format(id="000000000000"))

    assert theirs.status_code == 404
    assert theirs.json() == {"detail": f"No existe el trabajo '{hers.id}'"}
    assert missing.status_code == 404
    assert hers.status == "running"


def test_the_author_reads_and_stops_their_own(queue):
    hers = _submit(queue, "generate", ANA)

    assert _client(ANA).get(f"/api/jobs/{hers.id}").status_code == 200
    assert _client(ANA).delete(f"/api/jobs/{hers.id}").json() == {"cancelled": True}


def test_a_build_is_everybodys_to_read(queue):
    build = _submit(queue, "build_kg", ANA)

    assert _client(LUIS).get(f"/api/jobs/{build.id}").status_code == 200


def test_current_names_neither_their_running_nor_their_queued_commission(queue, monkeypatch):
    _submit(queue, "generate", ANA)
    monkeypatch.setattr(lanes, "backends_for", lambda kind, params=None: frozenset({lanes.LOCAL}))
    queue.runner.submit("generate", {}, workspace="aula", user_id=ANA)
    queue.runner.submit("generate", {}, workspace="aula", user_id=ANA)

    theirs = _client(LUIS).get("/api/jobs/current").json()
    own = _client(ANA).get("/api/jobs/current").json()

    assert theirs["job"] is None
    assert theirs["queued"] == []
    assert own["job"]["kind"] == "generate"
    assert len(own["queued"]) == 1


def test_the_replay_route_carries_only_what_the_account_may_see(queue):
    hers = _submit(queue, "generate", ANA)
    queue.bus.publish_job(hers, "token", {"text": "solo de Ana"})

    theirs = _client(LUIS).get("/api/events").json()["events"]
    own = _client(ANA).get("/api/events").json()["events"]

    assert all(event["job_id"] != hers.id for event in theirs)
    assert any(event.get("text") == "solo de Ana" for event in own)


def test_the_socket_backlog_and_snapshot_leave_out_another_accounts_commission(queue):
    hers = _submit(queue, "generate", ANA)
    build = _submit(queue, "build_kg", ANA)

    replayed, _, _ = ws_routes._backlog(0, "aula", LUIS)
    snapshot = queue.runner.all(workspace="aula", for_user=LUIS)

    assert {event["job_id"] for event in replayed} == {build.id}
    assert [job.id for job in snapshot] == [build.id]
    assert hers.id in {job.id for job in queue.runner.all(workspace="aula", for_user=ANA)}


def test_a_lane_held_by_another_accounts_commission_is_busy_and_unnamed(queue, monkeypatch):
    monkeypatch.setattr(lanes, "backends_for", lambda kind, params=None: frozenset({lanes.LOCAL}))
    _submit(queue, "generate", ANA)

    theirs = pipeline_payload(_access(LUIS))
    own = pipeline_payload(_access(ANA))

    assert theirs["lanes"][lanes.LOCAL]["busy"] is True
    assert theirs["lanes"][lanes.LOCAL]["kind"] is None
    assert theirs["lanes"][lanes.LOCAL]["mine"] is False
    assert theirs["current_job"] is None
    assert own["lanes"][lanes.LOCAL]["kind"] == "generate"
    assert own["current_job"]["kind"] == "generate"


def test_a_wait_is_measured_against_ones_own_job(queue, monkeypatch):
    monkeypatch.setattr(lanes, "backends_for", lambda kind, params=None: frozenset({lanes.LOCAL}))
    _submit(queue, "build_kg", ANA)
    queue.runner.submit("generate", {}, workspace="aula", user_id=ANA)
    queue.runner.submit("generate", {}, workspace="aula", user_id=LUIS)

    lane = pipeline_payload(_access(LUIS))["lanes"][lanes.LOCAL]

    assert lane["queued"] == 1
    assert lane["ahead"] == 2

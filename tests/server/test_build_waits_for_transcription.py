"""A build does not start while the slot it reads is being transcribed.

Not a gate on the transcription being DONE — a slot nobody is reading builds whether its
pages are cached or not — but a refusal while a transcription of that slot is live: both
jobs write the same page cache document by document, and with two lanes the queue does not
keep them apart.
"""

import threading
from types import SimpleNamespace

import pytest

from server import singletons
from server.jobs import EventBus, JobRunner
from server.routers.jobs import transcribing_slot, transcription_error
from server.routers.pipeline import pipeline_payload

CHAIN = [
    {"artifact": "exemplars_profile", "status": "missing"},
    {"artifact": "knowledge_graph", "status": "missing"},
    {"artifact": "exemplars_bank", "status": "missing"},
]


@pytest.fixture
def stand(monkeypatch):
    monkeypatch.setattr(EventBus, "_append_jsonl", lambda *a, **k: None)
    monkeypatch.setattr(singletons, "pipeline_snapshot", lambda ws: [dict(s) for s in CHAIN])
    started = threading.Event()
    release = threading.Event()

    def handler(job, control) -> dict:
        started.set()
        release.wait(3.0)
        return {}

    runner = JobRunner(EventBus(), {"transcribe": handler})
    monkeypatch.setattr(singletons, "runner", runner)
    runner.start()
    yield SimpleNamespace(runner=runner, started=started, release=release)
    release.set()
    runner.shutdown(timeout=1.0)


def _ws(slug: str):
    return SimpleNamespace(slug=slug)


def _stages(slug: str) -> dict[str, str | None]:
    payload = pipeline_payload(SimpleNamespace(ws=_ws(slug)))
    return {s["artifact"]: s["transcribing_slot"] for s in payload["stages"]}


def test_nothing_is_transcribing_on_an_idle_installation(stand):
    assert transcribing_slot("aula", "build_profile") is None
    assert transcription_error(_ws("aula"), "build_profile") is None
    assert set(_stages("aula").values()) == {None}


def test_the_two_stages_reading_the_exemplars_wait_for_their_transcription(stand):
    stand.runner.submit("transcribe", {"slot": "exemplars"}, workspace="aula")
    assert stand.started.wait(3.0)

    assert transcribing_slot("aula", "build_profile") == "exemplars"
    assert transcribing_slot("aula", "build_bank") == "exemplars"
    # The graph reads the corpus, which nobody is touching.
    assert transcribing_slot("aula", "build_kg") is None
    assert _stages("aula") == {
        "exemplars_profile": "exemplars",
        "knowledge_graph": None,
        "exemplars_bank": "exemplars",
    }
    error = transcription_error(_ws("aula"), "build_profile")
    assert error is not None and "espera a que termine" in error


def test_a_waiting_transcription_counts_as_much_as_a_running_one(stand):
    stand.runner.submit("transcribe", {"slot": "exemplars"}, workspace="aula")
    assert stand.started.wait(3.0)
    # The second one queues behind the first on the same lane; it is about to write.
    stand.runner.submit("transcribe", {"slot": "corpus"}, workspace="aula")
    assert transcribing_slot("aula", "build_kg") == "corpus"


def test_another_workspace_is_not_held_up(stand):
    stand.runner.submit("transcribe", {"slot": "corpus"}, workspace="aula")
    assert stand.started.wait(3.0)
    assert transcribing_slot("taller", "build_kg") is None
    assert set(_stages("taller").values()) == {None}


def test_only_the_three_builds_read_a_slot(stand):
    stand.runner.submit("transcribe", {"slot": "exemplars"}, workspace="aula")
    assert stand.started.wait(3.0)
    for kind in ("tag", "index", "generate", "evaluate", "transcribe"):
        assert transcribing_slot("aula", kind) is None

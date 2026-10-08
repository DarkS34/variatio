"""The route checks every link of a chain before it queues the head.

The taggability review heads the bank's collection (`jobs/chain.py`); the links behind it are
queued by the runner and not by the route, so a link whose gate is closed would be skipped in
silence and «Recoger el banco» would decide the labels and collect nothing. The route answers
the head with the link's reason instead, and the same for a transcription of the slot a link
reads. While the head runs, the bank reads as building, so its step does not offer to
collect it a second time.
"""

import json
import threading
from types import SimpleNamespace

import pytest

from server import approvals, singletons
from server.jobs import EventBus, JobRunner
from server.routers.jobs import gate_error, transcribing_slot, transcription_error
from server.routers.pipeline import NEXT_JOB
from variatio.core.workspace import Workspace

from ..conftest import CHAIN_GRAPH

PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio",
            "description": "Uno cualquiera.",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "fields": {"enunciado": {"schema": {"type": "string"}, "description": "El texto."}},
        }
    }
}


@pytest.fixture
def aula(tmp_path) -> Workspace:
    ws = Workspace(tmp_path / "aula", slug="aula")
    ws.artifacts_dir.mkdir(parents=True)
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    ws.exemplars_profile_path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return ws


@pytest.fixture
def stand(monkeypatch):
    """A live runner whose jobs hold their lane until released."""
    started = threading.Event()
    release = threading.Event()

    def handler(job, control) -> dict:
        started.set()
        release.wait(3.0)
        return {}

    runner = JobRunner(EventBus(), {"transcribe": handler, "review_taggability": handler})
    monkeypatch.setattr(singletons, "runner", runner)
    runner.start()
    yield SimpleNamespace(runner=runner, started=started, release=release)
    release.set()
    runner.shutdown(timeout=1.0)


def test_the_bank_is_collected_by_its_review(aula):
    assert NEXT_JOB[approvals.EXEMPLARS_BANK] == "review_taggability"


def test_unsettled_types_refuse_the_collection(aula):
    error = gate_error(aula, "review_taggability")
    assert error == "Antes hay que dar por bueno: Tipos de ejercicio."


def test_an_unsettled_syllabus_refuses_it_too_through_the_extraction_behind(aula):
    approvals.Approvals(aula).approve(approvals.EXEMPLARS_PROFILE)

    assert gate_error(aula, "review_taggability") == "Antes hay que dar por bueno: Temario."


def test_with_both_settled_the_collection_goes(aula):
    approvals.Approvals(aula).approve(approvals.EXEMPLARS_PROFILE)
    approvals.Approvals(aula).approve(approvals.KNOWLEDGE_GRAPH)

    assert gate_error(aula, "review_taggability") is None


def test_the_graph_s_chain_adds_no_gate(aula):
    assert gate_error(aula, "build_kg") is None


def test_a_transcription_of_the_exercises_holds_the_whole_collection(stand, aula):
    stand.runner.submit("transcribe", {"slot": "exemplars"}, workspace="aula")
    assert stand.started.wait(3.0)

    assert transcribing_slot("aula", "review_taggability") == "exemplars"
    error = transcription_error(aula, "review_taggability")
    assert error is not None and "espera a que termine" in error


def test_a_transcription_of_the_notes_does_not(stand, aula):
    stand.runner.submit("transcribe", {"slot": "corpus"}, workspace="aula")
    assert stand.started.wait(3.0)

    assert transcribing_slot("aula", "review_taggability") is None


def test_the_bank_reads_as_building_while_its_review_runs(stand, aula):
    assert approvals.EXEMPLARS_BANK not in singletons.building(aula)

    stand.runner.submit("review_taggability", {}, workspace="aula")
    assert stand.started.wait(3.0)

    assert approvals.EXEMPLARS_BANK in singletons.building(aula)
    bank = next(s for s in singletons.pipeline_snapshot(aula) if s["artifact"] == "exemplars_bank")
    assert bank["status"] == "building"


def test_a_review_that_collects_nothing_marks_nothing(stand, aula):
    stand.runner.submit("review_taggability", {"chain": ["index"]}, workspace="aula")
    assert stand.started.wait(3.0)

    assert approvals.EXEMPLARS_BANK not in singletons.building(aula)


def test_the_chain_order_is_the_path_s(aula):
    assert approvals.ARTIFACTS == (
        approvals.KNOWLEDGE_GRAPH,
        approvals.EXEMPLARS_PROFILE,
        approvals.EXEMPLARS_BANK,
    )
    assert [s["artifact"] for s in singletons.pipeline_snapshot(aula)] == list(approvals.ARTIFACTS)

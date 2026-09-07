"""The stage that reviews taggability: what it demands, what it reads, what it returns."""

import json

import pytest

from variatio import entrypoints
from variatio.core.workspace import Workspace

from ..conftest import CHAIN_GRAPH, PROFILE


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path, "aula")
    workspace.instance_dir.mkdir(parents=True)
    return workspace


def write_graph(ws) -> None:
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")


def write_profile(ws) -> None:
    ws.exemplars_profile_path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")


def record(monkeypatch) -> list[tuple]:
    """Stand in for the model pass and keep what it was handed."""
    calls: list[tuple] = []

    def fake_review(graph, profile, prompts, bank=None, context=None, max_attempts=None):
        calls.append((graph, profile, prompts, bank, context))
        return ["Notación asintótica"]

    monkeypatch.setattr(entrypoints.taggability, "review", fake_review)
    return calls


def test_it_refuses_without_a_graph(ws):
    write_profile(ws)
    with pytest.raises(entrypoints.MissingArtifactError) as exc:
        entrypoints.review_taggability(ws)
    assert exc.value.artifact == entrypoints.KNOWLEDGE_GRAPH


def test_it_refuses_without_a_profile(ws):
    """The judgement is relative to the shapes of item, so the graph alone cannot answer."""
    write_graph(ws)
    with pytest.raises(entrypoints.MissingArtifactError) as exc:
        entrypoints.review_taggability(ws)
    assert exc.value.artifact == entrypoints.EXEMPLARS_PROFILE


def test_it_reports_the_verdict_with_the_size_of_the_graph(ws, monkeypatch):
    write_graph(ws)
    write_profile(ws)
    record(monkeypatch)

    assert entrypoints.review_taggability(ws) == {
        "non_taggable": ["Notación asintótica"],
        "concepts": 5,
    }


def test_it_hands_the_review_the_workspace_own_prompt_set(ws, monkeypatch):
    write_graph(ws)
    write_profile(ws)
    ws.locale_path.write_text(json.dumps({"prompt_language": "en"}), encoding="utf-8")
    calls = record(monkeypatch)

    entrypoints.review_taggability(ws)

    assert calls[0][2].LANGUAGE == "en"


def test_the_bank_is_evidence_and_never_a_condition(ws, monkeypatch):
    """A missing or corrupt bank costs the samples, never the review."""
    write_graph(ws)
    write_profile(ws)
    calls = record(monkeypatch)

    entrypoints.review_taggability(ws)
    ws.exemplars_bank_path.write_text("{ not json", encoding="utf-8")
    entrypoints.review_taggability(ws)

    assert [call[3] for call in calls] == [{}, {}]


def test_the_bank_reaches_the_review_when_it_is_there(ws, monkeypatch):
    write_graph(ws)
    write_profile(ws)
    bank = {"C001": {"enunciado": "Escribe una función recursiva."}}
    ws.exemplars_bank_path.write_text(json.dumps(bank, ensure_ascii=False), encoding="utf-8")
    calls = record(monkeypatch)

    entrypoints.review_taggability(ws)

    assert calls[0][3] == bank

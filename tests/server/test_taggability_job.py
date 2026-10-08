"""The taggability job: the library judges, the server writes, translates and skips.

The model pass is `entrypoints.review_taggability`; what stays in the handler is
`kg_edit.set_non_taggable` — which owns the history, the database mirror and the approval —
turning the library's exception into a sentence somebody can act on, and skipping the pass
when nothing it reads changed (`server/taggability.py`). The review heads every collection
of the bank since 2026-10-08, so the skip is what keeps a second collection from paying the
model again and from undoing what a teacher switched by hand.
"""

import json

import pytest

from server import approvals, taggability
from server.editors import kg_edit
from server.jobs import handlers
from server.jobs.catalogue import JOB_ARTIFACT, Job
from variatio import entrypoints
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
def stub(monkeypatch, tmp_path):
    saved: list[list[str]] = []
    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    monkeypatch.setattr(
        handlers, "_workspace", lambda job: Workspace(tmp_path / job.workspace, slug=job.workspace)
    )

    def set_non_taggable(ws, concepts, *, reseal=False):
        assert reseal, "the review is the system's: it seals the graph's approval again"
        saved.append(list(concepts))
        return {"non_taggable": len(concepts)}

    monkeypatch.setattr(handlers.kg_edit, "set_non_taggable", set_non_taggable)
    return saved


def job() -> Job:
    return Job(kind="review_taggability", workspace="aula")


def test_it_writes_what_the_stage_judged_and_reports_both_counts(stub, monkeypatch):
    monkeypatch.setattr(
        entrypoints,
        "review_taggability",
        lambda ws: {"non_taggable": ["Notación asintótica", "Algoritmo"], "concepts": 5},
    )

    assert handlers.handle_review_taggability(job(), None) == {"non_taggable": 2, "concepts": 5}
    assert stub == [["Notación asintótica", "Algoritmo"]]


@pytest.mark.parametrize(
    "artifact, said",
    [
        (entrypoints.EXEMPLARS_PROFILE, "perfil de ejemplares"),
        (entrypoints.KNOWLEDGE_GRAPH, "grafo de conocimiento"),
    ],
)
def test_a_missing_artifact_reaches_the_person_as_a_sentence(stub, monkeypatch, artifact, said):
    """`MissingArtifactError` names the artifact; only this layer knows somebody is reading."""

    def refuse(ws):
        raise entrypoints.MissingArtifactError(artifact)

    monkeypatch.setattr(entrypoints, "review_taggability", refuse)

    with pytest.raises(ValueError) as exc:
        handlers.handle_review_taggability(job(), None)

    assert said in str(exc.value)
    assert artifact not in str(exc.value)
    assert stub == []


def test_it_patches_the_graph_in_place_and_builds_no_artifact():
    """Out of `JOB_ARTIFACT` on purpose: the `building` state would hide its own button."""
    assert "review_taggability" not in JOB_ARTIFACT
    assert Job(kind="review_taggability").artifact is None


# THE SKIP AND THE SEAL, on real files -----------------------------------------------------


@pytest.fixture
def aula(tmp_path, monkeypatch):
    """A workspace with a graph, a profile and a context, its handler pointed at it."""
    ws = Workspace(tmp_path / "aula", slug="aula")
    ws.artifacts_dir.mkdir(parents=True)
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    ws.exemplars_profile_path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    ws.content_context_path.write_text(
        json.dumps({"text": "Programación.", "subject": "Programación"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(handlers, "_workspace", lambda job: ws)
    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    return ws


@pytest.fixture
def judge(monkeypatch):
    """The model pass, counted: it rules «Notación asintótica» out every time it runs."""
    calls: list[str] = []

    def review(ws):
        calls.append(ws.slug)
        return {"non_taggable": ["Notación asintótica"], "concepts": 5}

    monkeypatch.setattr(entrypoints, "review_taggability", review)
    return calls


def _graph(ws: Workspace) -> dict:
    return json.loads(ws.kg_path.read_text(encoding="utf-8"))


def test_a_second_review_over_the_same_inputs_is_skipped(aula, judge):
    handlers.handle_review_taggability(job(), None)
    again = handlers.handle_review_taggability(job(), None)

    assert judge == ["aula"]
    assert again == {"skipped": True, "non_taggable": 1, "concepts": 5}


def test_a_changed_profile_is_reviewed_again(aula, judge):
    handlers.handle_review_taggability(job(), None)
    profile = dict(PROFILE, general_generation_rules=["Una regla nueva."])
    aula.exemplars_profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")

    handlers.handle_review_taggability(job(), None)

    assert judge == ["aula", "aula"]


def test_a_changed_syllabus_is_reviewed_again(aula, judge):
    handlers.handle_review_taggability(job(), None)
    kg_edit.add_concept(aula, "Pila de llamadas", "Avanzado")

    handlers.handle_review_taggability(job(), None)

    assert judge == ["aula", "aula"]


def test_a_switch_turned_by_hand_survives_the_next_collection(aula, judge):
    """The fingerprint leaves the non-taggable list out: it is what a teacher corrects."""
    handlers.handle_review_taggability(job(), None)
    kg_edit.update_concept(aula, "Notación asintótica", taggable=True)

    result = handlers.handle_review_taggability(job(), None)

    assert result["skipped"] is True
    assert judge == ["aula"]
    assert _graph(aula)["generic_non_taggable_concepts"] == []


def test_a_graph_reviewed_before_the_record_existed_is_taken_at_its_word(aula, judge):
    graph = dict(CHAIN_GRAPH, taggability_reviewed=True)
    aula.kg_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

    result = handlers.handle_review_taggability(job(), None)

    assert result["skipped"] is True
    assert judge == []
    assert taggability.record(aula)["fingerprint"] == taggability.fingerprint(aula)


def test_a_graph_a_build_just_wrote_is_always_reviewed(aula, judge):
    graph = dict(CHAIN_GRAPH, taggability_reviewed=False)
    aula.kg_path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    taggability.write_record(aula, taggability.fingerprint(aula), [], 5)

    handlers.handle_review_taggability(job(), None)

    assert judge == ["aula"]


def test_the_review_keeps_an_approved_syllabus_approved_with_its_new_hash(aula, judge):
    approvals.Approvals(aula).approve(approvals.KNOWLEDGE_GRAPH)
    before = approvals.Approvals(aula).state(approvals.KNOWLEDGE_GRAPH)["hash"]

    handlers.handle_review_taggability(job(), None)

    state = approvals.Approvals(aula).state(approvals.KNOWLEDGE_GRAPH)
    assert state["status"] == "approved"
    assert state["hash"] != before


def test_the_review_leaves_a_syllabus_in_draft_in_draft(aula, judge):
    handlers.handle_review_taggability(job(), None)

    assert approvals.Approvals(aula).state(approvals.KNOWLEDGE_GRAPH)["status"] == "draft"


def test_a_hand_edit_still_withdraws_the_syllabus_approval(aula, judge):
    approvals.Approvals(aula).approve(approvals.KNOWLEDGE_GRAPH)

    kg_edit.set_non_taggable(aula, ["Variable"])

    assert approvals.Approvals(aula).state(approvals.KNOWLEDGE_GRAPH)["status"] == "draft"


def test_emptying_the_syllabus_forgets_the_record(aula, judge):
    handlers.handle_review_taggability(job(), None)
    assert aula.taggability_review_path.is_file()

    approvals.discard(aula, approvals.KNOWLEDGE_GRAPH)

    assert not aula.taggability_review_path.exists()

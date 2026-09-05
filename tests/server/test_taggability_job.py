"""The taggability job: the library judges, the server writes and translates.

The model pass is `entrypoints.review_taggability`; what stays in the handler is
`kg_edit.set_non_taggable` — which owns the history, the database mirror and the approval
the edit revokes — and turning the library's exception into a sentence somebody can act on.
"""

import pytest

from server.jobs import handlers
from server.jobs.catalogue import JOB_ARTIFACT, Job
from variatio import entrypoints
from variatio.core.workspace import Workspace


@pytest.fixture
def stub(monkeypatch, tmp_path):
    saved: list[list[str]] = []
    monkeypatch.setattr(handlers.deps, "require_inference", lambda: None)
    monkeypatch.setattr(
        handlers, "_workspace", lambda job: Workspace(tmp_path / job.workspace, slug=job.workspace)
    )

    def set_non_taggable(ws, concepts):
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

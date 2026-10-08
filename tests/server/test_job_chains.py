"""What a job drags behind it, and what stops each link.

Two jobs leave mandatory work behind. The graph build chains the concept descriptions: one
press gives a syllabus whose concepts have vectors. The taggability review heads the bank's
collection (2026-10-08, when the types of exercise and the bank became one step): one press,
«Recoger el banco», decides the labels, extracts and tags the bank with them, and warms the
indices. Both are invisible from the screens that start them, and a silently emptied
`CHAINS` would look exactly like a chain that works, so this pins them.

The conditions are pinned with them: each link declares one, the condition is the LINK's own
and not its neighbour's, an unmet condition SKIPS rather than fails, and the chain carries on
with the next.
"""

import json

import pytest

from server import approvals
from server.jobs import chain
from server.jobs.catalogue import Job
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


class Recorder:
    """A runner that records what would be queued, and what announced, instead of doing it."""

    def __init__(self):
        self.submitted: list[tuple[str, dict]] = []
        self.published: list[tuple[str, dict]] = []
        self.bus = self

    def submit(self, kind, params, **_kwargs):
        self.submitted.append((kind, params))

    def publish(self, _workspace, _job_id, kind, payload=None):
        self.published.append((kind, payload or {}))


def workspace(
    tmp_path,
    *,
    profile=False,
    profile_approved=False,
    graph_approved=False,
    exercises=False,
    bank=False,
) -> Workspace:
    ws = Workspace(root=tmp_path, slug="test")
    ws.artifacts_dir.mkdir(parents=True, exist_ok=True)
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    if profile:
        ws.exemplars_profile_path.write_text(
            json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8"
        )
    if profile_approved:
        approvals.Approvals(ws).approve(approvals.EXEMPLARS_PROFILE)
    if graph_approved:
        approvals.Approvals(ws).approve(approvals.KNOWLEDGE_GRAPH)
    if exercises:
        ws.raw_exemplars_dir.mkdir(parents=True, exist_ok=True)
        (ws.raw_exemplars_dir / "hoja.md").write_text("# Ejercicio 1\n", encoding="utf-8")
    if bank:
        ws.exemplars_bank_path.write_text(json.dumps({"items": []}), encoding="utf-8")
    return ws


def ready(tmp_path, **extra) -> Workspace:
    """A workspace whose bank may be collected: both upstreams approved, a sheet to read."""
    return workspace(
        tmp_path, profile=True, profile_approved=True, graph_approved=True, exercises=True, **extra
    )


def advance(monkeypatch, ws: Workspace, job: Job) -> Recorder:
    """Run one step of the chain against `ws`, whatever slug the job carries."""
    monkeypatch.setattr(chain.installation, "workspace_for", lambda _slug: ws)
    runner = Recorder()
    chain.advance(runner, job)
    return runner


# THE TWO CHAINS --------------------------------------------------------------------------


def test_a_graph_build_is_followed_by_its_descriptions_alone():
    # The labels and the indices left this chain on 2026-10-08: indexing between a graph build
    # and a bank collection embedded concepts nobody had reviewed, and was thrown away.
    assert chain.CHAINS["build_kg"] == ("describe_concepts",)


def test_the_taggability_review_heads_the_bank_s_collection():
    # The order matters: the bank is tagged with the labels the review decides, and the
    # index embeds the bank the extraction wrote.
    assert chain.CHAINS["review_taggability"] == ("build_bank", "index")


def test_only_those_two_chain_anything():
    assert set(chain.CHAINS) == {"build_kg", "review_taggability"}


def test_every_link_declares_its_own_condition():
    """Nothing may be chained without a reason it can be skipped for.

    A link with no entry in `REQUIRES` runs unconditionally, which in a workspace that is
    missing its upstream means a job that fails instead of one that is not queued.
    """
    for followers in chain.CHAINS.values():
        for kind in followers:
            assert kind in chain.REQUIRES, f"«{kind}» se encadena sin condición"


def test_a_link_carries_the_rest_and_the_head_its_kind_s(tmp_path):
    assert chain.remaining(Job(kind="review_taggability")) == ("build_bank", "index")
    assert chain.remaining(Job(kind="build_bank", params={"chain": ["index"]})) == ("index",)
    assert chain.remaining(Job(kind="index", params={"chain": []})) == ()
    assert chain.links("generate") == ()


# THE GRAPH'S ------------------------------------------------------------------------------


def test_with_no_profile_the_descriptions_still_follow(tmp_path, monkeypatch):
    """Describing needs the GRAPH, so the state a new workspace starts in is not a skip."""
    ws = workspace(tmp_path)
    runner = advance(monkeypatch, ws, Job(kind="build_kg", workspace=ws.slug))
    assert runner.submitted == [("describe_concepts", {"chain": [], "head": "build_kg"})]


def test_without_a_graph_nothing_is_described(tmp_path, monkeypatch):
    """The one condition describing actually has, and it is reported rather than raised."""
    ws = Workspace(root=tmp_path, slug="test")
    ws.artifacts_dir.mkdir(parents=True, exist_ok=True)
    runner = advance(monkeypatch, ws, Job(kind="build_kg", workspace=ws.slug))
    assert runner.submitted == []


def test_the_descriptions_end_the_graph_s_chain(tmp_path, monkeypatch):
    ws = ready(tmp_path, bank=True)
    job = Job(kind="describe_concepts", params={"chain": []}, workspace=ws.slug)
    assert advance(monkeypatch, ws, job).submitted == []


# THE BANK'S -------------------------------------------------------------------------------


def test_with_everything_settled_the_review_queues_the_extraction_and_passes_the_rest(
    tmp_path, monkeypatch
):
    ws = ready(tmp_path)
    runner = advance(monkeypatch, ws, Job(kind="review_taggability", workspace=ws.slug))
    # The remainder travels ON the job, so each condition is read when its own turn comes.
    assert runner.submitted == [
        ("build_bank", {"chain": ["index"], "head": "review_taggability"})
    ]


def test_the_extraction_is_followed_by_the_index(tmp_path, monkeypatch):
    ws = ready(tmp_path, bank=True)
    job = Job(
        kind="build_bank",
        params={"chain": ["index"], "head": "review_taggability"},
        workspace=ws.slug,
    )
    assert advance(monkeypatch, ws, job).submitted == [
        ("index", {"chain": [], "head": "review_taggability"})
    ]


@pytest.mark.parametrize(
    "state",
    [
        {"profile": True, "graph_approved": True, "exercises": True},
        {"profile": True, "profile_approved": True, "exercises": True},
        {"profile": True, "profile_approved": True, "graph_approved": True},
    ],
    ids=["types-not-settled", "syllabus-not-settled", "no-exercise-sheet"],
)
def test_the_bank_and_the_index_are_skipped_when_the_bank_cannot_be_collected(
    tmp_path, monkeypatch, state
):
    """The route refuses these first; a skip here is what a forced head leaves behind."""
    ws = workspace(tmp_path, **state)
    runner = advance(monkeypatch, ws, Job(kind="review_taggability", workspace=ws.slug))
    assert runner.submitted == []


@pytest.mark.parametrize("kind", ["build_profile", "transcribe", "generate", "tag", "index"])
def test_no_other_job_queues_anything_behind_it(tmp_path, monkeypatch, kind):
    ws = ready(tmp_path, bank=True)
    runner = advance(monkeypatch, ws, Job(kind=kind, params={}, workspace=ws.slug))
    assert runner.submitted == []


# WHAT A CHAIN CLOSES ----------------------------------------------------------------------


def last_link(ws: Workspace) -> Job:
    """The index that ends a collection of the bank, as the chain queued it."""
    return Job(
        kind="index", params={"chain": [], "head": "review_taggability"}, workspace=ws.slug
    )


def test_the_bank_s_collection_closes_the_bank_once_indexed(tmp_path, monkeypatch):
    """A bank extracted, tagged and indexed is a finished step: the doors open with it."""
    ws = ready(tmp_path, bank=True)
    runner = advance(monkeypatch, ws, last_link(ws))
    assert approvals.Approvals(ws).state(approvals.EXEMPLARS_BANK)["status"] == "approved"
    assert runner.published == [
        ("pipeline.changed", {"artifact": approvals.EXEMPLARS_BANK, "action": "approve"})
    ]


def test_types_reopened_while_it_ran_leave_the_bank_a_draft(tmp_path, monkeypatch):
    """The bank was collected with the types closed then; corrected since, it is not theirs."""
    ws = ready(tmp_path, bank=True)
    approvals.Approvals(ws).reopen(approvals.EXEMPLARS_PROFILE)
    runner = advance(monkeypatch, ws, last_link(ws))
    assert approvals.Approvals(ws).state(approvals.EXEMPLARS_BANK)["status"] == "draft"
    assert runner.published == []


@pytest.mark.parametrize(
    "job",
    [
        Job(kind="index", params={}),
        Job(kind="index", params={"chain": [], "head": "index"}),
        Job(kind="describe_concepts", params={"chain": [], "head": "build_kg"}),
    ],
    ids=["index-alone", "index-heading-itself", "graph-chain"],
)
def test_nothing_else_closes_the_bank(tmp_path, monkeypatch, job):
    ws = ready(tmp_path, bank=True)
    job.workspace = ws.slug
    advance(monkeypatch, ws, job)
    assert approvals.Approvals(ws).state(approvals.EXEMPLARS_BANK)["status"] == "draft"

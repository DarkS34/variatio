"""What a graph build drags behind it, and what stops each link.

The user asks for one press: build the syllabus and get back a syllabus that is FINISHED —
described, with its labels decided and its indices warm — rather than a graph plus three
buttons nobody was told about. That is `jobs/chain.py`, and this pins it, because the three
links are invisible from the screen that starts them and a silently emptied `CHAINS` would
look exactly like a chain that works.

The conditions are pinned with it: each link declares one, the condition is the LINK's own
and not its neighbour's, an unmet condition SKIPS rather than fails, and the chain carries
on with the next. A fresh workspace — graph first, no profile yet — must still get its
descriptions, because describing reads the graph and never the profile.
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
    """A runner that records what would be queued instead of queueing it."""

    def __init__(self):
        self.submitted: list[tuple[str, dict]] = []

    def submit(self, kind, params, **_kwargs):
        self.submitted.append((kind, params))


def workspace(tmp_path, *, profile=False, approved=False, bank=False) -> Workspace:
    ws = Workspace(root=tmp_path, slug="test")
    ws.instance_dir.mkdir(parents=True, exist_ok=True)
    ws.kg_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    if profile:
        ws.exemplars_profile_path.write_text(
            json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8"
        )
    if approved:
        approvals.Approvals(ws).approve(approvals.EXEMPLARS_PROFILE)
    if bank:
        ws.exemplars_bank_path.write_text(json.dumps({"items": []}), encoding="utf-8")
    return ws


def build_job(ws: Workspace, params: dict | None = None) -> Job:
    return Job(kind="build_kg", params=params or {}, workspace=ws.slug)


def advance(monkeypatch, ws: Workspace, job: Job) -> Recorder:
    """Run one step of the chain against `ws`, whatever slug the job carries."""
    monkeypatch.setattr(chain.installation, "workspace_for", lambda _slug: ws)
    runner = Recorder()
    chain.advance(runner, job)
    return runner


def test_a_graph_build_is_followed_by_the_three_derivations():
    # The order matters: describing writes the vectors the taggability judgement and the
    # index both read, so a chain that ran them the other way round would judge and index
    # against descriptions that do not exist yet.
    assert chain.CHAINS["build_kg"] == ("describe_concepts", "review_taggability", "index")


def test_only_the_graph_build_chains_anything():
    assert set(chain.CHAINS) == {"build_kg"}


def test_every_link_declares_its_own_condition():
    """Nothing may be chained without a reason it can be skipped for.

    A link with no entry in `REQUIRES` runs unconditionally, which in a workspace that is
    missing its upstream means a job that fails instead of one that is not queued.
    """
    for followers in chain.CHAINS.values():
        for kind in followers:
            assert kind in chain.REQUIRES, f"«{kind}» se encadena sin condición"


def test_with_no_profile_the_descriptions_still_follow(tmp_path, monkeypatch):
    """Describing needs the GRAPH, so the state a new workspace starts in is not a skip.

    It used to be gated on the profile, which withheld the one derivation this chain calls
    mandatory from the very workspace the chain was written for.
    """
    ws = workspace(tmp_path)
    runner = advance(monkeypatch, ws, build_job(ws))
    assert [kind for kind, _ in runner.submitted] == ["describe_concepts"]


def test_with_no_profile_the_other_two_links_are_skipped(tmp_path, monkeypatch):
    """And the chain ends there rather than failing: both of them do read the profile."""
    ws = workspace(tmp_path)
    job = Job(
        kind="describe_concepts",
        params={"chain": ["review_taggability", "index"]},
        workspace=ws.slug,
    )
    assert advance(monkeypatch, ws, job).submitted == []


def test_without_a_graph_nothing_is_described(tmp_path, monkeypatch):
    """The one condition describing actually has, and it is reported rather than raised."""
    ws = Workspace(root=tmp_path, slug="test")
    ws.instance_dir.mkdir(parents=True, exist_ok=True)
    runner = advance(monkeypatch, ws, build_job(ws))
    assert runner.submitted == []


def test_with_a_profile_the_descriptions_follow_and_carry_the_rest(tmp_path, monkeypatch):
    ws = workspace(tmp_path, profile=True)
    runner = advance(monkeypatch, ws, build_job(ws))
    assert len(runner.submitted) == 1
    kind, params = runner.submitted[0]
    assert kind == "describe_concepts"
    # The remainder travels ON the job, so each condition is read when its own turn comes
    # and not at the moment the build finished.
    assert params["chain"] == ["review_taggability", "index"]


def test_an_unapproved_profile_skips_the_review_without_cutting_the_chain(tmp_path, monkeypatch):
    """Built but unapproved is a skip, and the link behind it still gets its turn."""
    ws = workspace(tmp_path, profile=True, bank=True)
    job = Job(
        kind="describe_concepts",
        params={"chain": ["review_taggability", "index"]},
        workspace=ws.slug,
    )
    runner = advance(monkeypatch, ws, job)
    assert [kind for kind, _ in runner.submitted] == ["index"]


def test_an_approved_profile_lets_the_taggability_review_through(tmp_path, monkeypatch):
    ws = workspace(tmp_path, profile=True, approved=True, bank=True)
    job = Job(
        kind="describe_concepts",
        params={"chain": ["review_taggability", "index"]},
        workspace=ws.slug,
    )
    runner = advance(monkeypatch, ws, job)
    assert [kind for kind, _ in runner.submitted] == ["review_taggability"]


def test_without_a_bank_the_index_is_skipped_and_the_chain_simply_ends(tmp_path, monkeypatch):
    ws = workspace(tmp_path, profile=True, approved=True)
    job = Job(kind="review_taggability", params={"chain": ["index"]}, workspace=ws.slug)
    runner = advance(monkeypatch, ws, job)
    assert runner.submitted == []


@pytest.mark.parametrize("kind", ["build_profile", "build_bank", "transcribe", "generate"])
def test_no_other_job_queues_anything_behind_it(tmp_path, monkeypatch, kind):
    ws = workspace(tmp_path, profile=True, approved=True, bank=True)
    runner = advance(monkeypatch, ws, Job(kind=kind, params={}, workspace=ws.slug))
    assert runner.submitted == []

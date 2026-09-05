"""Which backend each job kind competes for.

The claim under test is not «this kind uses that model» — that is the builders' and the
handlers' business — but the two properties the parallel queue rests on: with one engine
everything shares one lane and the queue behaves exactly as it did, and with the hybrid
engine a kind reserves a lane for each backend its GENERATIVE models resolve to. The
embedder and the guardrail never reserve anything, whatever they are routed to: they are
small, co-resident and not what a wait is ever about.
"""

import pytest

from server.jobs import lanes
from server.jobs.catalogue import JOB_LABELS
from variatio import config
from variatio.core import inference
from variatio.settings import derived

# `VARIANT_GENERATION_LLM` is derived rather than declared since the commission started
# choosing its own writer, so it is named here beside the phases it stopped being one of.
MODEL_SETTINGS = {
    "LLM_MAIN",
    "GUARDRAIL_LLM",
    "EMBEDDING_LLM",
    "VARIANT_GENERATION_LLM",
    *derived.PHASES.values(),
}

BUILD_KINDS = ("build_profile", "build_kg", "build_bank")
COMPONENT_KINDS = tuple(k for k in JOB_LABELS if k not in BUILD_KINDS)


@pytest.fixture
def ollama(monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_ENGINE", "ollama")
    inference.reset_engine()
    yield
    inference.reset_engine()


# One model on Cerebras and everything else on Ollama, with distinct names per phase so
# the split is readable instead of collapsing into whatever `LLM_MAIN` happens to be.
@pytest.fixture
def hybrid(monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_ENGINE", "cerebras+ollama")
    monkeypatch.setattr(config, "CEREBRAS_MODELS", ["remoto"])
    monkeypatch.setattr(config, "KG_TAGGABLE_MODEL", "remoto")
    monkeypatch.setattr(config, "REPAIR_LLM", "local-repair")
    monkeypatch.setattr(config, "DESCRIPTION_GENERATION_LLM", "local-describe")
    monkeypatch.setattr(config, "TRANSCRIBE_MODEL", "remoto")
    monkeypatch.setattr(config, "TRANSCRIBE_SEAM_MODEL", "remoto")
    inference.reset_engine()
    yield
    inference.reset_engine()


def test_one_engine_means_one_lane_for_every_component(ollama):
    for kind in COMPONENT_KINDS:
        assert lanes.backends_for(kind) == frozenset({lanes.LOCAL}), kind


# Separate from the components because a build's models are the BUILDER's declaration, not
# a table here: this is the one test that reads `entrypoints.build_models`, and it is where a
# builder that stops resolving its own phase models shows up.
def test_one_engine_means_one_lane_for_every_build(ollama):
    for kind in BUILD_KINDS:
        assert lanes.backends_for(kind) == frozenset({lanes.LOCAL}), kind


def test_a_kind_reserves_a_lane_per_backend_it_actually_calls(hybrid):
    # The taggability review calls the remote judge and repairs locally: both.
    assert lanes.backends_for("review_taggability") == frozenset(
        {lanes.LOCAL, lanes.REMOTE}
    )
    # Describing calls neither remotely.
    assert lanes.backends_for("describe_concepts") == frozenset({lanes.LOCAL})
    # Transcribing calls one model and it is remote.
    assert lanes.backends_for("transcribe") == frozenset({lanes.REMOTE})


def test_the_embedder_and_the_guardrail_never_reserve_a_lane(monkeypatch):
    monkeypatch.setattr(config, "INFERENCE_ENGINE", "cerebras+ollama")
    monkeypatch.setattr(config, "EMBEDDING_LLM", "emb")
    monkeypatch.setattr(config, "GUARDRAIL_LLM", "guard")
    monkeypatch.setattr(config, "CEREBRAS_MODELS", ["emb", "guard"])
    inference.reset_engine()
    try:
        for kind in COMPONENT_KINDS:
            assert lanes.REMOTE not in lanes.backends_for(kind), kind
            assert "guard" not in lanes.models_for(kind), kind
        # The graph build declares the embedder among its models; the lane calculation
        # drops it, so what would otherwise be a remote reservation is not one.
        assert "emb" not in lanes.models_for("build_kg")
        assert lanes.REMOTE not in lanes.backends_for("build_kg")
    finally:
        inference.reset_engine()


def test_a_job_that_calls_no_model_reserves_nothing(ollama):
    assert lanes.backends_for("una-clase-que-no-existe") == frozenset()


# The table names `config` attributes by hand, which is what makes it readable; this is
# what keeps it from naming one the registry stopped declaring.
def test_every_model_the_table_names_is_one_the_registry_declares():
    named = {name for names in lanes._COMPONENT_MODELS.values() for name in names}
    assert named
    assert named <= MODEL_SETTINGS


# The writer of a variant is the commission's since 2026-08-29, and with one offered model
# served remotely and another on the GPU that is the whole lane calculation of a generate
# job: reading the installation's default instead would send it to wait behind the wrong
# queue, or reserve a lane it never touches.
def test_a_generate_job_reserves_the_lane_of_the_model_its_commission_names(hybrid, monkeypatch):
    monkeypatch.setattr(config, "GENERATION_MODELS", ["remoto", "local-escritor"])
    monkeypatch.setattr(config, "VARIANT_GENERATION_LLM", "remoto")
    monkeypatch.setattr(config, "ADMISSIBILITY_LLM", "local-juez")
    monkeypatch.setattr(config, "CONCEPT_TAGGER_LLM", "local-etiquetador")

    assert lanes.models_for("generate", {"model": "local-escritor"})[0] == "local-escritor"
    assert lanes.backends_for("generate", {"model": "local-escritor"}) == frozenset(
        {lanes.LOCAL}
    )
    # Naming none is the default, which here is the remote one: both lanes, because the
    # repair and the tagger stay on the GPU.
    assert lanes.backends_for("generate", {}) == frozenset({lanes.LOCAL, lanes.REMOTE})
    assert lanes.models_for("generate", {})[0] == "remoto"


# A name the installation stopped offering is the submit route's 422, never a 500 here:
# a lane calculation that raises turns a queueing problem into a broken button.
def test_an_unoffered_model_falls_back_instead_of_raising(ollama, monkeypatch):
    monkeypatch.setattr(config, "GENERATION_MODELS", ["el-que-hay"])
    monkeypatch.setattr(config, "VARIANT_GENERATION_LLM", "el-que-hay")
    assert lanes.models_for("generate", {"model": "el-que-ya-no"})[0] == "el-que-hay"
    assert lanes.backends_for("generate", {"model": "el-que-ya-no"}) == frozenset(
        {lanes.LOCAL}
    )


def test_transcribing_reserves_the_lane_of_the_model_that_reads_the_pages(ollama):
    assert lanes.models_for("transcribe")[0] == config.TRANSCRIBE_MODEL
    assert lanes.backends_for("transcribe") == frozenset({lanes.LOCAL})


# An evaluation's two local proposals are written by the installation's own setting since
# 2026-09-04 (`evaluation.local_model`), so the lane it reserves is that model's and never
# the generation default's alone.
def test_an_evaluate_job_reserves_the_lane_of_the_installations_writer(hybrid, monkeypatch):
    monkeypatch.setattr(config, "VARIANT_GENERATION_LLM", "remoto")
    monkeypatch.setattr(lanes, "_evaluation_writer", lambda: "local-escritor")
    assert lanes.models_for("evaluate")[0] == "local-escritor"
    assert lanes.backends_for("evaluate") >= frozenset({lanes.LOCAL})

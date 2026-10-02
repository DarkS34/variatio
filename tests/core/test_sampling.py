"""Each model call samples with its own temperature, top-k and top-p, inherited when empty.

Empty is what every call did before the triple existed, and that is the property worth
pinning: the temperature follows the judging pair by whether the call reasons, top-k and
top-p are not sent, and a call reading with another phase's model takes that phase's values.
"""

import json

import httpx
import pytest

from variatio import config, settings
from variatio.builders.source_docs import pages
from variatio.core import inference
from variatio.core.cerebras import CerebrasEngine
from variatio.core.inference import OllamaEngine, Sampling
from variatio.entrypoints import transcribe
from variatio.settings import derived, store
from variatio.settings.registry import BY_KEY, reasoning

EMPTY = {"temperature": None, "top_k": None, "top_p": None}


@pytest.fixture
def triples(monkeypatch):
    """Install a SAMPLING map the test edits, with the judging pair at known values."""
    table = {phase: dict(EMPTY) for phase in config.SAMPLING}
    monkeypatch.setattr(config, "SAMPLING", table)
    monkeypatch.setattr(config, "TEMPERATURE_DETERMINISTIC", 0.0)
    monkeypatch.setattr(config, "TEMPERATURE_REASONING", 0.2)
    return table


def test_every_call_of_the_pipeline_has_its_triple():
    for lane in reasoning.PIPELINE:
        for phase in lane.phases:
            for param in ("temperature", "top_k", "top_p"):
                assert f"sampling.phases.{phase.key}.{param}" in BY_KEY
            assert phase.key in config.SAMPLING


def test_an_empty_temperature_follows_whether_the_call_reasons(triples):
    assert inference.sampling("kg_extract", False) == Sampling(0.0)
    assert inference.sampling("kg_extract", "low") == Sampling(0.2)


def test_a_temperature_of_its_own_ignores_the_switch(triples):
    triples["kg_extract"]["temperature"] = 0.7
    assert inference.sampling("kg_extract", False).temperature == 0.7
    assert inference.sampling("kg_extract", "high").temperature == 0.7


def test_top_k_and_top_p_travel_only_when_set(triples):
    triples["kg_clean_drop"].update(top_k=20, top_p=0.95)
    assert inference.sampling("kg_clean_drop") == Sampling(0.0, 20, 0.95)
    assert inference.sampling("kg_extract") == Sampling(0.0, None, None)


def test_a_misspelt_phase_is_refused_rather_than_inherited(triples):
    with pytest.raises(KeyError):
        inference.sampling("kg_extrac")


def test_the_three_temperatures_that_were_one_call_s_keep_their_values():
    assert config.SAMPLING["transcribe"]["temperature"] == config.TRANSCRIBE_TEMPERATURE
    assert config.SAMPLING["variant_generation"]["temperature"] == config.TEMPERATURE_GENERATION
    assert config.SAMPLING["repair"]["temperature"] == config.TEMPERATURE_REPAIR


def test_the_pictures_inherit_what_they_leave_empty_from_the_pages():
    values = settings.values()
    values["sampling.phases.transcribe.top_k"] = 40
    values["sampling.phases.transcribe_image.top_p"] = 0.8
    out = derived.derive(values)["SAMPLING"]
    assert out["transcribe_image"]["top_k"] == 40
    assert out["transcribe_image"]["top_p"] == 0.8
    assert out["transcribe_image"]["temperature"] == out["transcribe"]["temperature"]
    assert out["transcribe"]["top_p"] is None


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("builders.transcribe_temperature", "sampling.phases.transcribe.temperature"),
        ("sampling.temperature_generation", "sampling.phases.variant_generation.temperature"),
        ("sampling.temperature_repair", "sampling.phases.repair.temperature"),
    ],
)
def test_a_file_written_before_the_triples_keeps_its_temperatures(tmp_path, old, new):
    head, leaf = old.split(".")
    path = tmp_path / "config.json"
    path.write_text(json.dumps({head: {leaf: 0.55}}), encoding="utf-8")
    assert store.read_file(path) == {new: 0.55}


# THE ENGINES ------------------------------------------------------------------------------------


def test_ollama_sends_top_k_and_top_p_only_when_set(monkeypatch):
    monkeypatch.setattr(config, "LLM_CONTEXT", {})
    plain = OllamaEngine._context_option("m", Sampling(0.1))
    assert plain == {"options": {"temperature": 0.1}}
    full = OllamaEngine._context_option("m", Sampling(0.1, 20, 0.9))
    assert full == {"options": {"temperature": 0.1, "top_k": 20, "top_p": 0.9}}


def test_cerebras_sends_top_p_and_drops_top_k():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    engine = CerebrasEngine()
    engine._client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://api.cerebras.ai/v1"
    )
    engine.generate("gemma-4-31b", "hola", sampling=Sampling(0.3, 20, 0.9))
    assert seen["temperature"] == 0.3
    assert seen["top_p"] == 0.9
    assert "top_k" not in seen


# THE TRANSCRIPTION'S CACHES -----------------------------------------------------------------------


def test_an_empty_top_k_and_top_p_leave_the_page_fingerprint_as_it_was(triples):
    triples["transcribe"]["temperature"] = 0.0
    assert pages.sampling_record("transcribe") == {"temperature": 0.0}


def test_a_set_top_k_enters_the_fingerprint_and_is_named_when_it_moves(triples):
    triples["transcribe"].update(temperature=0.0, top_k=20)
    expected = {"model": "m", **pages.sampling_record("transcribe")}
    assert expected["top_k"] == 20
    stored = {"model": "m", "temperature": 0.0}
    assert transcribe._reasons(stored, expected) == ["sampling"]
    # Emptied again since the reading: the field only the stored side has counts too.
    assert transcribe._reasons(expected, stored) == ["sampling"]

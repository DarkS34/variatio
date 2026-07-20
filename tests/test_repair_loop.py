import pytest

from builders.content_profile_builder import ContentProfileBuilder
from builders.exemplars_bank_builder import ExemplarsBankBuilder
from system import config

TAG_OK = '{"concepts": ["Bucles"], "primary_concept": "Bucles"}'
ITEM_OK = (
    '{"statement": "Escribe una función que recorra una lista.", "solution": null, '
    '"difficulty_level": "básico", "tags": []}'
)
BATCH_OK = (
    '[{"statement": "Escribe una función que recorra una lista.", "solution": null, '
    '"difficulty_level": "básico", "tags": []}]'
)


@pytest.fixture
def bank_builder(profile):
    builder = object.__new__(ExemplarsBankBuilder)
    builder.item_model = profile.content_item
    builder.context = profile.content_context
    builder.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
    builder._schema_str = "{}"
    builder._extraction_guidance_block = ""
    return builder


@pytest.fixture
def profile_builder():
    builder = object.__new__(ContentProfileBuilder)
    builder.model = "profile-model"
    builder.max_repair_attempts = config.MAX_JSON_REPAIR_TRIES
    return builder


# CONCEPT TAGGER -----------------------------------------------------------------------------


def test_tagger_does_not_repair_a_valid_response(tagger, scripted_generate):
    calls = scripted_generate(TAG_OK)

    result = tagger.tag("Recorre una lista con un bucle.")

    assert result["primary_concept"] == "Bucles"
    assert len(calls) == 1


def test_tagger_recovers_on_a_later_repair(tagger, scripted_generate):
    calls = scripted_generate("no soy json", "sigo sin serlo", TAG_OK)

    result = tagger.tag("Recorre una lista con un bucle.")

    assert result["primary_concept"] == "Bucles"
    assert len(calls) == 3


def test_tagger_gives_up_after_exhausting_attempts(tagger, scripted_generate):
    calls = scripted_generate(*(["no soy json"] * 8))

    result = tagger.tag("Recorre una lista con un bucle.")

    assert result == {"concepts": [], "primary_concept": None}
    assert len(calls) == 1 + config.MAX_JSON_REPAIR_TRIES


def test_tagger_repairs_with_its_own_model(tagger, scripted_generate):
    calls = scripted_generate("roto", TAG_OK)

    tagger.tag("Recorre una lista con un bucle.")

    assert [c["model"] for c in calls] == ["tagger-model", "tagger-model"]


def test_tagger_repair_prompt_asks_for_the_object_it_actually_parses(tagger, scripted_generate):
    calls = scripted_generate("roto", TAG_OK)

    tagger.tag("Recorre una lista con un bucle.")

    assert "un objeto JSON corregido" in calls[1]["prompt"]
    assert "array" not in calls[1]["prompt"]


# CONTENT GENERATOR --------------------------------------------------------------------------


def test_generator_does_not_repair_a_valid_response(generator, scripted_generate):
    calls = scripted_generate(ITEM_OK)

    results = generator.generate(concepts=["Bucles"], n=1)

    assert len(results) == 1
    assert len(calls) == 1


def test_generator_recovers_on_a_later_repair(generator, scripted_generate):
    calls = scripted_generate("no soy json", ITEM_OK)

    results = generator.generate(concepts=["Bucles"], n=1)

    assert len(results) == 1
    assert len(calls) == 2


def test_generator_repairs_with_the_repair_model(generator, scripted_generate):
    calls = scripted_generate("roto", ITEM_OK)

    generator.generate(concepts=["Bucles"], n=1)

    assert [c["model"] for c in calls] == ["generator-model", config.REPAIR_LLM]


def test_generator_drops_the_item_after_exhausting_attempts(generator, scripted_generate):
    calls = scripted_generate(*(["no soy json"] * 8))

    results = generator.generate(concepts=["Bucles"], n=1)

    assert results == []
    assert len(calls) == 1 + config.MAX_JSON_REPAIR_TRIES


def test_generator_repair_prompt_asks_for_the_object_it_actually_parses(
    generator, scripted_generate
):
    calls = scripted_generate("roto", ITEM_OK)

    generator.generate(concepts=["Bucles"], n=1)

    assert "un objeto JSON corregido" in calls[1]["prompt"]


def test_extraction_repair_prompt_still_asks_for_an_array(bank_builder, scripted_generate):
    calls = scripted_generate("roto", BATCH_OK)

    bank_builder._extract_batch("1. Escribe una función.", "tag")

    assert "un array JSON corregido" in calls[1]["prompt"]


def test_generator_strips_thinking_before_parsing(generator, scripted_generate):
    scripted_generate(f"<think>lo pienso</think>{ITEM_OK}")

    results = generator.generate(concepts=["Bucles"], n=1)

    assert len(results) == 1
    assert results[0].thinking == "lo pienso"


def test_generator_strips_thinking_from_repair_responses_too(generator, scripted_generate):
    scripted_generate("roto", f"<think>ahora sí</think>{ITEM_OK}")

    results = generator.generate(concepts=["Bucles"], n=1)

    assert len(results) == 1


# EXEMPLARS BANK BUILDER ---------------------------------------------------------------------


def test_extraction_does_not_repair_a_valid_response(bank_builder, scripted_generate):
    calls = scripted_generate(BATCH_OK)

    items = bank_builder._extract_batch("1. Escribe una función.", "tag")

    assert len(items) == 1
    assert len(calls) == 1


def test_extraction_recovers_on_a_later_repair(bank_builder, scripted_generate):
    calls = scripted_generate("no soy json", BATCH_OK)

    items = bank_builder._extract_batch("1. Escribe una función.", "tag")

    assert len(items) == 1
    assert len(calls) == 2


def test_extraction_raises_after_exhausting_attempts(bank_builder, scripted_generate):
    scripted_generate(*(["no soy json"] * 8))

    with pytest.raises(ValueError, match="unrecoverable JSON"):
        bank_builder._extract_batch("1. Escribe una función.", "tag")


def test_extraction_repairs_with_the_repair_model(bank_builder, scripted_generate):
    calls = scripted_generate("roto", BATCH_OK)

    bank_builder._extract_batch("1. Escribe una función.", "tag")

    assert [c["model"] for c in calls] == [config.CONTENT_FORMATTING_LLM, config.REPAIR_LLM]


# CONTENT PROFILE BUILDER --------------------------------------------------------------------


def test_profile_inference_does_not_repair_a_valid_response(
    profile_builder, scripted_generate, min_profile_data
):
    import json

    calls = scripted_generate(json.dumps(min_profile_data))

    profile = profile_builder._infer("muestra")

    assert profile["primary_field"] == "statement"
    assert len(calls) == 1


def test_profile_inference_asks_for_an_object_shape(
    profile_builder, scripted_generate, min_profile_data
):
    import json

    calls = scripted_generate("roto", json.dumps(min_profile_data))

    profile_builder._infer("muestra")

    assert "un objeto JSON corregido" in calls[1]["prompt"]
    assert profile_builder is not None


def test_profile_inference_returns_the_last_parseable_draft(profile_builder, scripted_generate):
    scripted_generate(*(['{"incompleto": true}'] * 8))

    profile = profile_builder._infer("muestra")

    assert profile == {"incompleto": True}

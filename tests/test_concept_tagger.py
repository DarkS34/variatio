import json

import pytest

CANDIDATES = ["Bucles", "Variables"]


def _parse(tagger, payload: str):
    return tagger._parse_and_validate(payload, CANDIDATES)


# PARSING ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        '["Bucles"]',
        '{"primary_concept": "Bucles"}',
        '{"concepts": ["Bucles"]}',
        '{"concepts": "Bucles", "primary_concept": "Bucles"}',
    ],
)
def test_parse_rejects_malformed_payloads(tagger, payload):
    assert _parse(tagger, payload) is None


def test_parse_accepts_a_well_formed_annotation(tagger):
    parsed = _parse(tagger, '{"concepts": ["Bucles", "Variables"], "primary_concept": "Bucles"}')

    assert parsed == {"concepts": ["Bucles", "Variables"], "primary_concept": "Bucles"}


def test_parse_discards_concepts_the_model_invented(tagger):
    parsed = _parse(tagger, '{"concepts": ["Bucles", "Inventado"], "primary_concept": "Bucles"}')

    assert parsed["concepts"] == ["Bucles"]


def test_parse_falls_back_when_the_primary_is_not_a_candidate(tagger):
    parsed = _parse(tagger, '{"concepts": ["Variables"], "primary_concept": "Inventado"}')

    assert parsed == {"concepts": ["Variables"], "primary_concept": "Variables"}


def test_parse_rejects_when_nothing_survives_filtering(tagger):
    assert _parse(tagger, '{"concepts": ["Inventado"], "primary_concept": "Tampoco"}') is None


def test_parse_backfills_concepts_from_a_valid_primary(tagger):
    parsed = _parse(tagger, '{"concepts": ["Inventado"], "primary_concept": "Bucles"}')

    assert parsed == {"concepts": ["Bucles"], "primary_concept": "Bucles"}


def test_parse_accepts_a_deliberate_rejection(tagger):
    parsed = _parse(tagger, '{"concepts": [], "primary_concept": null}')

    assert parsed == {"concepts": [], "primary_concept": None}


# TAGGING ------------------------------------------------------------------------------------


def test_tag_returns_empty_without_asking_the_model(tagger, scripted_generate, stub_embedder):
    tagger.embedder = stub_embedder([])
    calls = scripted_generate()

    result = tagger.tag("Un enunciado cualquiera.")

    assert result["primary_concept"] is None
    assert calls == []


def test_tag_returns_empty_when_the_model_rejects_every_candidate(tagger, scripted_generate):
    scripted_generate('{"concepts": [], "primary_concept": null}')

    result = tagger.tag("Un enunciado sin relación con el temario.")

    assert result["concepts"] == []
    assert result["primary_concept"] is None


def test_tag_passes_the_scored_candidates_to_the_prompt(tagger, scripted_generate):
    calls = scripted_generate('{"concepts": ["Bucles"], "primary_concept": "Bucles"}')

    tagger.tag("Recorre una lista.")

    assert "1. Bucles (score: 0.900)" in calls[0]["prompt"]
    assert "2. Variables (score: 0.500)" in calls[0]["prompt"]


def test_tag_honours_the_candidate_limit(tagger, scripted_generate, stub_embedder):
    tagger.embedder = stub_embedder([(f"C{i}", 0.9) for i in range(20)])
    tagger.top_k_candidates = 3
    calls = scripted_generate('{"concepts": ["C0"], "primary_concept": "C0"}')

    tagger.tag("Recorre una lista.")

    assert "3. C2 (score" in calls[0]["prompt"]
    assert "4. C3 (score" not in calls[0]["prompt"]


def test_every_tag_outcome_has_the_same_shape(tagger, scripted_generate, stub_embedder):
    scripted_generate('{"concepts": ["Bucles"], "primary_concept": "Bucles"}')
    tagged = tagger.tag("Recorre una lista.")

    scripted_generate('{"concepts": [], "primary_concept": null}')
    rejected = tagger.tag("Algo ajeno.")

    tagger.embedder = stub_embedder([])
    scripted_generate()
    no_candidates = tagger.tag("Algo ajeno.")

    assert tagged.keys() == rejected.keys() == no_candidates.keys()


# BULK TAGGING -------------------------------------------------------------------------------


def test_tag_all_annotates_every_item_preserving_its_fields(tagger, scripted_generate):
    scripted_generate(*(['{"concepts": ["Bucles"], "primary_concept": "Bucles"}'] * 4))
    bank = {
        "C001": {"statement": "Recorre una lista", "solution": "código", "source": "WB1"},
        "C002": {"statement": "Declara una variable", "solution": None, "source": "WB1"},
    }

    annotated = tagger.tag_all(bank)

    assert set(annotated) == {"C001", "C002"}
    assert annotated["C001"]["solution"] == "código"
    assert annotated["C001"]["source"] == "WB1"
    assert annotated["C001"]["primary_concept"] == "Bucles"


def test_tag_all_does_not_touch_the_input_bank(tagger, scripted_generate):
    scripted_generate(*(['{"concepts": ["Bucles"], "primary_concept": "Bucles"}'] * 4))
    bank = {"C001": {"statement": "Recorre una lista"}}

    tagger.tag_all(bank)

    assert bank == {"C001": {"statement": "Recorre una lista"}}


def test_tag_all_of_an_empty_bank(tagger, scripted_generate):
    scripted_generate()

    assert tagger.tag_all({}) == {}

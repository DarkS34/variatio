import json

import pytest

import main
from system import config
from tests.conftest import MIN_KG_PATH, MIN_PROFILE_PATH

TAGGED = '{"concepts": ["Bucles"], "primary_concept": "Bucles"}'
ITEM = (
    '{"statement": "Escribe una función que recorra una lista de precios.", '
    '"solution": "def f(xs): return sum(xs)", "difficulty_level": "intermedio", "tags": []}'
)

RAW_BANK = {
    "C001": {"statement": "Recorre una lista", "solution": None, "difficulty_level": "básico"},
    "C002": {"statement": "Declara una variable", "solution": None, "difficulty_level": "básico"},
}


@pytest.fixture
def wired(tmp_path, monkeypatch, scripted_embed):
    bank_path = tmp_path / "exemplars_bank.json"
    bank_path.write_text(json.dumps(RAW_BANK, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(config, "CONTENT_PROFILE_PATH", MIN_PROFILE_PATH)
    monkeypatch.setattr(config, "KG_PATH", MIN_KG_PATH)
    monkeypatch.setattr(config, "EXEMPLARS_BANK_PATH", bank_path)
    monkeypatch.setattr(config, "CONCEPT_DESCRIPTIONS_PATH", tmp_path / "descriptions.json")
    monkeypatch.setattr(config, "CONCEPTS_EMBEDDINGS_PATH", tmp_path / "concepts.npz")
    monkeypatch.setattr(config, "EXEMPLARS_BANK_EMBEDDINGS_PATH", tmp_path / "bank.npz")
    monkeypatch.setattr(main, "bootstrap", lambda: None)
    scripted_embed()

    return bank_path


@pytest.fixture
def responses(kg):
    def _build(n_items: int, tag_response: str = TAGGED) -> list[str]:
        return (
            ["una descripción de concepto"] * len(kg.taggable_concepts)
            + [tag_response] * len(RAW_BANK)
            + [ITEM] * n_items
        )

    return _build


def test_pipeline_runs_end_to_end(wired, scripted_generate, responses):
    scripted_generate(*responses(2))

    results = main.main(n=2)

    assert len(results) == 2


def test_generated_items_carry_exactly_the_profile_fields(
    wired, scripted_generate, responses, profile
):
    scripted_generate(*responses(2))

    results = main.main(n=2)

    for result in results:
        assert set(result.item.model_dump()) == set(profile.field_specs)


def test_generated_items_revalidate_against_a_freshly_loaded_profile(
    wired, scripted_generate, responses, profile
):
    scripted_generate(*responses(2))

    results = main.main(n=2)

    for result in results:
        profile.content_item(**result.item.model_dump())


def test_generated_items_honour_the_fixed_values(wired, scripted_generate, responses):
    scripted_generate(*responses(2))

    results = main.main(n=2)

    assert all(r.item.difficulty_level == "intermedio" for r in results)


def test_the_pipeline_persists_the_annotated_bank(wired, scripted_generate, responses):
    scripted_generate(*responses(2))

    main.main(n=2)

    stored = json.loads(wired.read_text(encoding="utf-8"))
    assert set(stored) == set(RAW_BANK)
    assert all("concepts" in item for item in stored.values())
    assert all(item["statement"] for item in stored.values())


def test_the_pipeline_writes_both_embedding_caches(
    wired, scripted_generate, responses, tmp_path
):
    scripted_generate(*responses(2))

    main.main(n=2)

    assert (tmp_path / "concepts.npz").exists()
    assert (tmp_path / "bank.npz").exists()
    assert (tmp_path / "descriptions.json").exists()


def test_target_concepts_come_from_the_taggable_set(wired, scripted_generate, responses, kg):
    calls = scripted_generate(*responses(2))

    main.main(n=2)

    generation_prompts = [c["prompt"] for c in calls if "CONCEPTOS OBJETIVO" in c["prompt"]]
    assert generation_prompts
    assert any(f"**{concept}**" in generation_prompts[0] for concept in kg.taggable_concepts)


def test_a_second_run_reuses_the_caches_and_skips_tagging(wired, scripted_generate, responses):
    scripted_generate(*responses(2))
    main.main(n=2)

    calls = scripted_generate(ITEM, ITEM)
    results = main.main(n=2)

    assert len(results) == 2
    assert len(calls) == 2


def test_the_pipeline_aborts_when_nothing_could_be_tagged(wired, scripted_generate, responses):
    scripted_generate(*responses(0, tag_response='{"concepts": [], "primary_concept": null}'))

    with pytest.raises(SystemExit):
        main.main(n=2)

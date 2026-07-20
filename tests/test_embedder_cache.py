import json

import numpy as np
import pytest

from system.embedder import Embedder

CONTEXT = {"materia": "Programación I"}


@pytest.fixture
def paths(tmp_path):
    return {
        "descriptions_path": tmp_path / "concept_descriptions.json",
        "concepts_cache_path": tmp_path / "embeddings" / "concepts.npz",
        "exemplars_bank_cache_path": tmp_path / "embeddings" / "bank.npz",
    }


@pytest.fixture
def descriptions(kg, paths):
    written = {c: f"descripción de {c}" for c in kg.taggable_concepts}
    paths["descriptions_path"].parent.mkdir(parents=True, exist_ok=True)
    paths["descriptions_path"].write_text(
        json.dumps(written, ensure_ascii=False), encoding="utf-8"
    )
    return written


@pytest.fixture
def build(kg, paths):
    def _build(model: str = "embed-model") -> Embedder:
        return Embedder(kg, model, primary_field="statement", context=CONTEXT, **paths)

    return _build


BANK = {
    "C001": {"statement": "Recorre una lista", "concepts": ["Bucles"]},
    "C002": {"statement": "Declara una variable", "concepts": ["Variables"]},
}


# CONCEPT INDEX ------------------------------------------------------------------------------


def test_embeds_every_taggable_concept_on_a_cold_start(build, descriptions, scripted_embed, kg):
    calls = scripted_embed()

    embedder = build()

    assert len(calls) == len(kg.taggable_concepts)
    assert set(embedder.concepts_index) == set(kg.taggable_concepts)


def test_embeds_the_description_not_the_concept_name(build, descriptions, scripted_embed):
    calls = scripted_embed()

    build()

    embedded = {c["text"] for c in calls}
    assert "descripción de Bucles" in embedded
    assert "Bucles" not in embedded


def test_writes_the_concept_cache_on_a_cold_start(build, descriptions, scripted_embed, paths):
    scripted_embed()

    build()

    assert paths["concepts_cache_path"].exists()


def test_a_warm_start_does_not_re_embed(build, descriptions, scripted_embed):
    scripted_embed()
    build()

    calls = scripted_embed()
    embedder = build()

    assert calls == []
    assert len(embedder.concepts_index) > 0


def test_a_changed_description_invalidates_the_concept_cache(
    build, descriptions, scripted_embed, paths
):
    scripted_embed()
    build()

    descriptions["Bucles"] = "otra descripción"
    paths["descriptions_path"].write_text(
        json.dumps(descriptions, ensure_ascii=False), encoding="utf-8"
    )
    calls = scripted_embed()
    build()

    assert len(calls) > 0


def test_a_changed_embedding_model_invalidates_the_concept_cache(
    build, descriptions, scripted_embed
):
    scripted_embed()
    build()

    calls = scripted_embed()
    build(model="otro-modelo")

    assert len(calls) > 0


def test_a_corrupt_concept_cache_is_rebuilt(build, descriptions, scripted_embed, paths):
    scripted_embed()
    build()
    paths["concepts_cache_path"].write_bytes(b"no soy un npz")

    calls = scripted_embed()
    embedder = build()

    assert len(calls) > 0
    assert len(embedder.concepts_index) > 0


# DESCRIPTIONS -------------------------------------------------------------------------------


def test_missing_descriptions_are_generated_and_persisted(
    build, paths, scripted_embed, scripted_generate, kg
):
    scripted_embed()
    scripted_generate(*(["una descripción"] * 20))

    build()

    stored = json.loads(paths["descriptions_path"].read_text(encoding="utf-8"))
    assert set(stored) == set(kg.taggable_concepts)


def test_only_the_missing_descriptions_are_generated(
    build, paths, descriptions, scripted_embed, scripted_generate, kg
):
    descriptions.pop("Bucles")
    paths["descriptions_path"].write_text(
        json.dumps(descriptions, ensure_ascii=False), encoding="utf-8"
    )
    scripted_embed()
    calls = scripted_generate(*(["descripción nueva"] * 20))

    build()

    assert len(calls) == 1


def test_a_failing_description_falls_back_to_the_graph(
    build, paths, scripted_embed, monkeypatch, kg
):
    from system import inference

    def _boom(model, prompt, think=None):
        raise RuntimeError("modelo caído")

    monkeypatch.setattr(inference, "generate", _boom)
    scripted_embed()

    embedder = build()

    assert 'Concepto: "Bucles".' in embedder.concept_descriptions["Bucles"]


# BANK INDEX ---------------------------------------------------------------------------------


def test_a_cold_start_leaves_the_merged_index_as_pure_concepts(
    build, descriptions, scripted_embed
):
    scripted_embed()

    embedder = build()

    for concept, vector in embedder.concepts_index.items():
        assert np.allclose(embedder.merged_index[concept], vector)


def test_enrich_embeds_every_bank_item(build, descriptions, scripted_embed):
    scripted_embed()
    embedder = build()

    calls = scripted_embed()
    embedder.enrich_index_with_content(BANK)

    assert [c["text"] for c in calls] == ["Recorre una lista", "Declara una variable"]


def test_enrich_merges_examples_into_their_concepts(build, descriptions, scripted_embed):
    scripted_embed()
    embedder = build()
    before = dict(embedder.merged_index)

    scripted_embed()
    embedder.enrich_index_with_content(BANK)

    assert not np.allclose(embedder.merged_index["Bucles"], before["Bucles"])
    assert np.allclose(embedder.merged_index["Condicionales"], before["Condicionales"])


def test_the_merged_vector_is_the_normalised_centroid(build, descriptions, scripted_embed):
    scripted_embed({"descripción de Bucles": [1.0, 0.0, 0.0], "Recorre una lista": [0.0, 1.0, 0.0]})
    embedder = build()
    scripted_embed({"descripción de Bucles": [1.0, 0.0, 0.0], "Recorre una lista": [0.0, 1.0, 0.0]})

    embedder.enrich_index_with_content({"C001": {"statement": "Recorre una lista", "concepts": ["Bucles"]}})

    expected = np.array([1.0, 1.0, 0.0]) / np.linalg.norm([1.0, 1.0, 0.0])
    assert np.allclose(embedder.merged_index["Bucles"], expected)


def test_enrich_is_idempotent_for_an_unchanged_bank(build, descriptions, scripted_embed):
    scripted_embed()
    embedder = build()
    scripted_embed()
    embedder.enrich_index_with_content(BANK)
    first = dict(embedder.merged_index)

    calls = scripted_embed()
    embedder.enrich_index_with_content(BANK)

    assert calls == []
    for concept, vector in first.items():
        assert np.allclose(embedder.merged_index[concept], vector)


def test_a_changed_bank_triggers_re_embedding(build, descriptions, scripted_embed):
    scripted_embed()
    embedder = build()
    scripted_embed()
    embedder.enrich_index_with_content(BANK)

    calls = scripted_embed()
    embedder.enrich_index_with_content({**BANK, "C003": {"statement": "Nuevo", "concepts": []}})

    assert len(calls) == 3


def test_the_next_run_warm_starts_from_the_persisted_bank_index(
    build, descriptions, scripted_embed
):
    scripted_embed()
    embedder = build()
    scripted_embed()
    embedder.enrich_index_with_content(BANK)
    enriched = dict(embedder.merged_index)

    scripted_embed()
    reloaded = build()

    assert set(reloaded.exemplars_bank_index) == {"C001", "C002"}
    assert np.allclose(reloaded.merged_index["Bucles"], enriched["Bucles"])


def test_a_reloaded_bank_keeps_only_the_concept_assignments(build, descriptions, scripted_embed):
    scripted_embed()
    embedder = build()
    scripted_embed()
    embedder.enrich_index_with_content(BANK)

    scripted_embed()
    reloaded = build()

    assert reloaded.exemplars_bank == {
        "C001": {"concepts": ["Bucles"]},
        "C002": {"concepts": ["Variables"]},
    }


# RETRIEVAL ----------------------------------------------------------------------------------


def test_top_k_concepts_ranks_by_cosine_similarity(build, descriptions, scripted_embed):
    scripted_embed(
        {
            "descripción de Bucles": [1.0, 0.0, 0.0],
            "descripción de Variables": [0.0, 1.0, 0.0],
            "consulta": [1.0, 0.0, 0.0],
        }
    )
    embedder = build()

    ranked = embedder.top_k_concepts("consulta", k=2)

    assert ranked[0][0] == "Bucles"
    assert ranked[0][1] == pytest.approx(1.0)


def test_top_k_concepts_drops_results_below_the_threshold(build, descriptions, scripted_embed):
    scripted_embed()
    embedder = build()
    embedder.similarity_threshold = 1.1

    assert embedder.top_k_concepts("cualquier cosa", k=5) == []


def test_top_k_concepts_never_returns_bank_items(build, descriptions, scripted_embed, kg):
    scripted_embed()
    embedder = build()
    scripted_embed()
    embedder.enrich_index_with_content(BANK)
    embedder.similarity_threshold = -1.0

    returned = {c for c, _ in embedder.top_k_concepts("consulta", k=50)}

    assert returned <= set(kg.taggable_concepts)

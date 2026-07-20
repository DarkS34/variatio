import numpy as np
import pytest


def test_collect_relations_skips_relations_not_used_in_embedding(embedder):
    relations = embedder._collect_relations("Bucles")

    assert relations == {"es un tipo de este concepto": ["Bucle for", "Bucle while"]}


def test_collect_relations_skips_prerequisites_in_both_directions(embedder):
    outgoing = embedder._collect_relations("Bucles")
    incoming = embedder._collect_relations("Variables")

    assert not any("prerrequisito" in verb for verb in outgoing)
    assert not any("prerrequisito" in verb for verb in incoming)


def test_collect_relations_keeps_undirected_relations(embedder):
    assert embedder._collect_relations("Variables") == {
        "se relaciona con": ["Tipos de datos"]
    }


def test_collect_relations_labels_successors_as_outgoing(embedder):
    assert embedder._collect_relations("Bucle for") == {
        "este concepto es un tipo de": ["Bucles"]
    }


def test_collect_relations_is_empty_for_isolated_concept(embedder):
    assert embedder._collect_relations("Programación") == {}


def test_collect_relations_and_simple_describe_agree_on_which_relations_count(embedder):
    collected = embedder._collect_relations("Bucles")
    described = embedder._simple_describe("Bucles")

    assert not any("prerrequisito" in verb for verb in collected)
    assert "prerrequisito" not in described


def test_simple_describe_states_relations_in_the_same_sense_as_collect(embedder):
    described = embedder._simple_describe("Bucles")

    assert "es un tipo de este concepto: Bucle for, Bucle while." in described
    assert "Este concepto es un tipo de" not in described


def test_simple_describe_reports_the_concept_and_its_domain(embedder):
    described = embedder._simple_describe("Bucles")

    assert described.startswith('Concepto: "Bucles".\nDominio: "Control de flujo"')


def test_simple_describe_never_contradicts_collect_relations(embedder):
    for concept in embedder.knowledge_graph.taggable_concepts:
        described = embedder._simple_describe(concept)
        for verb, neighbors in embedder._collect_relations(concept).items():
            assert f'{verb}: {", ".join(neighbors)}.' in described


def test_l2_normalize_produces_unit_vector(embedder):
    normalized = embedder._l2_normalize(np.array([3.0, 4.0]))

    assert np.linalg.norm(normalized) == pytest.approx(1.0)


def test_l2_normalize_leaves_zero_vector_untouched(embedder):
    zero = np.zeros(3)

    assert np.array_equal(embedder._l2_normalize(zero), zero)


def test_cosine_similarity_of_normalized_vectors(embedder):
    a = embedder._l2_normalize(np.array([1.0, 1.0]))
    b = embedder._l2_normalize(np.array([1.0, 0.0]))

    assert embedder.cosine_similarity(a, a) == pytest.approx(1.0)
    assert embedder.cosine_similarity(a, b) == pytest.approx(0.70710678)


def _fingerprint(embedder, model: str, descriptions: dict[str, str]) -> str:
    embedder.embedding_model = model
    embedder.concept_descriptions = descriptions
    return embedder._concept_fingerprint()


def test_concept_fingerprint_is_stable_for_same_state(embedder):
    descriptions = {c: f"desc {c}" for c in embedder.knowledge_graph.taggable_concepts}

    first = _fingerprint(embedder, "model-a", descriptions)
    second = _fingerprint(embedder, "model-a", dict(descriptions))

    assert first == second


def test_concept_fingerprint_changes_when_a_description_changes(embedder):
    descriptions = {c: f"desc {c}" for c in embedder.knowledge_graph.taggable_concepts}
    before = _fingerprint(embedder, "model-a", descriptions)

    changed = dict(descriptions)
    changed["Bucles"] = "otra descripción"
    after = _fingerprint(embedder, "model-a", changed)

    assert before != after


def test_concept_fingerprint_changes_when_model_changes(embedder):
    descriptions = {c: f"desc {c}" for c in embedder.knowledge_graph.taggable_concepts}

    before = _fingerprint(embedder, "model-a", descriptions)
    after = _fingerprint(embedder, "model-b", descriptions)

    assert before != after

import pytest

from variatio import config
from variatio.variatio import NEIGHBOUR, VariantGenerator, build_few_shot_block


class _FakeEmbedder:
    def rank_exemplars(self, concepts, exemplar_ids):
        return list(exemplar_ids)


def _exemplar(text: str, concepts: list[str], primary: str) -> dict:
    return {
        "item_type": "ejercicio",
        "enunciado": text,
        "concepts": concepts,
        "primary_concept": primary,
    }


def _bank(*primaries: str) -> dict:
    return {
        f"ex{i}": _exemplar(f"Ejercicio {i} sobre {primary}", [primary], primary)
        for i, primary in enumerate(primaries, start=1)
    }


def _generator(graph, profile, bank: dict, max_few_shot: int = 3) -> VariantGenerator:
    generator = object.__new__(VariantGenerator)
    generator.knowledge_graph = graph
    generator.exemplars_profile = profile
    generator.exemplars_bank = bank
    generator.embedder = _FakeEmbedder()
    generator.max_few_shot = max_few_shot
    return generator


@pytest.fixture(autouse=True)
def _prerequisite_relation(monkeypatch):
    monkeypatch.setattr(config, "KG_PREREQUISITE_RELATION", "tiene como prerrequisito")


def _ids(chosen):
    return [ex_id for ex_id, _ in chosen]


def test_enough_primary_exemplars_leave_the_neighbours_untouched(graph, profile):
    bank = _bank("Recursividad", "Recursividad", "Recursividad", "Función")
    generator = _generator(graph, profile, bank, max_few_shot=3)
    chosen, origins = generator._select_few_shot(profile.item_type("ejercicio"), ["Recursividad"], {})
    assert len(chosen) == 3
    assert set(_ids(chosen)) == {"ex1", "ex2", "ex3"}
    assert set(origins.values()) == {"primary"}


def test_without_on_target_exemplars_the_direct_prerequisite_fills_the_gap(graph, profile):
    bank = _bank("Función", "Memoización", "Función")
    generator = _generator(graph, profile, bank, max_few_shot=3)
    chosen, origins = generator._select_few_shot(profile.item_type("ejercicio"), ["Recursividad"], {})
    assert _ids(chosen) == ["ex1", "ex3"]
    assert origins == {"ex1": NEIGHBOUR, "ex3": NEIGHBOUR}


def test_the_two_hop_prerequisite_is_not_a_neighbour(graph, profile):
    bank = _bank("Variable", "Variable")
    generator = _generator(graph, profile, bank, max_few_shot=3)
    chosen, origins = generator._select_few_shot(profile.item_type("ejercicio"), ["Recursividad"], {})
    assert chosen == []
    assert origins == {}


def test_neighbours_only_top_up_after_the_tag_pools(graph, profile):
    bank = _bank("Recursividad", "Función", "Función", "Función")
    bank["ex5"] = _exemplar("Usa recursividad de pasada", ["Recursividad", "Función"], "Función")
    generator = _generator(graph, profile, bank, max_few_shot=3)
    chosen, origins = generator._select_few_shot(profile.item_type("ejercicio"), ["Recursividad"], {})
    assert _ids(chosen) == ["ex1", "ex5", "ex2"]
    assert origins == {"ex1": "primary", "ex5": "secondary", "ex2": NEIGHBOUR}


def test_a_neighbour_is_labelled_as_a_prior_concept_in_the_prompt(profile):
    item_type = profile.item_type("ejercicio")
    items = [
        {"enunciado": "Ejercicio sobre recursividad", "primary_concept": "Recursividad"},
        {"enunciado": "Ejercicio sobre funciones", "primary_concept": "Función"},
    ]
    plain = build_few_shot_block(item_type, items)
    labelled = build_few_shot_block(item_type, items, ["primary", NEIGHBOUR])
    label = "(Ejemplo de un concepto previo: «Función». Referencia de forma, no del objetivo.)"
    assert label not in plain
    assert labelled.count("(Ejemplo de un concepto previo") == 1
    assert label in labelled
    assert labelled.index(label) < labelled.index("Ejercicio sobre funciones")
    assert labelled.index(label) > labelled.index("Ejercicio sobre recursividad")

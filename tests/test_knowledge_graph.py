import networkx as nx
import pytest


def test_loads_concepts_grouped_by_domain(kg):
    assert kg.concepts_by_domains["Fundamentos"] == [
        "Variables",
        "Tipos de datos",
        "Programación",
    ]
    assert len(kg.all_concepts) == 7


def test_concept_domain_is_inverted_index(kg):
    assert kg.concept_domain["Bucle for"] == "Control de flujo"
    assert kg.concept_domain["Variables"] == "Fundamentos"


def test_taggable_concepts_exclude_generic_ones(kg):
    assert "Programación" in kg.all_concepts
    assert "Programación" not in kg.taggable_concepts
    assert len(kg.taggable_concepts) == 6


def test_graphs_are_keyed_by_verbose_name(kg):
    assert set(kg.graphs) == {
        "tiene como prerrequisito",
        "es un tipo de",
        "se relaciona con",
    }


def test_directedness_follows_relation_details(kg):
    assert isinstance(kg["tiene como prerrequisito"], nx.DiGraph)
    assert not isinstance(kg["se relaciona con"], nx.DiGraph)


def test_every_concept_is_a_node_in_every_graph(kg):
    for graph in kg.graphs.values():
        assert set(graph.nodes) == set(kg.all_concepts)


def test_details_exposes_relation_metadata(kg):
    assert kg.details("tiene como prerrequisito")["use_in_embedding"] is False
    assert kg.details("es un tipo de")["use_in_embedding"] is True


def test_loader_is_agnostic_to_the_relation_set(write_kg, min_kg_data):
    min_kg_data["relations"].append(
        {
            "details": {
                "verbose": "se evalúa con",
                "directed": True,
                "acyclic": False,
                "use_in_embedding": True,
            },
            "relations_data": {"Bucles": ["Condicionales"]},
        }
    )
    graph = write_kg(min_kg_data)

    assert "se evalúa con" in graph.graphs
    assert graph.neighbors("Bucles", "se evalúa con", direction="out") == ["Condicionales"]


def test_neighbors_walks_a_directed_relation_in_both_senses(kg):
    assert kg.neighbors("Bucles", "tiene como prerrequisito", direction="out") == ["Variables"]
    assert kg.neighbors("Variables", "tiene como prerrequisito", direction="in") == ["Bucles"]


def test_neighbors_ignores_direction_on_an_undirected_relation(kg):
    assert kg.neighbors("Variables", "se relaciona con", direction="out") == ["Tipos de datos"]
    assert kg.neighbors("Variables", "se relaciona con", direction="in") == ["Tipos de datos"]


def test_neighbors_is_empty_for_an_isolated_concept(kg):
    assert kg.neighbors("Programación", "es un tipo de", direction="out") == []


def test_neighbors_defaults_to_the_outgoing_direction(kg):
    assert kg.neighbors("Bucles", "tiene como prerrequisito") == ["Variables"]


def test_neighbors_always_returns_a_sorted_list(kg):
    for direction in ("out", "in"):
        for relation in kg.graphs:
            result = kg.neighbors("Bucles", relation, direction=direction)
            assert isinstance(result, list)
            assert result == sorted(result)


def test_neighbors_rejects_an_unknown_direction(kg):
    with pytest.raises(ValueError, match="direction must be"):
        kg.neighbors("Bucles", "tiene como prerrequisito", direction="sideways")


def test_cycle_in_acyclic_relation_is_reported(write_kg, min_kg_data, captured_logs):
    min_kg_data["relations"][0]["relations_data"] = {
        "Bucles": ["Variables"],
        "Variables": ["Bucles"],
    }
    write_kg(min_kg_data)

    errors = [r for r in captured_logs if r["level"].name == "ERROR"]
    assert any("Cycle detected" in r["message"] for r in errors)


def test_acyclic_without_directed_skips_validation(write_kg, min_kg_data, captured_logs):
    min_kg_data["relations"][0]["details"]["directed"] = False
    write_kg(min_kg_data)

    warnings = [r for r in captured_logs if r["level"].name == "WARNING"]
    assert any("skipping cycle validation" in r["message"] for r in warnings)

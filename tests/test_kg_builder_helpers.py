import pytest

from builders.knowledge_graph_builder import KnowledgeGraphBuilder as KGB


# NORMALISATION ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Bucles", "bucle"),
        ("bucles", "bucle"),
        ("BUCLES", "bucle"),
        ("  Bucles  ", "bucle"),
        ("Recursión", "recursion"),
        ("Listas en Python", "lista"),
        ("Listas en Java", "lista"),
        ("Listas   anidadas", "listas anidada"),
        ("os", "os"),
        ("abcs", "abc"),
    ],
)
def test_norm_key_folds_mechanical_variants(raw, expected):
    assert KGB._norm_key(raw) == expected


def test_norm_key_only_singularises_the_last_word():
    assert KGB._norm_key("Listas anidadas") != KGB._norm_key("Lista anidadas")


def test_norm_key_keeps_parenthesised_complexities_apart():
    assert KGB._norm_key("O(n)") != KGB._norm_key("O(log n)")


def test_deterministic_merge_prefers_capitalised_and_short():
    variant_to_canon, representatives = KGB._deterministic_merge(["Bucles", "bucles", "Bucle"])

    assert representatives == ["Bucle"]
    assert variant_to_canon == {"Bucles": "Bucle", "bucles": "Bucle", "Bucle": "Bucle"}


def test_deterministic_merge_keeps_distinct_concepts_apart():
    _, representatives = KGB._deterministic_merge(["Bucles", "Variables", "Recursión"])

    assert representatives == ["Bucles", "Recursión", "Variables"]


# GRAPH SHAPING ------------------------------------------------------------------------------


def test_node_universe_includes_dangling_relation_endpoints():
    graph = {"entities": ["A"], "relations": [["A", "rel", "B"], ["C", "rel", "A"]]}

    assert KGB._node_universe(graph) == ["A", "B", "C"]


def test_nodes_block_attaches_outgoing_relations_as_evidence():
    block = KGB._nodes_block(
        ["Bucles"], [["Bucles", "incluye", "Bucle for"]], {"Bucle for": "Bucle for"}
    )

    assert block == "- Bucles  [incluye Bucle for]"


def test_nodes_block_remaps_endpoints_through_the_deterministic_map():
    block = KGB._nodes_block(["Bucles"], [["bucles", "incluye", "for"]], {"bucles": "Bucles", "for": "Bucle for"})

    assert block == "- Bucles  [incluye Bucle for]"


def test_nodes_block_caps_evidence_at_six_relations():
    relations = [["A", "rel", f"T{i}"] for i in range(10)]

    assert KGB._nodes_block(["A"], relations, {}).count(";") == 5


def test_nodes_block_omits_evidence_for_isolated_nodes():
    assert KGB._nodes_block(["A"], [], {}) == "- A"


# ALIAS MAPPING ------------------------------------------------------------------------------


def test_llm_alias_map_rewrites_aliases_onto_the_canonical():
    alias_map = KGB._llm_alias_map({"Bucles": ["bucles", "Bucle"]}, {"Bucles", "bucles", "Bucle"})

    assert alias_map == {"Bucles": "Bucles", "bucles": "Bucles", "Bucle": "Bucles"}


def test_llm_alias_map_falls_back_when_the_canonical_was_invented():
    alias_map = KGB._llm_alias_map({"Inventado": ["Bucles"]}, {"Bucles"})

    assert alias_map == {"Bucles": "Bucles"}


def test_llm_alias_map_drops_groups_with_no_surviving_member():
    assert KGB._llm_alias_map({"Inventado": ["Tampoco"]}, {"Bucles"}) == {}


def test_compose_marks_dropped_nodes_as_none():
    node_map = KGB._compose_node_map(
        ["Bucles", "bucles", "Ruido"],
        {"bucles": "Bucles", "Ruido": "Ruido"},
        {"Bucles": "Bucles"},
        {"Ruido"},
    )

    assert node_map == {"Bucles": "Bucles", "bucles": "Bucles", "Ruido": None}


def test_apply_keeps_only_relations_whose_endpoints_survive():
    graph = {
        "entities": ["A", "B", "C"],
        "relations": [["A", "rel", "B"], ["A", "rel", "C"], ["B", "rel", "C"]],
    }

    cleaned = KGB._apply_node_map(graph, {"A": "A", "B": "B", "C": None})

    assert cleaned == {"entities": ["A", "B"], "edges": ["rel"], "relations": [["A", "rel", "B"]]}


def test_apply_rewrites_endpoints_through_the_node_map():
    graph = {"entities": ["a", "B"], "relations": [["a", "rel", "B"]]}

    cleaned = KGB._apply_node_map(graph, {"a": "A", "B": "B"})

    assert cleaned["entities"] == ["A", "B"]
    assert cleaned["relations"] == [["A", "rel", "B"]]


def test_apply_deduplicates_relations_collapsed_by_the_merge():
    graph = {"entities": ["a", "A", "B"], "relations": [["a", "rel", "B"], ["A", "rel", "B"]]}

    cleaned = KGB._apply_node_map(graph, {"a": "A", "A": "A", "B": "B"})

    assert cleaned["relations"] == [["A", "rel", "B"]]


# DOMAIN RECONCILIATION ----------------------------------------------------------------------


def test_reconcile_domains_places_every_concept_exactly_once():
    by_domain, non_taggable = KGB._reconcile_domains(
        ["A", "B", "C"], {"Uno": ["A", "B"], "Dos": ["C"]}, []
    )

    assert by_domain == {"Uno": ["A", "B"], "Dos": ["C"]}
    assert non_taggable == []


def test_reconcile_domains_sends_unplaced_concepts_to_the_catch_all():
    by_domain, _ = KGB._reconcile_domains(["A", "B"], {"Uno": ["A"]}, [])

    assert by_domain == {"Uno": ["A"], "Sin clasificar": ["B"]}


def test_reconcile_domains_keeps_the_first_home_of_a_duplicated_concept():
    by_domain, _ = KGB._reconcile_domains(["A"], {"Uno": ["A"], "Dos": ["A"]}, [])

    assert by_domain == {"Uno": ["A"]}


def test_reconcile_domains_discards_concepts_the_model_invented():
    by_domain, non_taggable = KGB._reconcile_domains(["A"], {"Uno": ["A", "Inventado"]}, ["Otro"])

    assert by_domain == {"Uno": ["A"]}
    assert non_taggable == []


def test_reconcile_domains_ignores_malformed_domain_entries():
    by_domain, _ = KGB._reconcile_domains(["A"], {"Uno": "A", "Dos": ["A"]}, [])

    assert by_domain == {"Dos": ["A"]}


# RELATION TYPING ----------------------------------------------------------------------------


def test_edges_block_shows_one_example_per_verb():
    block = KGB._edges_block(
        ["incluye"], [["Bucles", "incluye", "Bucle for"], ["A", "incluye", "B"]]
    )

    assert block == '- "incluye"  (p.ej. Bucles → Bucle for)'


def test_edges_block_handles_a_verb_without_examples():
    assert KGB._edges_block(["huérfano"], []) == '- "huérfano"'


def test_build_typed_relations_groups_by_canonical_type():
    typed = KGB._build_typed_relations(
        {"requiere": "prerrequisito", "incluye": "parte_de"},
        [["A", "requiere", "B"], ["C", "incluye", "D"]],
        {"A", "B", "C", "D"},
    )

    assert [t["details"]["verbose"] for t in typed] == ["tiene como prerrequisito", "es parte de"]
    assert typed[0]["relations_data"] == {"A": ["B"]}


def test_build_typed_relations_defaults_unknown_verbs_to_relacionado():
    typed = KGB._build_typed_relations({}, [["A", "verbo raro", "B"]], {"A", "B"})

    assert len(typed) == 1
    assert typed[0]["details"]["verbose"] == "se relaciona con"


def test_build_typed_relations_drops_endpoints_outside_the_universe():
    typed = KGB._build_typed_relations({"rel": "relacionado"}, [["A", "rel", "Fuera"]], {"A"})

    assert typed == []


def test_build_typed_relations_deduplicates_targets():
    typed = KGB._build_typed_relations(
        {"rel": "relacionado"}, [["A", "rel", "B"], ["A", "rel", "B"]], {"A", "B"}
    )

    assert typed[0]["relations_data"] == {"A": ["B"]}


def test_build_typed_relations_does_not_alias_the_relation_type_table():
    typed = KGB._build_typed_relations({"rel": "relacionado"}, [["A", "rel", "B"]], {"A", "B"})
    typed[0]["details"]["verbose"] = "MUTADO"

    assert KGB.RELATION_TYPES["relacionado"]["verbose"] == "se relaciona con"

import json
from types import SimpleNamespace

from variant_generator import config
from variant_generator.builders.knowledge_graph_builder import (
    blocks,
    cleaning,
    curation,
    extraction,
    parsing,
)
from variant_generator.instance.relations import RELATION_SCHEMA_ES as SCHEMA

PREREQ = SCHEMA.prerequisite_verbose
EMPTY = '{"concepts": [], "relations": []}'


def details(verbose: str, acyclic: bool = True) -> dict:
    return {"verbose": verbose, "directed": True, "acyclic": acyclic, "use_in_embedding": False}


# PARSING -----------------------------------------------------------------------------------


def test_concepts_arrive_as_objects_or_bare_strings():
    names, definitions = parsing.concepts_with_definitions(
        [
            {"name": " Variable ", "definition": "Un nombre ligado a un valor."},
            "Bucle",
            {"name": "", "definition": "nada"},
            {"name": "Variable", "definition": "otra"},
            7,
        ]
    )
    assert names == ["Variable", "Bucle"]
    assert definitions == {"Variable": "Un nombre ligado a un valor."}


def test_a_long_definition_is_clipped_on_a_word():
    clipped = parsing.clip_definition("palabra " * 80)
    assert len(clipped) <= config.KG_DEFINITION_MAX_CHARS + 1
    assert clipped.endswith("…") and not clipped.endswith(" …")


# EXTRACTION --------------------------------------------------------------------------------


def answers(monkeypatch, *responses: str) -> list[str]:
    prompts: list[str] = []
    queue = list(responses)

    def fake_generate(*, model, prompt, think, format, temperature):
        prompts.append(prompt)
        return SimpleNamespace(response=queue.pop(0) if queue else EMPTY)

    monkeypatch.setattr(extraction.inference, "generate", fake_generate)
    return prompts


def concept(name: str, definition: str = "") -> dict:
    return {"name": name, "definition": definition or f"Definición de {name}."}


def test_positions_record_the_first_chunk_a_concept_is_seen_in(monkeypatch):
    monkeypatch.setattr(config, "KG_EXTRACT_GLEANING_PASSES", 0)
    first = json.dumps({"concepts": [concept("Variable")], "relations": []})
    second = json.dumps(
        {
            "concepts": [concept("Bucle"), concept("Variable", "Otra definición.")],
            "relations": [["Bucle", "prerrequisito", "Variable"]],
        }
    )
    answers(monkeypatch, first, second)
    documents = [("doc.md", [], [("Tema 1", [], "texto uno"), ("Tema 2", [], "texto dos")])]

    found = extraction.extract_documents(documents, schema=SCHEMA, max_attempts=1)

    assert found["positions"] == {"Variable": 1, "Bucle": 2}
    assert found["definitions"]["Variable"] == "Definición de Variable."
    assert ("Bucle", "prerrequisito", "Variable") in found["relations"]


def test_positions_run_across_documents(monkeypatch):
    monkeypatch.setattr(config, "KG_EXTRACT_GLEANING_PASSES", 0)
    answers(
        monkeypatch,
        json.dumps({"concepts": [concept("A")], "relations": []}),
        json.dumps({"concepts": [concept("B")], "relations": []}),
    )
    documents = [("uno.md", [], [("", [], "x")]), ("dos.md", [], [("", [], "y")])]
    found = extraction.extract_documents(documents, schema=SCHEMA, max_attempts=1)
    assert found["positions"] == {"A": 1, "B": 2}


def test_gleaning_adds_what_the_first_reading_missed(monkeypatch):
    monkeypatch.setattr(config, "KG_EXTRACT_GLEANING_PASSES", 2)
    first = json.dumps({"concepts": [concept("Variable"), concept("Bucle")], "relations": []})
    gleaned = json.dumps(
        {
            "concepts": [concept("Variable", "repetida"), concept("Condición")],
            "relations": [["Bucle", "prerrequisito", "Variable"]],
        }
    )
    prompts = answers(monkeypatch, first, gleaned, EMPTY)

    concepts, relations, definitions = extraction.extract_from_chunk(
        "texto", "[t] ", "", schema=SCHEMA, max_attempts=1
    )
    concepts, relations, definitions = extraction.glean_chunk(
        "texto", "[t] ", "", concepts, relations, definitions, schema=SCHEMA, max_attempts=1
    )

    assert concepts == ["Variable", "Bucle", "Condición"]
    assert relations == [["Bucle", "prerrequisito", "Variable"]]
    assert definitions["Variable"] == "Definición de Variable."
    assert len(prompts) == 3
    assert "- Variable — Definición de Variable." in prompts[1]
    assert '["Bucle", "prerrequisito", "Variable"]' in prompts[2]


def test_gleaning_stops_as_soon_as_a_pass_adds_nothing(monkeypatch):
    monkeypatch.setattr(config, "KG_EXTRACT_GLEANING_PASSES", 3)
    prompts = answers(monkeypatch, EMPTY)
    extraction.glean_chunk("texto", "[t] ", "", ["A"], [], {}, schema=SCHEMA, max_attempts=1)
    assert len(prompts) == 1


def test_gleaning_is_skipped_when_the_first_reading_found_nothing(monkeypatch):
    prompts = answers(monkeypatch)
    extraction.glean_chunk("texto", "[t] ", "", [], [], {}, schema=SCHEMA, max_attempts=1)
    assert prompts == []


def test_occurrences_record_only_extractions_and_not_relation_endpoints(monkeypatch):
    monkeypatch.setattr(config, "KG_EXTRACT_GLEANING_PASSES", 0)
    first = json.dumps(
        {
            "concepts": [concept("Bucle")],
            "relations": [["Bucle", "prerrequisito", "Recursividad"]],
        }
    )
    second = json.dumps({"concepts": [concept("Recursividad")], "relations": []})
    answers(monkeypatch, first, second)
    documents = [("doc.md", [], [("", [], "uno"), ("", [], "dos")])]

    found = extraction.extract_documents(documents, schema=SCHEMA, max_attempts=1)

    assert found["positions"]["Recursividad"] == 1
    assert found["occurrences"]["Recursividad"] == [2]
    assert found["occurrences"]["Bucle"] == [1]


def test_occurrences_accumulate_every_chunk_a_concept_is_extracted_from(monkeypatch):
    monkeypatch.setattr(config, "KG_EXTRACT_GLEANING_PASSES", 0)
    body = json.dumps({"concepts": [concept("Lista")], "relations": []})
    answers(monkeypatch, body, body, body)
    documents = [("doc.md", [], [("", [], "a"), ("", [], "b"), ("", [], "c")])]

    found = extraction.extract_documents(documents, schema=SCHEMA, max_attempts=1)

    assert found["occurrences"]["Lista"] == [1, 2, 3]


def test_the_outline_keeps_duplicates_and_the_order_of_the_corpus(monkeypatch):
    monkeypatch.setattr(config, "KG_EXTRACT_GLEANING_PASSES", 0)
    answers(monkeypatch)
    documents = [
        ("uno.md", [], [("", ["Tema I", "Ejemplo"], "a"), ("", ["Tema II"], "b")]),
        ("dos.md", [], [("", ["Ejemplo"], "c")]),
    ]

    found = extraction.extract_documents(documents, schema=SCHEMA, max_attempts=1)

    assert found["outline"] == [
        {"document": 0, "heading": "Tema I", "chunk": 1},
        {"document": 0, "heading": "Ejemplo", "chunk": 1},
        {"document": 0, "heading": "Tema II", "chunk": 2},
        {"document": 1, "heading": "Ejemplo", "chunk": 3},
    ]


# CLEANING ----------------------------------------------------------------------------------


def test_merging_keeps_the_earliest_position_and_its_definition():
    graph = {
        "entities": ["Lista", "Listas"],
        "relations": [],
        "origins": {"Lista": [0], "Listas": [0]},
        "passages": {},
        "positions": {"Lista": 7, "Listas": 2},
        "definitions": {"Lista": "la tardía", "Listas": "la temprana"},
    }
    cleaned = cleaning.apply_node_map(graph, {"Lista": "Lista", "Listas": "Lista"})
    assert cleaned["positions"] == {"Lista": 2}
    assert cleaned["definitions"] == {"Lista": "la temprana"}


def test_a_dropped_node_takes_its_position_and_definition_with_it():
    graph = {
        "entities": ["A", "Ruido"],
        "relations": [],
        "origins": {},
        "passages": {},
        "positions": {"A": 1, "Ruido": 2},
        "definitions": {"A": "a", "Ruido": "r"},
    }
    cleaned = cleaning.apply_node_map(graph, {"A": "A", "Ruido": None})
    assert cleaned["positions"] == {"A": 1}
    assert cleaned["definitions"] == {"A": "a"}


def test_merging_unions_the_occurrences_rather_than_keeping_the_earliest():
    graph = {
        "entities": ["Lista", "Listas"],
        "relations": [],
        "origins": {},
        "passages": {},
        "positions": {"Lista": 7, "Listas": 2},
        "occurrences": {"Lista": [7, 9], "Listas": [2, 7]},
        "definitions": {},
    }
    cleaned = cleaning.apply_node_map(graph, {"Lista": "Lista", "Listas": "Lista"})
    assert cleaned["positions"] == {"Lista": 2}
    assert cleaned["occurrences"] == {"Lista": [2, 7, 9]}


def test_a_dropped_node_takes_its_occurrences_with_it():
    graph = {
        "entities": ["A", "Ruido"],
        "relations": [],
        "origins": {},
        "passages": {},
        "positions": {},
        "occurrences": {"A": [1], "Ruido": [2]},
        "definitions": {},
    }
    cleaned = cleaning.apply_node_map(graph, {"A": "A", "Ruido": None})
    assert cleaned["occurrences"] == {"A": [1]}


def test_the_outline_passes_through_the_cleaning_untouched():
    outline = [{"document": 0, "heading": "Tema I", "chunk": 1}]
    graph = {
        "entities": ["A"],
        "relations": [],
        "origins": {},
        "passages": {},
        "positions": {},
        "occurrences": {},
        "definitions": {},
        "outline": outline,
    }
    assert cleaning.apply_node_map(graph, {"A": "A"})["outline"] == outline


# BLOCKS ------------------------------------------------------------------------------------


def test_ordered_follows_the_material_and_parks_the_unknown_last():
    assert blocks.ordered(["C", "A", "B", "Z"], {"A": 3, "B": 1, "C": 2}) == ["B", "C", "A", "Z"]


def test_nodes_block_writes_the_definition_beside_the_name():
    block = blocks.nodes_block(["A", "B"], [], {}, definitions={"A": "una idea"})
    assert block == "- A — una idea\n- B"


# CURATION ----------------------------------------------------------------------------------


def test_domains_are_ordered_by_the_median_position_of_their_members():
    unclassified = config.KG_BUILDER_UNCLASSIFIED_DOMAIN
    by_domain = {
        "Tarde": ["T1", "T2"],
        "Pronto": ["P2", "P1"],
        unclassified: ["X"],
        "Sin posiciones": ["S"],
    }
    positions = {"T1": 10, "T2": 12, "P1": 1, "P2": 3}
    ordered = curation.order_domains(by_domain, positions)
    assert list(ordered) == ["Pronto", "Tarde", "Sin posiciones", unclassified]
    assert ordered["Pronto"] == ["P1", "P2"]


def test_the_linking_prompt_lists_the_domain_in_the_order_of_the_material(monkeypatch):
    prompts: list[str] = []

    def fake_generate(*, model, prompt, think, temperature):
        prompts.append(prompt)
        return SimpleNamespace(response='{"relations": []}')

    monkeypatch.setattr(curation.inference, "generate", fake_generate)
    by_domain = curation.order_domains(
        {"D": ["Recursividad", "Variable", "Función"]},
        {"Variable": 1, "Función": 5, "Recursividad": 9},
    )
    curation.link_relations(
        by_domain, [], {"Variable": "Un nombre ligado a un valor."}, schema=SCHEMA, max_attempts=1
    )
    body = prompts[0].split("EN EL ORDEN DEL MATERIAL")[-1]
    assert body.index("Variable") < body.index("Función") < body.index("Recursividad")
    assert "- Variable — Un nombre ligado a un valor." in body


def test_break_cycles_removes_the_edge_that_contradicts_the_material():
    typed = [
        {"details": details(PREREQ), "relations_data": {"B": ["A"], "C": ["B"], "A": ["C"]}}
    ]
    result = curation.break_cycles(typed, {"A": 1, "B": 2, "C": 3}, PREREQ)
    assert result[0]["relations_data"] == {"B": ["A"], "C": ["B"]}


def test_break_cycles_falls_back_to_the_back_edge_without_positions():
    typed = [{"details": details(PREREQ), "relations_data": {"A": ["B"], "B": ["A"]}}]
    data = curation.break_cycles(typed)[0]["relations_data"]
    assert sum(len(v) for v in data.values()) == 1


def test_break_cycles_leaves_other_acyclic_relations_on_the_old_rule():
    typed = [
        {
            "details": details("otra dirigida"),
            "relations_data": {"B": ["A"], "C": ["B"], "A": ["C"]},
        }
    ]
    data = curation.break_cycles(typed, {"A": 1, "B": 2, "C": 3}, PREREQ)[0]["relations_data"]
    assert sum(len(v) for v in data.values()) == 2


def test_most_backwards_picks_the_largest_lag():
    cycle = [("B", "A"), ("C", "B"), ("A", "C")]
    assert curation.most_backwards(cycle, {"A": 1, "B": 2, "C": 3}) == ("A", "C")

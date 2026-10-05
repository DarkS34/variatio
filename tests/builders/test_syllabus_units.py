import json
from types import SimpleNamespace

from variatio import config
from variatio.builders.knowledge_graph_builder import blocks, curation
from variatio.prompts.es import segment_syllabus_prompt

from ..conftest import ES

OUTLINE = [
    {"document": 0, "heading": "Índice", "chunk": 1},
    {"document": 0, "heading": "Tema I", "chunk": 2},
    {"document": 0, "heading": "Un ejemplo", "chunk": 3},
    {"document": 0, "heading": "Tema II", "chunk": 5},
    {"document": 0, "heading": "Tema III", "chunk": 9},
]


def answer(monkeypatch, response: str) -> list[str]:
    prompts: list[str] = []

    def fake_generate(*, model, prompt, think, format, sampling):
        prompts.append(prompt)
        return SimpleNamespace(response=response)

    monkeypatch.setattr(curation.inference, "generate", fake_generate)
    return prompts


def units(*pairs) -> str:
    return json.dumps({"units": [{"name": n, "opens_at": p} for n, p in pairs]})


# THE BLOCK -----------------------------------------------------------------------------


def test_the_outline_block_numbers_the_entries_from_one():
    block = blocks.outline_block(OUTLINE, [{"name": "apuntes.pdf"}])
    assert block.splitlines()[0] == "1. Índice"
    assert block.splitlines()[3] == "4. Tema II"


def test_the_outline_block_names_the_document_only_when_there_is_more_than_one():
    one = blocks.outline_block(OUTLINE, [{"name": "apuntes.pdf"}])
    many = blocks.outline_block(OUTLINE, [{"name": "apuntes.pdf"}, {"name": "otro.pdf"}])
    assert "apuntes.pdf" not in one
    assert "apuntes.pdf" in many


def test_every_number_the_block_prints_resolves_back_to_that_same_entry():
    lines = blocks.outline_block(OUTLINE, []).splitlines()
    assert len(lines) == len(OUTLINE)
    proposed = [
        {"name": f"U{line.split('.', 1)[0]}", "opens_at": int(line.split(".", 1)[0])}
        for line in lines
    ]
    accepted = curation.accept_units(proposed, OUTLINE)
    assert [unit["heading"] for unit in accepted] == [entry["heading"] for entry in OUTLINE]


# VERIFICATION --------------------------------------------------------------------------


def test_accept_units_anchors_each_unit_to_its_entry_of_the_outline():
    accepted = curation.accept_units(
        [{"name": "Introducción", "opens_at": 2}, {"name": "Bucles", "opens_at": 4}], OUTLINE
    )
    assert accepted == [
        {"name": "Introducción", "heading": "Tema I", "chunk": 2, "order": 0},
        {"name": "Bucles", "heading": "Tema II", "chunk": 5, "order": 1},
    ]


def test_accept_units_discards_a_position_outside_the_outline():
    accepted = curation.accept_units(
        [
            {"name": "A", "opens_at": 2},
            {"name": "Fuera por arriba", "opens_at": 99},
            {"name": "Fuera por abajo", "opens_at": 0},
            {"name": "Sin número", "opens_at": "cuatro"},
            {"name": "D", "opens_at": 4},
        ],
        OUTLINE,
    )
    assert [u["name"] for u in accepted] == ["A", "D"]


def test_a_repeated_position_keeps_the_first_the_model_wrote():
    accepted = curation.accept_units(
        [{"name": "Primera", "opens_at": 2}, {"name": "Segunda", "opens_at": 2},
         {"name": "Tercera", "opens_at": 4}],
        OUTLINE,
    )
    assert [u["name"] for u in accepted] == ["Primera", "Tercera"]


def test_units_come_back_in_the_order_of_the_corpus_whatever_order_they_were_written_in():
    accepted = curation.accept_units(
        [{"name": "Tarde", "opens_at": 5}, {"name": "Pronto", "opens_at": 2},
         {"name": "Medio", "opens_at": 4}],
        OUTLINE,
    )
    assert [u["name"] for u in accepted] == ["Pronto", "Medio", "Tarde"]
    assert [u["chunk"] for u in accepted] == [2, 5, 9]
    assert [u["order"] for u in accepted] == [1, 2, 0]


def test_the_catch_all_sentinel_is_refused_as_a_unit_name():
    accepted = curation.accept_units(
        [{"name": config.KG_BUILDER_UNCLASSIFIED_DOMAIN, "opens_at": 2},
         {"name": "A", "opens_at": 4}, {"name": "B", "opens_at": 5}],
        OUTLINE,
    )
    assert [u["name"] for u in accepted] == ["A", "B"]


def test_the_catch_all_sentinel_is_refused_whatever_its_case():
    accepted = curation.accept_units(
        [{"name": config.KG_BUILDER_UNCLASSIFIED_DOMAIN.lower(), "opens_at": 2},
         {"name": "A", "opens_at": 4}, {"name": "B", "opens_at": 5}],
        OUTLINE,
    )
    assert [u["name"] for u in accepted] == ["A", "B"]


def test_a_repeated_name_is_kept_once():
    accepted = curation.accept_units(
        [{"name": "Bucles", "opens_at": 2}, {"name": " bucles ", "opens_at": 4},
         {"name": "Otro", "opens_at": 5}],
        OUTLINE,
    )
    assert [u["name"] for u in accepted] == ["Bucles", "Otro"]


def test_fewer_than_two_units_is_a_failed_segmentation():
    assert curation.accept_units([{"name": "Todo", "opens_at": 2}], OUTLINE) == []
    assert curation.accept_units([], OUTLINE) == []
    assert curation.accept_units([{"name": "", "opens_at": 2}, 7, None], OUTLINE) == []


def test_two_units_opening_in_the_same_chunk_keep_only_the_first():
    outline = [
        {"document": 0, "heading": "Tema I", "chunk": 2},
        {"document": 0, "heading": "Subapartado", "chunk": 2},
        {"document": 0, "heading": "Tema II", "chunk": 7},
    ]
    accepted = curation.accept_units(
        [
            {"name": "Primera", "opens_at": 1},
            {"name": "Colisión", "opens_at": 2},
            {"name": "Segunda", "opens_at": 3},
        ],
        outline,
    )
    assert [u["name"] for u in accepted] == ["Primera", "Segunda"]


# THE CALL ------------------------------------------------------------------------------


def test_segment_syllabus_reads_what_the_model_writes(monkeypatch):
    answer(monkeypatch, units(("Introducción", 2), ("Bucles", 4)))
    result = curation.segment_syllabus(OUTLINE, [{"name": "apuntes.pdf"}], max_attempts=1, prompts=ES)
    assert [u["name"] for u in result] == ["Introducción", "Bucles"]


def test_segment_syllabus_returns_nothing_without_an_outline(monkeypatch):
    prompts = answer(monkeypatch, units(("A", 1), ("B", 2)))
    assert curation.segment_syllabus([], [], max_attempts=1, prompts=ES) == []
    assert prompts == []


def test_segment_syllabus_returns_nothing_when_the_answer_is_unreadable(monkeypatch):
    answer(monkeypatch, "lo siento, no puedo")
    assert curation.segment_syllabus(OUTLINE, [], max_attempts=0, prompts=ES) == []


# THE PROMPT ----------------------------------------------------------------------------


def test_the_prompt_asks_for_the_two_keys_and_for_the_order_the_units_are_taught_in():
    prompt = segment_syllabus_prompt("1. Tema I\n2. Tema II")
    assert '"opens_at"' in prompt
    assert '"units"' in prompt
    assert "1. Tema I" in prompt
    assert "ORDÉNALAS" in prompt
    assert "LA NUMERACIÓN MANDA" in prompt
    assert "ANTE LA DUDA, EL ORDEN DEL ÍNDICE" in prompt


def test_the_order_is_asked_for_between_finding_the_units_and_naming_them():
    prompt = segment_syllabus_prompt("1. Tema I\n2. Tema II")
    assert (
        prompt.index("# QUÉ ES UNA UNIDAD")
        < prompt.index("# ORDENA LAS UNIDADES COMO SE IMPARTEN")
        < prompt.index("# NOMBRES")
    )


# ASSIGNMENT ----------------------------------------------------------------------------

UNITS = [
    {"name": "Uno", "heading": "Tema I", "chunk": 2},
    {"name": "Dos", "heading": "Tema II", "chunk": 5},
    {"name": "Tres", "heading": "Tema III", "chunk": 9},
]


def test_unit_at_takes_the_last_unit_that_has_already_opened():
    assert curation.unit_at(UNITS, 1) is None
    assert curation.unit_at(UNITS, 2) == "Uno"
    assert curation.unit_at(UNITS, 4) == "Uno"
    assert curation.unit_at(UNITS, 5) == "Dos"
    assert curation.unit_at(UNITS, 40) == "Tres"


def test_the_mode_beats_the_first_appearance():
    assert curation.unit_of(UNITS, [2, 6, 7, 8]) == "Dos"


def test_a_tie_goes_to_the_earliest_unit():
    assert curation.unit_of(UNITS, [9, 2]) == "Uno"
    assert curation.unit_of(UNITS, [6, 10]) == "Dos"


def test_a_concept_seen_only_before_the_first_unit_is_not_assigned():
    assert curation.unit_of(UNITS, [1]) is None
    assert curation.unit_of(UNITS, []) is None


def test_assign_to_units_leaves_the_unplaceable_for_the_second_pass():
    by_unit, leftovers = curation.assign_to_units(
        UNITS,
        ["Pronto", "Tarde", "Portada", "Huérfano"],
        {"Pronto": [2, 3], "Tarde": [9, 9, 5], "Portada": [1]},
    )
    assert by_unit == {"Uno": ["Pronto"], "Dos": [], "Tres": ["Tarde"]}
    assert leftovers == ["Portada", "Huérfano"]


def test_the_units_keep_the_order_of_the_corpus_in_the_result():
    by_unit, _ = curation.assign_to_units(UNITS, [], {})
    assert list(by_unit) == ["Uno", "Dos", "Tres"]


# THE WHOLE PHASE -----------------------------------------------------------------------


# The positions are deliberately the REVERSE of the corpus order: a grouping ordered by
# where its members are first seen would come back ["Tres", "Dos", "Uno"].
def cleaned_corpus(**overrides) -> dict:
    base = {
        "entities": ["Variable", "Bucle", "Recursividad"],
        "relations": [],
        "documents": [{"name": "apuntes.pdf", "titles": []}],
        "origins": {},
        "definitions": {},
        "positions": {"Variable": 9, "Bucle": 5, "Recursividad": 2},
        "occurrences": {"Variable": [2], "Bucle": [5, 6], "Recursividad": [9]},
        "outline": OUTLINE,
    }
    base.update(overrides)
    return base


def test_curate_units_places_by_the_corpus_and_keeps_the_order_of_the_answer(monkeypatch):
    answer(monkeypatch, units(("Uno", 2), ("Dos", 4), ("Tres", 5)))
    cleaned = cleaned_corpus()
    by_domain, found = curation.curate_units(cleaned, max_attempts=1, prompts=ES)

    assert list(by_domain) == ["Uno", "Dos", "Tres"]
    assert by_domain["Uno"] == ["Variable"]
    assert by_domain["Dos"] == ["Bucle"]
    assert by_domain["Tres"] == ["Recursividad"]
    assert [u["name"] for u in found] == ["Uno", "Dos", "Tres"]


# «Copia de Tema 3» sorts before «Tema 1»: the corpus opens on the third unit, and the answer
# says which one is taught first. What a unit HOLDS still comes from where it opens.
def test_curate_units_writes_the_units_in_the_order_they_are_taught(monkeypatch):
    answer(monkeypatch, units(("Primero", 4), ("Segundo", 5), ("Tercero", 2)))
    by_domain, found = curation.curate_units(cleaned_corpus(), max_attempts=1, prompts=ES)

    assert list(by_domain) == ["Primero", "Segundo", "Tercero"]
    assert by_domain["Tercero"] == ["Variable"]
    assert by_domain["Primero"] == ["Bucle"]
    assert by_domain["Segundo"] == ["Recursividad"]
    assert [u["name"] for u in found] == ["Tercero", "Primero", "Segundo"]
    assert [u["order"] for u in found] == [2, 0, 1]


def test_the_unclassified_bucket_closes_the_units(monkeypatch):
    answer(monkeypatch, units(("Primero", 4), ("Tercero", 2)))
    monkeypatch.setattr(curation, "place_leftovers", lambda by_unit, *_, **__: by_unit)
    by_domain, _ = curation.curate_units(
        cleaned_corpus(occurrences={"Variable": [2], "Bucle": [5]}), max_attempts=1, prompts=ES
    )

    assert list(by_domain) == ["Primero", "Tercero", config.KG_BUILDER_UNCLASSIFIED_DOMAIN]


# POSITIONS -----------------------------------------------------------------------------

TAUGHT = [
    {"name": "Tercero", "heading": "Tema III", "chunk": 2, "order": 2},
    {"name": "Primero", "heading": "Tema I", "chunk": 5, "order": 0},
    {"name": "Segundo", "heading": "Tema II", "chunk": 9, "order": 1},
]


def test_positions_stay_as_they_are_when_the_corpus_is_in_the_order_it_is_taught():
    in_order = [{**unit, "order": index} for index, unit in enumerate(TAUGHT)]
    positions = {"A": 1, "B": 7, "C": 12}
    assert curation.taught_positions(positions, in_order) is positions
    assert curation.taught_positions(positions, []) is positions


def test_each_unit_moves_as_a_block_to_the_place_it_is_taught_in():
    positions = {"Portada": 1, "T1": 2, "T2": 4, "P1": 5, "P2": 8, "S1": 9, "S2": 12}
    moved = curation.taught_positions(positions, TAUGHT)

    assert sorted(moved, key=moved.get) == ["Portada", "P1", "P2", "S1", "S2", "T1", "T2"]
    assert sorted(moved.values()) == sorted(set(moved.values()))
    assert moved["P2"] - moved["P1"] == 3
    assert moved["T2"] - moved["T1"] == 2


def test_a_last_unit_no_concept_was_first_seen_in_moves_nothing_backwards():
    moved = curation.taught_positions({"T1": 2, "P1": 5}, TAUGHT)
    assert moved["P1"] < moved["T1"]


def test_curate_units_gives_up_without_an_outline(monkeypatch):
    prompts = answer(monkeypatch, units(("Uno", 2), ("Dos", 4)))
    assert curation.curate_units(cleaned_corpus(outline=[]), max_attempts=1, prompts=ES) == ({}, [])
    assert prompts == []


def test_curate_units_gives_up_when_the_segmentation_fails(monkeypatch):
    answer(monkeypatch, units(("Solo una", 2)))
    assert curation.curate_units(cleaned_corpus(), max_attempts=1, prompts=ES) == ({}, [])


def test_members_of_a_unit_follow_the_order_of_the_material(monkeypatch):
    answer(monkeypatch, units(("Uno", 2), ("Dos", 4)))
    # Alfa/Zeta reverse alphabetical order on purpose: a plain sorted() would fail here.
    by_domain, _ = curation.curate_units(
        cleaned_corpus(
            entities=["Alfa", "Zeta"],
            positions={"Alfa": 8, "Zeta": 3},
            occurrences={"Alfa": [6], "Zeta": [6]},
        ),
        max_attempts=1,
        prompts=ES,
    )
    assert by_domain["Dos"] == ["Zeta", "Alfa"]

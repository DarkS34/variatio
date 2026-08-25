import json
from types import SimpleNamespace

from variant_generator import config
from variant_generator.builders.knowledge_graph_builder import blocks, curation
from variant_generator.prompts import segment_syllabus_prompt

OUTLINE = [
    {"document": 0, "heading": "Índice", "chunk": 1},
    {"document": 0, "heading": "Tema I", "chunk": 2},
    {"document": 0, "heading": "Un ejemplo", "chunk": 3},
    {"document": 0, "heading": "Tema II", "chunk": 5},
    {"document": 0, "heading": "Tema III", "chunk": 9},
]


def answer(monkeypatch, response: str) -> list[str]:
    prompts: list[str] = []

    def fake_generate(*, model, prompt, think, format, temperature):
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


# VERIFICATION --------------------------------------------------------------------------


def test_accept_units_anchors_each_unit_to_its_entry_of_the_outline():
    accepted = curation.accept_units(
        [{"name": "Introducción", "opens_at": 2}, {"name": "Bucles", "opens_at": 4}], OUTLINE
    )
    assert accepted == [
        {"name": "Introducción", "heading": "Tema I", "chunk": 2},
        {"name": "Bucles", "heading": "Tema II", "chunk": 5},
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


def test_the_catch_all_sentinel_is_refused_as_a_unit_name():
    accepted = curation.accept_units(
        [{"name": config.KG_BUILDER_UNCLASSIFIED_DOMAIN, "opens_at": 2},
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


# THE CALL ------------------------------------------------------------------------------


def test_segment_syllabus_reads_what_the_model_writes(monkeypatch):
    answer(monkeypatch, units(("Introducción", 2), ("Bucles", 4)))
    result = curation.segment_syllabus(OUTLINE, [{"name": "apuntes.pdf"}], max_attempts=1)
    assert [u["name"] for u in result] == ["Introducción", "Bucles"]


def test_segment_syllabus_returns_nothing_without_an_outline(monkeypatch):
    prompts = answer(monkeypatch, units(("A", 1), ("B", 2)))
    assert curation.segment_syllabus([], [], max_attempts=1) == []
    assert prompts == []


def test_segment_syllabus_returns_nothing_when_the_answer_is_unreadable(monkeypatch):
    answer(monkeypatch, "lo siento, no puedo")
    assert curation.segment_syllabus(OUTLINE, [], max_attempts=0) == []


# THE PROMPT ----------------------------------------------------------------------------


def test_the_prompt_forbids_reordering_and_asks_for_the_two_keys():
    prompt = segment_syllabus_prompt("1. Tema I\n2. Tema II")
    assert '"opens_at"' in prompt
    assert '"units"' in prompt
    assert "1. Tema I" in prompt
    assert "reordenes" in prompt.lower() or "reordenar" in prompt.lower()

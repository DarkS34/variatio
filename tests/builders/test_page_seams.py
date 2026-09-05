from types import SimpleNamespace

import pytest

from variatio.builders._source_docs import chunking, markdown, pages
from variatio.core import inference
from variatio.prompts import SEAM_SEPARATORS

from ..conftest import ES

CODE_OPEN = "Escribe la función:\n\n```python\ndef f(n):\n    total = 0"
CODE_REST = "```python\n    for i in range(n):\n        total += i\n    return total\n```"

SENTENCE_OPEN = "El algoritmo recorre la lista y compara cada elemento con el"
SENTENCE_REST = "siguiente, intercambiándolos si están desordenados."

TABLE_OPEN = "| Entrada | Salida |\n| --- | --- |\n| 1 | 1 |"
TABLE_REST = "| 2 | 4 |\n| 3 | 9 |"


# THE DETERMINISTIC DETECTOR ----------------------------------------------------------------------


def test_an_open_code_fence_continues_and_is_certain():
    assert pages.seam(CODE_OPEN, CODE_REST) == (pages.NEWLINE, True)


def test_an_open_fence_does_not_reopen_on_the_next_page():
    joined = pages.join_pages([CODE_OPEN, CODE_REST])
    assert joined.count("```") == 2
    assert "def f(n):\n    total = 0\n    for i in range(n):" in joined


def test_a_cut_sentence_is_joined_with_a_space():
    separator, certain = pages.seam(SENTENCE_OPEN, SENTENCE_REST)
    assert separator == pages.SPACE
    assert not certain
    assert "con el siguiente," in pages.join_pages([SENTENCE_OPEN, SENTENCE_REST])


def test_a_table_that_continues_keeps_its_rows_adjacent():
    assert pages.seam(TABLE_OPEN, TABLE_REST)[0] == pages.NEWLINE
    assert "| 1 | 1 |\n| 2 | 4 |" in pages.join_pages([TABLE_OPEN, TABLE_REST])


def test_a_repeated_table_header_is_dropped():
    repeated = "| Entrada | Salida |\n| --- | --- |\n| 2 | 4 |"
    joined = pages.join_pages([TABLE_OPEN, repeated])
    assert joined.count("| Entrada | Salida |") == 1
    assert joined.count("| --- | --- |") == 1


def test_a_new_section_keeps_the_paragraph_break():
    left = "Con esto termina el tema."
    right = "## Tema 2\n\nEmpezamos otra cosa."
    assert pages.seam(left, right) == (pages.PARAGRAPH, False)
    assert "termina el tema.\n\n" in pages.join_pages([left, right])


def test_a_finished_sentence_is_not_a_continuation():
    assert pages.seam("Fin del apartado.", "otra cosa empieza")[0] == pages.PARAGRAPH


def test_an_empty_page_is_skipped_without_leaving_a_seam():
    assert pages.join_pages(["Uno.", "   ", "Dos."]) == "Uno.\n\n<!-- page 3 -->\n\nDos."


# THE PAGE MARK -----------------------------------------------------------------------------------


def test_a_clean_seam_records_which_page_starts_there():
    assert markdown.page_mark(4) in pages.join_pages(["Uno.", "Dos.", "Tres.", "Cuatro."])


def test_a_continuation_seam_carries_no_mark():
    assert markdown.page_mark(2) not in pages.join_pages([CODE_OPEN, CODE_REST])


def test_the_mark_never_reaches_a_block_or_a_section():
    joined = pages.join_pages(["# Tema 1\n\nUno.", "# Tema 2\n\nDos."])
    assert markdown.page_mark(2) in joined
    assert all("page" not in block for block in markdown.split_blocks(joined))
    assert all("page" not in body for _, _, body in chunking.split_sections(joined))
    assert all("page" not in chunk for chunk in chunking.chunk_text(joined, 1000))


def test_a_mark_inside_a_code_block_is_not_stripped():
    text = f"```\n{markdown.page_mark(2)}\n```"
    assert markdown.strip_page_marks(text) == text


# THE MODEL REVIEW --------------------------------------------------------------------------------


def answer(monkeypatch, response: str) -> list[str]:
    prompts: list[str] = []

    def fake_generate(*, model, prompt, think, format, temperature):
        prompts.append(prompt)
        return SimpleNamespace(response=response)

    monkeypatch.setattr(pages.inference, "generate", fake_generate)
    return prompts


def test_the_separator_catalogue_matches_the_prompt_exactly():
    assert set(pages.SEPARATORS) == set(SEAM_SEPARATORS)


def test_the_review_asks_once_per_uncertain_seam(monkeypatch):
    prompts = answer(monkeypatch, '{"continues": false, "separator": "paragraph", "drop_head_lines": 0}')
    records = pages.review_seams(["Uno.", "Dos.", "Tres."], ES, model="m")
    assert len(prompts) == 2
    assert [record["page"] for record in records] == [2, 3]


def test_the_review_never_asks_about_a_seam_the_rule_is_sure_of(monkeypatch):
    prompts = answer(monkeypatch, '{"continues": true, "separator": "newline", "drop_head_lines": 0}')
    assert pages.review_seams([CODE_OPEN, CODE_REST], ES, model="m") == []
    assert prompts == []


def test_the_model_can_override_the_rule(monkeypatch):
    answer(monkeypatch, '{"continues": true, "separator": "space", "drop_head_lines": 0}')
    left, right = "Escribe una función que", "Devuelve la suma."
    assert pages.seam(left, right)[0] == pages.PARAGRAPH
    seams = pages.review_seams([left, right], ES, model="m")
    assert pages.join_pages([left, right], seams) == "Escribe una función que Devuelve la suma."


def test_a_repeated_page_header_is_dropped_by_the_number_of_lines_the_model_says(monkeypatch):
    answer(monkeypatch, '{"continues": true, "separator": "space", "drop_head_lines": 1}')
    left, right = "El ejercicio pide que el alumno", "Prog1 · PEC1\nescriba una función."
    seams = pages.review_seams([left, right], ES, model="m")
    joined = pages.join_pages([left, right], seams)
    assert "Prog1" not in joined
    assert joined == "El ejercicio pide que el alumno escriba una función."


def test_the_model_may_not_drop_more_lines_than_the_cap(monkeypatch):
    answer(monkeypatch, '{"continues": true, "separator": "space", "drop_head_lines": 99}')
    seams = pages.review_seams(["El ejercicio pide que el alumno", "a\nb\nc\nd\ne"], ES, model="m")
    assert seams[0]["drop_head_lines"] == pages.MAX_SEAM_DROP_LINES


def test_an_invented_separator_is_discarded(monkeypatch):
    answer(monkeypatch, '{"continues": true, "separator": "pegado", "drop_head_lines": 0}')
    records = pages.review_seams(["Uno.", "Dos."], ES, model="m")
    assert records == [{"page": 2, "failed": True}]


def test_an_engine_failure_falls_back_to_the_rule(monkeypatch):
    def boom(**_kwargs):
        raise inference.InferenceError("el motor no responde")

    monkeypatch.setattr(pages.inference, "generate", boom)
    records = pages.review_seams([SENTENCE_OPEN, SENTENCE_REST], ES, model="m")
    assert records == [{"page": 2, "failed": True}]
    assert "con el siguiente," in pages.join_pages([SENTENCE_OPEN, SENTENCE_REST], records)


def test_unreadable_json_falls_back_to_the_rule(monkeypatch):
    answer(monkeypatch, "no soy json en absoluto")
    records = pages.review_seams(["Uno.", "Dos."], ES, model="m")
    assert records == [{"page": 2, "failed": True}]
    assert pages.join_pages(["Uno.", "Dos."], records) == "Uno.\n\n<!-- page 2 -->\n\nDos."


def test_the_prompt_shows_only_the_tail_and_the_head(monkeypatch):
    prompts = answer(monkeypatch, '{"continues": false, "separator": "paragraph", "drop_head_lines": 0}')
    left = "PRINCIPIO " + "x" * 5000 + " FIN DE LA IZQUIERDA"
    right = "PRINCIPIO DE LA DERECHA " + "y" * 5000 + " FINAL"
    pages.review_seams([left, right], ES, model="m")
    assert "FIN DE LA IZQUIERDA" in prompts[0]
    assert "PRINCIPIO DE LA DERECHA" in prompts[0]
    assert "FINAL" not in prompts[0].split("<<<FIN DE LA CABEZA>>>")[0].split("<<<CABEZA>>>")[1]


def test_a_cancellation_between_seams_is_honoured(monkeypatch):
    answer(monkeypatch, '{"continues": false, "separator": "paragraph", "drop_head_lines": 0}')

    class Stop:
        def emit(self, kind, payload):
            pass

        def should_cancel(self):
            return True

    with pages.progress.emitting(Stop()):
        with pytest.raises(pages.progress.Cancelled):
            pages.review_seams(["Uno.", "Dos."], ES, model="m")


def test_the_meta_records_how_many_seams_were_merged_and_which_failed():
    seams = [
        {"page": 2, "separator": "space", "drop_head_lines": 0},
        {"page": 3, "failed": True},
        {"page": 4, "separator": "paragraph", "drop_head_lines": 0},
    ]
    assert pages.seams_merged(seams) == 1
    assert pages.seams_failed(seams) == [3]


def test_the_seam_counters_are_written_beside_the_pages(tmp_path):
    seams = [{"page": 2, "separator": "newline", "drop_head_lines": 0}, {"page": 3, "failed": True}]
    pages.write_pages(tmp_path, ["Uno.", "Dos.", "Tres."], {"source": "x.pdf"}, seams)
    meta = pages.read_meta(tmp_path)
    assert meta["seams_merged"] == 1
    assert meta["seams_failed"] == [3]
    assert meta["failed_pages"] == []
    assert pages.fingerprint_of(meta) == {"source": "x.pdf"}

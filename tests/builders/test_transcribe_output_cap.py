"""An answer that never finishes is asked for once more, and what it read is kept under a marker.

Measured on the reference installation: a page whose header carries a fill-in line was
copied as 40 960 tokens of `\\_`; a page with a hand-drawn grid was cut at the 4 096-token
cap three times over with the same 7 368 characters, because the same request at
temperature 0 is the same loop. So a loop the engine stops on (`GenerationResponse.loop`)
or an answer that ran to `TRANSCRIBE_MAX_OUTPUT_TOKENS` (`truncated`) is asked for ONCE
MORE with the prompt naming what went wrong, and if that fails too the page keeps what
was read before the loop under `FAILED_PAGE_PREFIX`: counted in `failed_pages`, red in
"Apuntes y ejercicios", never handed downstream as a page with content.
"""

from variatio import config
from variatio.builders.source_docs import pages
from variatio.core.inference import GenerationResponse
from variatio.prompts import of as prompts_of
from variatio.wording import es as ES_WORDING

ROW = "| | | |       | | | |"
GRID = "# Sumador\n\n```\n1 0 0 0\n" + (ROW + "\n") * 40


class _Engine:
    """Answers each call with the next response of the list, repeating the last one."""

    def __init__(self, *responses: GenerationResponse):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> GenerationResponse:
        self.calls.append(kwargs)
        return self._responses[min(len(self.calls), len(self._responses)) - 1]


def _page(monkeypatch, *responses: GenerationResponse) -> tuple[str, _Engine]:
    engine = _Engine(*responses)
    monkeypatch.setattr(pages.inference, "generate", engine)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_RETRIES", 2)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_OUTPUT_TOKENS", 4096)
    page = pages._transcribe_page("AAAA", 3, 7, "m", "[t] ", prompts_of("es"))
    return page, engine


def _picture(monkeypatch, *responses: GenerationResponse) -> tuple[str | None, _Engine]:
    engine = _Engine(*responses)
    monkeypatch.setattr(pages.inference, "generate", engine)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_RETRIES", 2)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_OUTPUT_TOKENS", 4096)
    reading = pages._transcribe_image("AAAA", 1, 1, "m", "[t] ", prompts_of("es"))
    return reading, engine


def test_the_cap_and_the_loop_stop_travel_with_every_page_call(monkeypatch):
    page, engine = _page(monkeypatch, GenerationResponse("# Tema 1\n\nTexto."))
    assert page == "# Tema 1\n\nTexto."
    assert len(engine.calls) == 1
    assert engine.calls[0]["max_output_tokens"] == 4096
    assert engine.calls[0]["stop_on_loop"] is True


def test_a_looped_answer_is_asked_once_more_with_the_prompt_naming_the_loop(monkeypatch):
    page, engine = _page(
        monkeypatch,
        GenerationResponse(GRID, loop=ROW),
        GenerationResponse("# Sumador\n\n[cuadrícula vacía de 4 filas × 8 columnas]"),
    )
    assert page == "# Sumador\n\n[cuadrícula vacía de 4 filas × 8 columnas]"
    assert len(engine.calls) == 2
    assert ROW not in engine.calls[0]["prompt"]
    assert ROW in engine.calls[1]["prompt"], "the second attempt is told what repeated"
    assert "4096" in engine.calls[1]["prompt"]


def test_a_second_loop_keeps_what_came_before_it_under_the_marker(monkeypatch):
    page, engine = _page(
        monkeypatch, GenerationResponse(GRID, loop=ROW), GenerationResponse(GRID, loop=ROW)
    )
    assert len(engine.calls) == 2, "two attempts and never a third"
    assert page.startswith(ES_WORDING.FAILED_PAGE_PREFIX)
    assert "página 3 de 7" in page
    assert f"«{ROW}»" in page, "the marker names what the model kept writing"
    assert "# Sumador" in page and "1 0 0 0" in page, "what was read before the loop is kept"
    assert page.count(ROW) == 1, "the marker's quotation is the only copy of the row"
    assert page.count("```") == 2, "the fence the cut left open is closed"
    assert pages.failed_pages(["ok", page, "ok"]) == [2]


def test_nothing_before_the_loop_leaves_the_marker_alone(monkeypatch):
    looped = GenerationResponse("\\_" * 2048, loop="\\_")
    page, _ = _page(monkeypatch, looped, looped)
    assert page.startswith(ES_WORDING.FAILED_PAGE_PREFIX)
    assert page.endswith("]")
    assert "\\_\\_" not in page, "the garbage is not kept"
    assert "No se pudo salvar nada" in page


def test_an_answer_cut_at_the_cap_with_no_loop_found_keeps_its_text_and_names_the_cap(monkeypatch):
    cut = GenerationResponse("Un párrafo largo y legítimo.", truncated=True)
    page, engine = _page(monkeypatch, cut, cut)
    assert len(engine.calls) == 2
    assert "4096" in engine.calls[1]["prompt"]
    assert page.startswith(ES_WORDING.FAILED_PAGE_PREFIX)
    assert "4096" in page
    assert page.endswith("Un párrafo largo y legítimo.")


def test_the_attempt_that_read_further_is_the_one_kept(monkeypatch):
    short = GenerationResponse("# A\n" + (ROW + "\n") * 40, loop=ROW)
    longer = GenerationResponse("# A\n\nUn párrafo entero.\n\n" + (ROW + "\n") * 40, loop=ROW)
    page, _ = _page(monkeypatch, short, longer)
    assert "Un párrafo entero." in page


def test_a_looped_picture_is_asked_once_more_then_unreadable(monkeypatch):
    reading, engine = _picture(
        monkeypatch, GenerationResponse(GRID, loop=ROW), GenerationResponse(GRID, loop=ROW)
    )
    assert reading is None
    assert len(engine.calls) == 2
    assert ROW in engine.calls[1]["prompt"]
    assert engine.calls[0]["max_output_tokens"] == 4096
    assert engine.calls[0]["stop_on_loop"] is True


def test_a_picture_that_finishes_on_the_second_attempt_is_read(monkeypatch):
    reading, engine = _picture(
        monkeypatch,
        GenerationResponse(GRID, truncated=True),
        GenerationResponse("$$x^2$$"),
    )
    assert reading == "$$x^2$$"
    assert len(engine.calls) == 2

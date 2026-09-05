"""A transcription answer that hits the output cap is a failed page, not a short one.

Measured on 2026-09-05 in `compiladores`: nine pages of two exam papers came back with
exactly 40 960 tokens each — the engine's whole budget — of one repeated `\\_`, because the
header's fill-in line («Nombre: ____») was copied stroke for stroke and never stopped. Each
cost 0.063 $ and ~65 s instead of 0.003 $ and ~1 s, and the 738 832 characters of garbage
then went through the profile and the bank as if they were text: ~1.9 $ of that build's
5.48 $, and one exam that contributed 0 items.

`TRANSCRIBE_MAX_OUTPUT_TOKENS` bounds the call, and `truncated` — the engine's own stop
reason — turns the cut answer into `FAILED_PAGE_PREFIX`: visible in «Apuntes y ejercicios»,
counted in `failed_pages`, never handed downstream. Not retried, because at temperature 0
the same image produces the same run.
"""

from variatio import config
from variatio.builders._source_docs import pages
from variatio.core.inference import GenerationResponse
from variatio.prompts import of as prompts_of


class _Engine:
    """Answers every call with the same response and counts the calls."""

    def __init__(self, response: GenerationResponse):
        self._response = response
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> GenerationResponse:
        self.calls.append(kwargs)
        return self._response


def _page(monkeypatch, response: GenerationResponse) -> tuple[str, _Engine]:
    engine = _Engine(response)
    monkeypatch.setattr(pages.inference, "generate", engine)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_RETRIES", 2)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_OUTPUT_TOKENS", 4096)
    page = pages._transcribe_page("AAAA", 3, 7, "m", "[t] ", prompts_of("es"))
    return page, engine


def test_the_cap_travels_with_every_page_call(monkeypatch):
    page, engine = _page(monkeypatch, GenerationResponse("# Tema 1\n\nTexto."))
    assert page == "# Tema 1\n\nTexto."
    assert engine.calls[0]["max_output_tokens"] == 4096


def test_a_cut_answer_is_a_failed_page_and_names_the_page(monkeypatch):
    page, _ = _page(monkeypatch, GenerationResponse("\\_" * 2048, truncated=True))
    assert page.startswith(pages.FAILED_PAGE_PREFIX)
    assert "página 3 de 7" in page
    assert "4096" in page, "el marcador dice qué techo se superó"
    assert "\\_\\_" not in page, "la basura no se guarda"


def test_a_cut_answer_is_not_retried(monkeypatch):
    # Temperature 0: the same image would yield the same run, and `TRANSCRIBE_MAX_RETRIES`
    # is 2 here, so an answer treated as an error would have cost three calls.
    _, engine = _page(monkeypatch, GenerationResponse("\\_" * 2048, truncated=True))
    assert len(engine.calls) == 1


def test_the_failed_page_is_counted_as_failed(monkeypatch):
    page, _ = _page(monkeypatch, GenerationResponse("x" * 10, truncated=True))
    assert pages.failed_pages(["ok", page, "ok"]) == [2]


def test_a_cut_picture_is_unreadable_and_not_retried(monkeypatch):
    engine = _Engine(GenerationResponse("\\_" * 2048, truncated=True))
    monkeypatch.setattr(pages.inference, "generate", engine)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_RETRIES", 2)
    monkeypatch.setattr(config, "TRANSCRIBE_MAX_OUTPUT_TOKENS", 4096)
    reading = pages._transcribe_image("AAAA", 1, 1, "m", "[t] ", prompts_of("es"))
    assert reading is None
    assert len(engine.calls) == 1
    assert engine.calls[0]["max_output_tokens"] == 4096

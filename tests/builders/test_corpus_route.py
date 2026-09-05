import json

import pytest

from variatio.builders._source_docs import pages
from variatio.builders.knowledge_graph_builder import extraction
from variatio.core.inference import GenerationResponse
from variatio.core.workspace import Workspace

from ..conftest import ES

PAGE_ONE = "# Tema 1\n\nUna variable guarda un valor. El bucle recorre la"
PAGE_TWO = "lista entera.\n\n## Funciones\n\nUna función agrupa instrucciones."


class _Refuses:
    def convert(self, path: str):
        raise AssertionError("un PDF del corpus no puede pasar por Docling")


@pytest.fixture
def corpus(tmp_path):
    ws = Workspace(tmp_path, "pruebas")
    ws.raw_corpus_dir.mkdir(parents=True)
    (ws.raw_corpus_dir / "apuntes.pdf").write_bytes(b"%PDF-fake")
    return ws


def transcribes(monkeypatch, texts: list[str], seam: str = "space"):
    monkeypatch.setattr(
        pages,
        "page_images",
        lambda path, dpi, first=1: (len(texts), iter(range(first - 1, len(texts)))),
    )
    seen: list[str] = []

    def fake_generate(**kwargs):
        # The real shape, `truncated` included: a page call reads it.
        if kwargs.get("images") is not None:
            seen.append("página")
            return GenerationResponse(response=texts[len(seen) - 1])
        seen.append("costura")
        return GenerationResponse(
            response=json.dumps(
                {"continues": True, "separator": seam, "drop_head_lines": 0}
            )
        )

    monkeypatch.setattr(pages.inference, "generate", fake_generate)
    return seen


def convert(ws, monkeypatch, texts, seam="space"):
    seen = transcribes(monkeypatch, texts, seam)
    documents = extraction.convert_corpus(
        ws.raw_corpus_dir,
        recursive=False,
        converter=_Refuses(),
        chunk_size=12000,
        cache_dir=ws.markdown_cache_dir,
        prompts=ES,
    )
    return documents, seen


def test_a_corpus_pdf_is_transcribed_page_by_page_and_never_converted(corpus, monkeypatch):
    documents, seen = convert(corpus, monkeypatch, [PAGE_ONE, PAGE_TWO])
    assert seen.count("página") == 2
    assert documents


def test_the_corpus_lands_in_the_same_page_cache_as_the_exemplars(corpus, monkeypatch):
    convert(corpus, monkeypatch, [PAGE_ONE, PAGE_TWO])
    cached = corpus.markdown_cache_dir / "raw_corpus" / "apuntes.pdf"
    assert sorted(p.name for p in cached.iterdir()) == ["001.md", "002.md", "_meta.json"]


def test_a_sentence_cut_by_the_page_break_reaches_the_extractor_whole(corpus, monkeypatch):
    documents, _seen = convert(corpus, monkeypatch, [PAGE_ONE, PAGE_TWO])
    bodies = "\n".join(body for _path, _headings, body in documents[0][2])
    assert "recorre la lista entera." in bodies


def test_the_headings_of_both_pages_are_still_seen_as_sections(corpus, monkeypatch):
    documents, _seen = convert(corpus, monkeypatch, [PAGE_ONE, PAGE_TWO])
    paths = {path for path, _headings, _body in documents[0][2]}
    assert any("Tema 1" in path for path in paths)


def test_no_page_mark_survives_into_a_chunk(corpus, monkeypatch):
    documents, _seen = convert(corpus, monkeypatch, ["Uno.", "Dos."], seam="paragraph")
    assert all("pág." not in body for _p, _h, body in documents[0][2])


def test_a_second_build_reuses_the_pages_and_calls_no_model(corpus, monkeypatch):
    convert(corpus, monkeypatch, [PAGE_ONE, PAGE_TWO])

    def boom(**_kwargs):
        raise AssertionError("una caché válida no puede volver a llamar al modelo")

    monkeypatch.setattr(pages.inference, "generate", boom)
    monkeypatch.setattr(pages, "page_images", boom)
    documents = extraction.convert_corpus(
        corpus.raw_corpus_dir,
        recursive=False,
        converter=_Refuses(),
        chunk_size=12000,
        cache_dir=corpus.markdown_cache_dir,
        prompts=ES,
    )
    assert documents


def test_the_seam_decision_is_cached_and_not_re_asked(corpus, monkeypatch):
    _documents, seen = convert(corpus, monkeypatch, [PAGE_ONE, PAGE_TWO])
    assert seen.count("costura") == 1
    meta = pages.read_meta(corpus.markdown_cache_dir / "raw_corpus" / "apuntes.pdf")
    assert meta["seams"] == [{"page": 2, "separator": "space", "drop_head_lines": 0}]

"""The notes are cut from the page cache, placed in their units, and searched by cosine."""

import json

import numpy as np
import pytest
from PIL import Image

from tutor import originals, passages, paths
from variatio.builders.source_docs.files import source_hash
from variatio.core.workspace import Workspace

from .conftest import SOURCES, vector_for

PAGES = [
    "# Índice\n\nTema 1 Fundamentos .......... 1\nTema 2 Avanzado .......... 5\nOtro ..... 7",
    "# Tema 1 Fundamentos\n\n## Variables\n\nUna variable guarda un valor y tiene un nombre.",
    "# Tema 2 Avanzado\n\n## Recursividad\n\nUna función recursiva se llama a sí misma.",
]


def cached_workspace(tmp_path) -> Workspace:
    ws = Workspace(tmp_path / "ws", slug="ws")
    directory = paths.corpus_pages_dir(ws) / "apuntes.pdf"
    directory.mkdir(parents=True)
    for index, page in enumerate(PAGES, 1):
        (directory / f"{index:03d}.md").write_text(page, encoding="utf-8")
    (directory / "_meta.json").write_text(json.dumps({"pages": len(PAGES), "seams": []}), encoding="utf-8")
    return ws


def test_the_corpus_is_cut_by_its_headings_into_units_without_its_table_of_contents(tmp_path):
    cut = passages.cut_corpus(cached_workspace(tmp_path), SOURCES, 200)

    assert [(p.unit, p.location) for p in cut] == [
        ("Fundamentos", "Tema 1 Fundamentos > Variables"),
        ("Avanzado", "Tema 2 Avanzado > Recursividad"),
    ]
    assert all("....." not in p.text for p in cut)


def test_a_document_without_finished_pages_is_skipped(tmp_path):
    ws = Workspace(tmp_path / "ws", slug="ws")

    assert passages.cut_corpus(ws, SOURCES, 200) == []


def test_the_index_finds_above_its_threshold_and_skips_what_the_card_already_quotes():
    found = [
        passages.Passage("P1", "a.pdf", "Tema 2", "Avanzado", "La recursividad necesita un caso base."),
        passages.Passage("P2", "a.pdf", "Tema 1", "Fundamentos", "Una variable guarda un valor."),
    ]
    index = passages.PassageIndex(found, np.stack([vector_for(p.text) for p in found]), "fp")
    query = vector_for("¿qué es la recursividad?")

    assert [p.id for p, _ in index.search(query, 3, 0.5)] == ["P1"]
    assert index.search(query, 3, 0.5, exclude={passages.text_key(found[0].text)}) == []
    assert index.of_unit("Fundamentos") == [found[1]]


def test_the_index_is_cached_by_fingerprint_and_rebuilt_when_the_notes_change(tmp_path, monkeypatch):
    ws = cached_workspace(tmp_path)
    calls = []

    def embed(texts, what, model=None):
        calls.append(len(texts))
        return np.stack([vector_for(t) for t in texts])

    monkeypatch.setattr(passages, "embed_normalized", embed)
    passages.forget(ws.slug)

    first = passages.index_for(ws, SOURCES, 200)
    passages.forget(ws.slug)
    second = passages.index_for(ws, SOURCES, 200)
    assert calls == [2] and len(second) == 2 and second.fingerprint == first.fingerprint

    page = paths.corpus_pages_dir(ws) / "apuntes.pdf" / "003.md"
    page.write_text(page.read_text(encoding="utf-8") + "\n\nUn párrafo corregido a mano.", encoding="utf-8")
    passages.index_for(ws, SOURCES, 200)
    assert calls == [2, 2]


def test_the_reader_serves_a_document_of_the_notes_by_whole_sections_and_nothing_else(tmp_path):
    ws = cached_workspace(tmp_path)

    found = passages.read_document(ws, SOURCES, "apuntes.pdf")

    assert [s["location"] for s in found["sections"]] == [
        "Tema 1 Fundamentos > Variables",
        "Tema 2 Avanzado > Recursividad",
    ]
    assert found["sections"][1]["text"].startswith("## Recursividad")
    assert found["original"] is None and found["sections"][0]["page"] is None
    assert passages.read_document(ws, SOURCES, "../../etc/passwd") is None


# THE ORIGINAL DOCUMENT ---------------------------------------------------------------------------


def blank_pdf(path, pages: int) -> None:
    """Write a PDF of `pages` empty pages: enough to count and to draw."""
    sheets = [Image.new("RGB", (120, 170), "white") for _ in range(pages)]
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets[0].save(path, format="PDF", save_all=True, append_images=sheets[1:])


def with_original(ws: Workspace, pages: int = len(PAGES), **meta) -> None:
    """Put the document itself in the raw corpus and say the cache was read from it."""
    source = ws.raw_corpus_dir / "apuntes.pdf"
    blank_pdf(source, pages)
    record = {"pages": len(PAGES), "seams": [], "source_sha256": source_hash(source), **meta}
    (paths.corpus_pages_dir(ws) / "apuntes.pdf" / "_meta.json").write_text(
        json.dumps(record), encoding="utf-8"
    )


def test_a_section_opens_on_the_page_of_the_original_its_heading_is_on(tmp_path):
    ws = cached_workspace(tmp_path)
    with_original(ws)

    found = passages.read_document(ws, SOURCES, "apuntes.pdf")

    assert found["original"]["pages"] == 3 and len(found["original"]["version"]) == 16
    assert found["original"]["ratios"] == [round(170 / 120, 4)] * 3
    assert [s["page"] for s in found["sections"]] == [2, 3]


def test_a_page_of_the_original_is_drawn_once_and_only_inside_the_document(tmp_path, monkeypatch):
    ws = cached_workspace(tmp_path)
    with_original(ws)
    original = originals.original_for(ws, "apuntes.pdf")

    data, media = originals.page_image(ws, original, 2)

    assert media == "image/png" and data.startswith(b"\x89PNG")
    monkeypatch.setattr(originals.source_docs, "page_picture", lambda *a: pytest.fail("drawn twice"))
    assert originals.page_image(ws, original, 2) == (data, media)
    assert originals.page_image(ws, original, 0) is None
    assert originals.page_image(ws, original, 4) is None


def test_pages_moved_by_hand_are_found_by_their_titles_in_the_original_s_text(tmp_path, monkeypatch):
    ws = cached_workspace(tmp_path)
    with_original(ws, pages=5, restructured=True)
    monkeypatch.setattr(
        originals.source_docs,
        "page_texts",
        lambda pdf: [
            "Portada",
            "Índice\r\nVariables 3\r\nRecursividad 5",
            "1.1 Variables\r\nUna variable guarda un valor.",
            "La recursividad se ve más adelante.",
            "2.1. Recursividad\r\nUna función recursiva se llama a sí misma.",
        ],
    )

    found = passages.read_document(ws, SOURCES, "apuntes.pdf")

    assert [s["page"] for s in found["sections"]] == [3, 5]


def test_a_page_listing_the_titles_found_again_later_is_a_table_of_contents():
    titles = [f"Apartado {letter}" for letter in "abcdefg"]
    sections = [(title, title, f"## {title}") for title in titles] + [("Otro", "Otro", "## Otro")]
    texts = ["\n".join(titles)] + [f"{title}\nTexto." for title in titles]
    original = originals.Original(pdf=None, ratios=(1.4,) * len(texts), digest="0" * 64)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(originals.source_docs, "page_texts", lambda pdf: texts)
        found = originals.section_pages(original, {}, [], [], sections)

    assert found == [2, 3, 4, 5, 6, 7, 8, 8], "a title on no page stays with the one before"


def test_an_office_document_is_exported_once_and_a_refusal_is_not_asked_again(tmp_path, monkeypatch):
    ws = cached_workspace(tmp_path)
    ws.raw_corpus_dir.mkdir(parents=True)
    (ws.raw_corpus_dir / "tema.docx").write_bytes(b"un documento")
    (ws.raw_corpus_dir / "roto.docx").write_bytes(b"otro documento")
    (ws.raw_corpus_dir / "notas.md").write_text("# Notas", encoding="utf-8")
    asked = []

    def export(source, workdir, timeout):
        asked.append(source.name)
        if source.name == "roto.docx":
            return None
        blank_pdf(workdir / "tema.pdf", 2)
        return workdir / "tema.pdf"

    monkeypatch.setattr(originals.source_docs.office, "pdf_copy", export)
    monkeypatch.setattr(originals, "_unexportable", set())

    first, again = originals.original_for(ws, "tema.docx"), originals.original_for(ws, "tema.docx")

    assert first == again and first.pages == 2 and first.pdf.parent == paths.originals_dir(ws)
    assert originals.original_for(ws, "roto.docx") is None
    assert originals.original_for(ws, "roto.docx") is None
    assert asked == ["tema.docx", "roto.docx"]
    assert [entry.name for entry in paths.originals_dir(ws).iterdir()] == [first.pdf.name]
    assert originals.original_for(ws, "notas.md") is None
    assert originals.original_for(ws, "ausente.pdf") is None
    assert originals.original_for(ws, "../raw_corpus/tema.docx") is None

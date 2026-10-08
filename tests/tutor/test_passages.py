"""The notes are cut from the page cache, placed in their units, and searched by cosine."""

import json

import numpy as np

from tutor import passages, paths
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

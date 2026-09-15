"""A page the model could not read is read again the next time, and only that page.

Until 2026-09-15 a failed page was cached like any other, so a document read under a refusal
kept its markers for ever: re-uploading the same file found the same bytes in the cache and
asked nothing. The next read now tries the failed pages again — every other page, hand
corrections included, stays exactly as it is — unless pages were inserted or deleted by hand,
which makes the cache's page N stop being the file's page N.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from variatio import wording
from variatio.builders.source_docs import pages
from variatio.core.workspace import Workspace
from variatio.entrypoints import transcribe

from ..conftest import ES

PAGES = ["uno", "dos", "tres", "cuatro"]
TIDIED = [page + "\n" for page in PAGES]


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    workspace = Workspace(tmp_path, "aula")
    workspace.raw_corpus_dir.mkdir(parents=True)
    return workspace


@pytest.fixture
def source(ws: Workspace) -> Path:
    path = ws.raw_corpus_dir / "examen.pdf"
    path.write_bytes(b"%PDF-escaneado")
    return path


def _images(monkeypatch, count: int = len(PAGES)) -> None:
    def page_images(path, dpi, first=1, numbers=None):
        wanted = list(numbers) if numbers is not None else list(range(first, count + 1))
        return count, iter(wanted)

    monkeypatch.setattr(pages, "page_images", page_images)
    monkeypatch.setattr(pages, "page_count", lambda path: count)


def _model(monkeypatch, failing=()) -> tuple[list[int], list[dict]]:
    """Record the pages asked for and the seam calls; `failing` pages come back as markers."""
    asked: list[int] = []
    seams: list[dict] = []

    def transcribe_page(image, index, count, model, tag, prompts):
        asked.append(index)
        if index in failing:
            return wording.beside(prompts).failed_page(index, count, "413 payload too large")
        return PAGES[index - 1]

    def generate(**kwargs):
        seams.append(kwargs)
        return SimpleNamespace(
            response=json.dumps(
                {"continues": False, "separator": "paragraph", "drop_head_lines": 0}
            )
        )

    monkeypatch.setattr(pages, "_transcribe_page", transcribe_page)
    monkeypatch.setattr(pages.inference, "generate", generate)
    return asked, seams


def _read(source: Path, ws: Workspace) -> list[str]:
    return pages.document_pages(source, ES, cache_dir=ws.markdown_cache_dir)


def _cache(source: Path, ws: Workspace) -> Path:
    return pages.document_cache_dir(source, ws.markdown_cache_dir)


def _first_read(source, ws, monkeypatch, failing=(2, 4)) -> None:
    _images(monkeypatch)
    _model(monkeypatch, failing=failing)
    _read(source, ws)


def test_the_next_read_asks_only_for_the_pages_that_failed(source, ws, monkeypatch):
    _first_read(source, ws, monkeypatch)
    assert pages.read_meta(_cache(source, ws))["failed_pages"] == [2, 4]

    _images(monkeypatch)
    asked, _ = _model(monkeypatch)
    result = _read(source, ws)

    assert asked == [2, 4]
    assert result == TIDIED
    assert pages.read_meta(_cache(source, ws))["failed_pages"] == []


def test_a_page_that_fails_again_keeps_its_marker_and_the_rest_is_kept(source, ws, monkeypatch):
    _first_read(source, ws, monkeypatch)

    _images(monkeypatch)
    asked, _ = _model(monkeypatch, failing=(4,))
    result = _read(source, ws)

    assert asked == [2, 4]
    assert result[:3] == TIDIED[:3]
    assert pages.read_meta(_cache(source, ws))["failed_pages"] == [4]


def test_a_document_with_nothing_failed_still_costs_no_call(source, ws, monkeypatch):
    _first_read(source, ws, monkeypatch, failing=())

    _images(monkeypatch)
    asked, seams = _model(monkeypatch)
    _read(source, ws)

    assert asked == []
    assert seams == []


def test_only_the_seams_around_the_page_read_again_are_asked_again(source, ws, monkeypatch):
    _first_read(source, ws, monkeypatch, failing=(2,))

    _images(monkeypatch)
    _, seams = _model(monkeypatch)
    _read(source, ws)

    # Page 2 is between the seams named 2 (1→2) and 3 (2→3); the seam 3→4 keeps its answer.
    assert len(seams) == 2
    records = pages.read_meta(_cache(source, ws))["seams"]
    assert sorted(record["page"] for record in records) == [2, 3, 4]


def test_a_failed_page_corrected_by_hand_is_not_read_again(source, ws, monkeypatch):
    _first_read(source, ws, monkeypatch)
    transcribe.write_document_page(ws, "corpus", "examen.pdf", 2, "dos, corregida a mano")

    _images(monkeypatch)
    asked, _ = _model(monkeypatch)
    result = _read(source, ws)

    assert asked == [4]
    assert result[1] == "dos, corregida a mano"


def test_pages_moved_by_hand_stop_the_retry_for_good(source, ws, monkeypatch):
    _first_read(source, ws, monkeypatch)
    transcribe.insert_document_page(ws, "corpus", "examen.pdf", 0, "portada")
    transcribe.delete_document_page(ws, "corpus", "examen.pdf", 1)
    assert pages.read_meta(_cache(source, ws))["restructured"] is True

    _images(monkeypatch)
    asked, _ = _model(monkeypatch)
    _read(source, ws)

    assert asked == []


def test_a_cache_whose_page_count_is_not_the_files_is_not_read_again(source, ws, monkeypatch):
    _first_read(source, ws, monkeypatch)

    _images(monkeypatch, count=5)
    asked, _ = _model(monkeypatch)
    _read(source, ws)

    assert asked == []


def test_the_slot_offers_to_read_a_document_with_failed_pages_again(source, ws, monkeypatch):
    _first_read(source, ws, monkeypatch)

    status = transcribe.transcription_status(ws, "corpus")
    document = status["documents"][0]

    assert document["state"] == "done"
    assert document["failed_pages"] == 2
    assert document["retry_pages"] == 2
    assert status["retry"] == 1


def test_a_hand_edit_keeps_the_picture_tallies_of_the_document(tmp_path):
    cache = tmp_path / "doc"
    fingerprint = {"source": "x.docx", "mode": "docling"}
    pages.write_pages(cache, ["hola"], fingerprint, [], {"images_total": 3, "images_unreadable": 1})
    transcribe._save_document(cache, pages.read_meta(cache), ["hola, corregida"], dropped=set())

    meta = pages.read_meta(cache)
    assert (meta["images_total"], meta["images_unreadable"], meta["restructured"]) == (3, 1, False)

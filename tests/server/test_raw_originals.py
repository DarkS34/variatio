"""A raw document opens beside its original: drawn once, and page to page where the pages pair."""

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from server import auth, originals, raw_data
from server.auth.deps import Access
from server.routers.raw import router as raw_router
from variatio.builders import source_docs
from variatio.builders.source_docs.files import source_hash
from variatio.core.workspace import Workspace


def blank_pdf(path, pages: int) -> None:
    """Write a PDF of `pages` empty pages: enough to count and to draw."""
    sheets = [Image.new("RGB", (120, 170), "white") for _ in range(pages)]
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets[0].save(path, format="PDF", save_all=True, append_images=sheets[1:])


def transcribed(ws: Workspace, name: str, pages: int, **meta) -> None:
    """Put `pages` pages in the page cache of a corpus document, read from that very file."""
    source = ws.raw_corpus_dir / name
    cache = source_docs.document_cache_dir(source, ws.markdown_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    for index in range(1, pages + 1):
        (cache / f"{index:03d}.md").write_text(f"# Página {index}", encoding="utf-8")
    record = {"pages": pages, "seams": [], "source_sha256": source_hash(source), **meta}
    (cache / "_meta.json").write_text(json.dumps(record), encoding="utf-8")


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path / "aula", slug="aula")
    workspace.raw_corpus_dir.mkdir(parents=True)
    workspace.raw_exemplars_dir.mkdir(parents=True)
    blank_pdf(workspace.raw_corpus_dir / "apuntes.pdf", 3)
    return workspace


@pytest.fixture
def client(ws):
    access = Access(
        user=SimpleNamespace(id=1, name="Ana"),
        workspace=SimpleNamespace(slug="aula", name="Aula"),
        role="owner",
        ws=ws,
    )
    app = FastAPI()
    app.include_router(raw_router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    return TestClient(app)


# PAIRED PAGE TO PAGE -----------------------------------------------------------------------


def test_a_pdf_read_as_it_is_goes_page_to_page_with_its_transcription(ws):
    transcribed(ws, "apuntes.pdf", 3)

    body = raw_data.transcription_document(ws, "corpus", "apuntes.pdf")

    assert [page["index"] for page in body["pages"]] == [1, 2, 3]
    original = body["original"]
    assert original["pages"] == 3 and len(original["version"]) == 16
    assert original["ratios"] == [round(170 / 120, 4)] * 3
    assert original["paired"] is True and original["unpaired"] is None


def test_pages_moved_by_hand_other_bytes_or_another_count_unpair_the_two_views_and_say_why(ws):
    def why(name):
        found = raw_data.transcription_document(ws, "corpus", name)["original"]
        return found["paired"], found["unpaired"]

    transcribed(ws, "apuntes.pdf", 3, restructured=True)
    assert why("apuntes.pdf") == (False, "moved")

    transcribed(ws, "apuntes.pdf", 3, source_sha256="0" * 64)
    assert why("apuntes.pdf") == (False, "source")

    blank_pdf(ws.raw_corpus_dir / "tema.pdf", 4)
    transcribed(ws, "tema.pdf", 1)
    assert why("tema.pdf") == (False, "count")


def test_a_document_with_no_original_to_draw_answers_its_pages_alone(ws):
    (ws.raw_corpus_dir / "notas.md").write_text("# Notas", encoding="utf-8")
    (ws.raw_corpus_dir / "roto.pdf").write_bytes(b"%PDF-1.4 ")

    assert raw_data.transcription_document(ws, "corpus", "notas.md")["original"] is None
    assert raw_data.transcription_document(ws, "corpus", "roto.pdf")["original"] is None


# THE ORIGINAL, DRAWN ---------------------------------------------------------------------


def test_a_page_of_the_original_is_drawn_once_and_only_inside_the_document(ws, monkeypatch):
    original = originals.original_for(ws, ws.raw_corpus_dir / "apuntes.pdf")

    data, media = originals.page_image(ws, original, 2)

    assert media == "image/png" and data.startswith(b"\x89PNG")
    monkeypatch.setattr(originals.source_docs, "page_picture", lambda *a: pytest.fail("drawn twice"))
    assert originals.page_image(ws, original, 2) == (data, media)
    assert originals.page_image(ws, original, 0) is None
    assert originals.page_image(ws, original, 4) is None


def test_an_office_document_is_exported_once_and_a_refusal_is_not_asked_again(ws, monkeypatch):
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
    corpus = ws.raw_corpus_dir

    first, again = originals.original_for(ws, corpus / "tema.docx"), originals.original_for(ws, corpus / "tema.docx")

    assert first == again and first.pages == 2 and first.pdf.parent == originals.originals_dir(ws)
    assert originals.original_for(ws, corpus / "roto.docx") is None
    assert originals.original_for(ws, corpus / "roto.docx") is None
    assert asked == ["tema.docx", "roto.docx"]
    assert [entry.name for entry in originals.originals_dir(ws).iterdir()] == [first.pdf.name]
    assert originals.original_for(ws, corpus / "notas.md") is None
    assert originals.original_for(ws, corpus / "ausente.pdf") is None


def test_the_tutor_reader_s_old_cache_is_taken_over_where_none_exists_and_dropped_otherwise(tmp_path):
    first = Workspace(tmp_path / "uno", slug="uno")
    blank_pdf(first.raw_corpus_dir / "apuntes.pdf", 1)
    legacy = first.cache_dir / "tutor_originals"
    legacy.mkdir(parents=True)
    (legacy / "abc.pdf").write_bytes(b"exportado")

    originals.original_for(first, first.raw_corpus_dir / "apuntes.pdf")

    assert not legacy.exists()
    assert (originals.originals_dir(first) / "abc.pdf").read_bytes() == b"exportado"

    second = Workspace(tmp_path / "dos", slug="dos")
    blank_pdf(second.raw_corpus_dir / "apuntes.pdf", 1)
    (second.cache_dir / "tutor_originals").mkdir(parents=True)
    originals.originals_dir(second).mkdir(parents=True)

    originals.original_for(second, second.raw_corpus_dir / "apuntes.pdf")

    assert not (second.cache_dir / "tutor_originals").exists()


# THE ROUTE -------------------------------------------------------------------------------


def test_the_reader_asks_one_page_at_a_time_and_only_of_a_document_the_slot_holds(client, ws):
    transcribed(ws, "apuntes.pdf", 3)

    listing = client.get("/api/raw/corpus/transcription/apuntes.pdf").json()
    version = listing["original"]["version"]
    page = client.get(f"/api/raw/corpus/transcription/apuntes.pdf/original/2?v={version}")

    assert listing["original"]["paired"] is True
    assert page.status_code == 200 and page.headers["content-type"] == "image/png"
    assert "immutable" in page.headers["cache-control"]
    assert client.get("/api/raw/corpus/transcription/apuntes.pdf/original/9").status_code == 404
    assert client.get("/api/raw/corpus/transcription/otro.pdf/original/1").status_code == 404
    assert client.get("/api/raw/exemplars/transcription/apuntes.pdf/original/1").status_code == 404
    escaped = client.get("/api/raw/corpus/transcription/..%2F..%2Fconfig.json/original/1")
    assert escaped.status_code == 404

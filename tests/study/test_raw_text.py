"""The study's plain reading of a slot: prepared by bytes, cut into keyed pieces, reconciled."""

import json
from pathlib import Path

import pytest

from study import raw_text
from variatio.core.workspace import Workspace


def _pdf(lines: list[str]) -> bytes:
    """Write the smallest PDF with a text layer: one page, Helvetica, one line per `Tj`."""
    content = "BT /F1 12 Tf 72 720 Td " + " ".join(f"({line}) Tj 0 -16 Td" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n{body}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    return Workspace(root=tmp_path / "aula", slug="aula")


def test_a_pdf_is_read_with_the_plain_extractor(ws: Workspace):
    ws.raw_corpus_dir.mkdir(parents=True)
    (ws.raw_corpus_dir / "apuntes.pdf").write_bytes(_pdf(["Una lista es una secuencia.", "Se recorre con un bucle."]))

    report = raw_text.prepare_slot(ws, "corpus")

    assert report == {"read": 1, "dropped": 0, "failed": [], "documents": 1}
    text = raw_text.texts(ws, "corpus")["apuntes.pdf"]
    assert "Una lista es una secuencia." in text
    assert "Se recorre con un bucle." in text


def test_preparing_again_reads_nothing_and_a_removed_file_is_dropped(ws: Workspace):
    ws.raw_exemplars_dir.mkdir(parents=True)
    (ws.raw_exemplars_dir / "hoja1.md").write_text("Suma dos números.", encoding="utf-8")
    (ws.raw_exemplars_dir / "hoja2.txt").write_text("Resta dos números.", encoding="utf-8")
    assert raw_text.prepare_slot(ws, "exemplars")["read"] == 2

    assert raw_text.prepare_slot(ws, "exemplars") == {
        "read": 0, "dropped": 0, "failed": [], "documents": 2,
    }

    (ws.raw_exemplars_dir / "hoja2.txt").unlink()
    report = raw_text.prepare_slot(ws, "exemplars")
    assert report["dropped"] == 1 and report["documents"] == 1
    assert list(raw_text.texts(ws, "exemplars")) == ["hoja1.md"]
    assert not (raw_text.text_dir(ws, "exemplars") / "hoja2.txt.txt").exists()


def test_a_changed_file_is_read_again_under_the_same_name(ws: Workspace):
    ws.raw_exemplars_dir.mkdir(parents=True)
    source = ws.raw_exemplars_dir / "hoja1.md"
    source.write_text("Versión uno.", encoding="utf-8")
    raw_text.prepare_slot(ws, "exemplars")
    source.write_text("Versión dos.", encoding="utf-8")

    assert raw_text.prepare_slot(ws, "exemplars")["read"] == 1
    assert raw_text.texts(ws, "exemplars")["hoja1.md"] == "Versión dos."


def test_an_unreadable_file_is_left_out_and_stops_nothing(ws: Workspace):
    ws.raw_corpus_dir.mkdir(parents=True)
    (ws.raw_corpus_dir / "roto.pdf").write_bytes(b"not a pdf at all")
    (ws.raw_corpus_dir / "bien.txt").write_text("Texto legible.", encoding="utf-8")

    report = raw_text.prepare_slot(ws, "corpus")

    assert report["failed"] == ["roto.pdf"]
    assert list(raw_text.texts(ws, "corpus")) == ["bien.txt"]


def test_pieces_are_keyed_by_document_and_position(ws: Workspace):
    ws.raw_corpus_dir.mkdir(parents=True)
    body = "\n\n".join(f"Párrafo {n} " + "x" * 60 for n in range(1, 7))
    (ws.raw_corpus_dir / "tema1.txt").write_text(body, encoding="utf-8")
    raw_text.prepare_slot(ws, "corpus")

    pieces = raw_text.chunks(ws, "corpus", max_chars=150)

    assert list(pieces)[:2] == ["tema1.txt#1", "tema1.txt#2"]
    assert len(pieces) > 1
    assert "".join(pieces.values()).count("Párrafo") == 6


def test_the_meta_is_plain_json_beside_the_readings(ws: Workspace):
    ws.raw_corpus_dir.mkdir(parents=True)
    (ws.raw_corpus_dir / "a.txt").write_text("hola", encoding="utf-8")
    raw_text.prepare_slot(ws, "corpus")
    meta = json.loads((raw_text.text_dir(ws, "corpus") / "_meta.json").read_text(encoding="utf-8"))
    assert set(meta["a.txt"]) == {"sha256", "file", "chars", "version"}

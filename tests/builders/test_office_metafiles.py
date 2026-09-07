"""The metafiles of an Office document, rendered before Docling ever sees the file.

EMF and WMF are what Word writes for an Equation Editor equation, a piece of clip art and
most logos, and Pillow opens neither: Docling hands them over as pictures with no image and
its own LibreOffice fallback never reaches an `a:blip`. So a copy of the file is written
with every metafile replaced by a PNG LibreOffice rendered. What is pinned here is the
rewrite of the package — entries, relationships, content types — with the renderer stubbed,
and the real render once, on the reference workbook's own 588-byte equation, when
LibreOffice is on the PATH.
"""

import io
import re
import shutil
import zipfile
from pathlib import Path

import pytest

from variatio.builders.source_docs import office, pages

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

_DOCUMENT_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?><Relationships>'
    '<Relationship Id="rId1" Type="…/image" Target="media/image1.emf"/>'
    '<Relationship Id="rId2" Type="…/image" Target="media/image10.emf"/>'
    '<Relationship Id="rId3" Type="…/image" Target="media/photo.png"/>'
    "</Relationships>"
)
_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?><Types>'
    '<Default Extension="emf" ContentType="image/x-emf"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    "</Types>"
)


def _docx(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _workbook(tmp_path: Path) -> Path:
    return _docx(
        tmp_path / "cuaderno.docx",
        {
            "[Content_Types].xml": _TYPES.encode(),
            "word/document.xml": b"<w:document/>",
            "word/_rels/document.xml.rels": _DOCUMENT_RELS.encode(),
            "word/media/image1.emf": b"EMF one",
            "word/media/image10.emf": b"EMF ten",
            "word/media/photo.png": b"\x89PNG photo",
        },
    )


def _png(width: int = 8, height: int = 8, colour="black") -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def stub_renderer(monkeypatch):
    """Stand in for LibreOffice: every metafile becomes a small black PNG."""
    monkeypatch.setattr(office, "rasteriser", lambda: "/usr/bin/soffice")

    def render(tool, source, names, workdir):
        return {name: _png() for name in names}

    monkeypatch.setattr(office, "_render", render)


def test_the_metafiles_of_the_package_are_listed_in_archive_order(tmp_path):
    assert office.metafiles(_workbook(tmp_path)) == [
        "word/media/image1.emf",
        "word/media/image10.emf",
    ]


def test_the_copy_replaces_each_metafile_and_repoints_its_relationship(tmp_path, stub_renderer):
    copy = office.rasterised_copy(_workbook(tmp_path), tmp_path / "work")

    assert copy is not None and copy.name == "cuaderno.docx"
    with zipfile.ZipFile(copy) as archive:
        names = archive.namelist()
        assert "word/media/image1.emf.png" in names and "word/media/image10.emf.png" in names
        assert "word/media/image1.emf" not in names and "word/media/image10.emf" not in names
        assert archive.read("word/media/photo.png") == b"\x89PNG photo", "untouched"
        rels = archive.read("word/_rels/document.xml.rels").decode()
        assert 'Target="media/image1.emf.png"' in rels
        assert 'Target="media/image10.emf.png"' in rels, "image1 must not eat image10"
        assert 'Target="media/photo.png"' in rels
        types = archive.read("[Content_Types].xml").decode()
        assert 'Extension="png"' in types


def test_a_package_that_already_declares_png_is_not_told_twice(tmp_path, stub_renderer):
    types = _TYPES.replace("</Types>", '<Default Extension="png" ContentType="image/png"/></Types>')
    source = _docx(
        tmp_path / "cuaderno.docx",
        {
            "[Content_Types].xml": types.encode(),
            "word/_rels/document.xml.rels": _DOCUMENT_RELS.encode(),
            "word/media/image1.emf": b"EMF",
        },
    )
    copy = office.rasterised_copy(source, tmp_path / "work")
    with zipfile.ZipFile(copy) as archive:
        assert archive.read("[Content_Types].xml").decode().count('Extension="png"') == 1


def test_a_slide_deck_points_at_its_media_through_a_parent_path(tmp_path, stub_renderer):
    source = _docx(
        tmp_path / "tema.pptx",
        {
            "[Content_Types].xml": _TYPES.encode(),
            "ppt/slides/slide1.xml": b"<p:sld/>",
            "ppt/slides/_rels/slide1.xml.rels": (
                '<Relationships><Relationship Id="rId2" Type="…/image" '
                'Target="../media/image3.wmf"/></Relationships>'
            ).encode(),
            "ppt/media/image3.wmf": b"WMF",
        },
    )
    copy = office.rasterised_copy(source, tmp_path / "work")
    with zipfile.ZipFile(copy) as archive:
        assert "ppt/media/image3.wmf.png" in archive.namelist()
        assert 'Target="../media/image3.wmf.png"' in archive.read(
            "ppt/slides/_rels/slide1.xml.rels"
        ).decode()


def test_a_metafile_the_renderer_could_not_draw_is_left_as_it_was(tmp_path, monkeypatch):
    monkeypatch.setattr(office, "rasteriser", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(
        office, "_render", lambda tool, source, names, workdir: {"word/media/image1.emf": _png()}
    )
    copy = office.rasterised_copy(_workbook(tmp_path), tmp_path / "work")
    with zipfile.ZipFile(copy) as archive:
        assert "word/media/image10.emf" in archive.namelist()
        assert 'Target="media/image10.emf"' in archive.read("word/_rels/document.xml.rels").decode()


def test_nothing_to_do_reads_the_original(tmp_path, stub_renderer):
    plain = _docx(tmp_path / "plano.docx", {"word/media/photo.png": b"\x89PNG"})
    assert office.rasterised_copy(plain, tmp_path / "work") is None
    not_a_zip = tmp_path / "raro.docx"
    not_a_zip.write_bytes(b"PK")
    assert office.rasterised_copy(not_a_zip, tmp_path / "work") is None


def test_without_libreoffice_the_original_is_read_and_the_loss_is_said(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(office, "rasteriser", lambda: None)
    assert office.rasterised_copy(_workbook(tmp_path), tmp_path / "work") is None


def test_the_page_is_cropped_to_what_is_drawn_on_it():
    from PIL import Image

    page = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    for x in range(100, 140):
        for y in range(50, 70):
            page.putpixel((x, y), (0, 0, 0, 255))
    cropped = Image.open(io.BytesIO(office.crop_to_content(page)))
    assert cropped.size == (40 + 2 * office.CONTENT_MARGIN_PX, 20 + 2 * office.CONTENT_MARGIN_PX)
    assert cropped.getpixel((0, 0)) == (255, 255, 255), "transparent paper reads as white"
    assert cropped.getpixel((office.CONTENT_MARGIN_PX, office.CONTENT_MARGIN_PX)) == (0, 0, 0)


def test_a_blank_page_becomes_a_small_blank_picture_and_not_nothing():
    from PIL import Image

    cropped = Image.open(io.BytesIO(office.crop_to_content(Image.new("RGB", (400, 300), "white"))))
    assert cropped.size == (office.BLANK_SIDE_PX, office.BLANK_SIDE_PX)


def test_the_office_fingerprint_records_whether_metafiles_could_be_rendered(tmp_path, monkeypatch):
    docx = tmp_path / "cuaderno.docx"
    docx.write_bytes(b"PK")
    monkeypatch.setattr(office, "rasteriser", lambda: "/usr/bin/soffice")
    with_tool = pages.fingerprint_for(docx, "m", 200, False)
    monkeypatch.setattr(office, "rasteriser", lambda: None)
    without = pages.fingerprint_for(docx, "m", 200, False)

    assert with_tool["rasteriser"] == "soffice" and without["rasteriser"] == ""
    assert not pages.same_document(without, with_tool), (
        "installing LibreOffice expires what was read without it"
    )
    pdf = tmp_path / "examen.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert "rasteriser" not in pages.fingerprint_for(pdf, "m", 200, False)


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not on the PATH")
def test_libreoffice_renders_the_reference_equation(tmp_path):
    # The 588-byte WMF the reference workbook embeds for `ax² + bx + c = 0`. What is
    # measured: it comes out at VECTOR resolution — 380×54 of content at 384 dpi — and not
    # as the 96×13 Pillow could never have opened anyway.
    from PIL import Image

    source = _docx(
        tmp_path / "cuaderno.docx",
        {
            "[Content_Types].xml": _TYPES.encode(),
            "word/_rels/document.xml.rels": (
                '<Relationships><Relationship Id="rId1" Type="…/image" '
                'Target="media/image1.wmf"/></Relationships>'
            ).encode(),
            "word/media/image1.wmf": (FIXTURES / "equation.wmf").read_bytes(),
        },
    )
    copy = office.rasterised_copy(source, tmp_path / "work")

    assert copy is not None
    with zipfile.ZipFile(copy) as archive:
        image = Image.open(io.BytesIO(archive.read("word/media/image1.wmf.png")))
    assert image.width > 300 and image.height > 40
    assert image.getpixel((0, 0)) == (255, 255, 255)
    assert image.convert("L").getextrema()[0] < 128, "something is drawn on it"

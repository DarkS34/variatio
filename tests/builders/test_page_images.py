"""What a rendered page is sent to the model as: bounded in pixels, and a JPEG when it is a scan.

Measured on 2026-09-15: the scanned exercise sheets of the nursing subject failed on every page
with Cerebras' 413 «Request payload exceeds maximum size», because a photograph of paper rendered
at 200 dpi is a PNG of several megabytes — and one whose page declares its pixels as points is a
9.4 MB PNG of 6 892 × 9 745 px. The same page as a JPEG was read.
"""

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from variatio.builders.source_docs import pages

PNG_MAGIC = b"\x89PNG"
JPEG_MAGIC = b"\xff\xd8\xff"


def _text_pdf(path: Path) -> Path:
    """The smallest PDF with a text layer: one Letter page, Helvetica, one line."""
    content = "BT /F1 18 Tf 72 720 Td (Pregunta 1. Que es un farmaco?) Tj ET"
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
    path.write_bytes(out.encode("latin-1"))
    return path


def _scan(size: tuple[int, int]) -> Image.Image:
    """A photograph of paper: grey noise over an off-white ground, incompressible as a PNG."""
    noise = Image.effect_noise(size, 40).convert("RGB")
    return Image.blend(Image.new("RGB", size, (236, 233, 226)), noise, 0.25)


def _decoded(encoded: str) -> tuple[bytes, Image.Image]:
    raw = base64.b64decode(encoded)
    return raw, Image.open(io.BytesIO(raw))


# THE RENDER DENSITY --------------------------------------------------------------------------


def test_an_a4_and_an_a3_page_render_at_the_configured_density():
    assert pages.render_scale(595, 842, 200) == pytest.approx(200 / 72)
    assert pages.render_scale(842, 1191, 200) == pytest.approx(200 / 72, rel=1e-3)


def test_a_page_declared_bigger_renders_no_more_pixels_than_two_a4_pages_hold():
    # A phone-scan PDF declares its pixels as points: 2 481 × 3 508 pt is 17 A4 pages of area.
    scale = pages.render_scale(2481, 3508, 200)
    rendered = 2481 * scale * 3508 * scale
    ceiling = pages.PAGE_MAX_A4_AREAS * pages.A4_AREA_PT * (200 / 72) ** 2
    assert rendered == pytest.approx(ceiling)
    assert scale < 200 / 72


# THE ENCODING --------------------------------------------------------------------------------


def test_a_typeset_page_keeps_the_png_it_always_had():
    page = Image.new("RGB", (400, 300), "white")
    assert pages.encode_page(page, scanned=False).startswith(PNG_MAGIC)


def test_a_scanned_page_is_a_jpeg_from_the_start():
    assert pages.encode_page(_scan((400, 300)), scanned=True).startswith(JPEG_MAGIC)


def test_a_typeset_page_whose_png_is_too_heavy_falls_back_to_jpeg(monkeypatch):
    monkeypatch.setattr(pages, "PAGE_PNG_MAX_BYTES", 1_000)
    assert pages.encode_page(_scan((400, 300)), scanned=False).startswith(JPEG_MAGIC)


def test_a_picture_of_a_document_too_big_for_the_request_is_shrunk_and_sent_as_jpeg(monkeypatch):
    monkeypatch.setattr(pages, "IMAGE_MAX_PIXELS", 100_000)
    monkeypatch.setattr(pages, "PAGE_PNG_MAX_BYTES", 50_000)
    raw = pages._encode_image(_scan((1200, 900)))
    image = Image.open(io.BytesIO(raw))
    assert raw.startswith(JPEG_MAGIC)
    assert image.width * image.height <= 100_000 * 1.01


def test_a_small_picture_is_still_the_png_its_cached_reading_is_keyed_by():
    raw = pages._encode_image(Image.new("RGB", (1200, 900), "white"))
    assert raw.startswith(PNG_MAGIC)


# REAL PDFS -----------------------------------------------------------------------------------


@pytest.fixture
def pdfium():
    return pytest.importorskip("pypdfium2")


def test_a_pdf_page_with_no_text_layer_travels_as_a_bounded_jpeg(tmp_path, pdfium):
    path = tmp_path / "escaneado.pdf"
    # Saved at 72 dpi, so the page declares 1 240 × 1 754 pt: over two A4 pages of area.
    _scan((1240, 1754)).save(path, "PDF", resolution=72)

    count, images = pages.page_images(path, dpi=200)
    raw, image = _decoded(next(images))
    images.close()

    assert count == 1
    assert raw.startswith(JPEG_MAGIC)
    ceiling = pages.PAGE_MAX_A4_AREAS * pages.A4_AREA_PT * (200 / 72) ** 2
    assert image.width * image.height <= ceiling * 1.01


def test_a_pdf_page_with_a_text_layer_still_travels_as_a_png(tmp_path, pdfium):
    count, images = pages.page_images(_text_pdf(tmp_path / "examen.pdf"), dpi=100)
    raw, image = _decoded(next(images))
    images.close()

    assert count == 1
    assert raw.startswith(PNG_MAGIC)
    assert image.size == (round(612 * 100 / 72), round(792 * 100 / 72))


def test_only_the_named_pages_are_rendered_in_the_order_asked(tmp_path, pdfium):
    path = tmp_path / "tres.pdf"
    first, *rest = [_scan((100 + 50 * n, 100)) for n in range(3)]
    first.save(path, "PDF", resolution=72, save_all=True, append_images=rest)

    count, images = pages.page_images(path, dpi=72, numbers=[3, 1, 9])
    widths = [_decoded(image)[1].width for image in images]

    assert count == 3
    assert widths == [200, 100]

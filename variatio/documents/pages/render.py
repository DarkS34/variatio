"""Drawing a PDF's pages with PDFium, under the one lock every PDFium call takes.

PDFium is not thread-safe and this process calls it from two threads at once, so
`_PDFIUM_LOCK` lives here alone and every module that draws a page asks this one.
"""

import base64
import io
import threading
from collections.abc import Iterator
from pathlib import Path

from ... import config


# PDFium is not thread-safe and this process calls it from two threads at once: the job
# thread rendering a page and the request thread counting pages for `/raw`. Interleaved,
# the library's global state corrupts and EVERY later load in the process answers
# "Data format error" until it is restarted. Every PDFium call goes through this lock,
# and the lock is released between pages so a model call never holds it.
_PDFIUM_LOCK = threading.RLock()


def page_count(pdf_path: str | Path) -> int:
    """How many pages a PDF declares, without rendering or reading a single one."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return 0
    try:
        with _PDFIUM_LOCK:
            document = pdfium.PdfDocument(str(pdf_path))
            try:
                return len(document)
            finally:
                document.close()
    except Exception:
        return 0


def page_images(
    pdf_path: Path, dpi: int, first: int = 1, numbers: list[int] | None = None
) -> tuple[int, Iterator[str]]:
    """`(page_count, generator of base64 images)` — rendered one at a time, not all at once.

    `numbers` names the pages to render, counted from 1; without it every page from `first`
    on is rendered. What each image is encoded as is `encode_page`'s decision.
    """
    # Imported here and NEVER at module scope: pypdfium2 ships with the `builders` extra,
    # which the runtime pipeline does not install.
    try:
        import pypdfium2 as pdfium
    except ImportError as e:
        raise ImportError(
            "Rendering PDF pages needs pypdfium2, which ships with the builders extra. "
            "Install it with: uv sync --extra builders"
        ) from e

    with _PDFIUM_LOCK:
        document = pdfium.PdfDocument(str(pdf_path))
        count = len(document)

    def render():
        """Yield each requested page as a base64 image.

        Each page is rendered whole under the lock — page, bitmap and encoded bytes — and
        only the bytes cross the `yield`, so nothing PDFium owns is touched while the model
        reads.
        """
        wanted = numbers if numbers is not None else range(max(first, 1), count + 1)
        try:
            for number in wanted:
                if not 1 <= number <= count:
                    continue
                with _PDFIUM_LOCK:
                    page = document[number - 1]
                    width, height = page.get_size()
                    scanned = _scanned(page)
                    # Colour is load-bearing: on these exam PDFs the correct option is
                    # marked by nothing but its colour. Never render greyscale to save bytes.
                    bitmap = page.render(scale=render_scale(width, height, dpi))
                    encoded = encode_page(bitmap.to_pil(), scanned)
                    page.close()
                yield base64.b64encode(encoded).decode()
        finally:
            with _PDFIUM_LOCK:
                document.close()

    return count, render()


def page_picture(pdf_path: str | Path, number: int, width_px: int):
    """One page of a PDF as a PIL image `width_px` wide, or None when it cannot be drawn.

    The page as a PERSON reads it, not as the model is sent it (`page_images`): no DPI
    setting and no fingerprint depend on it. A page far taller than it is wide is drawn
    narrower, so its height never passes three times `width_px`.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    try:
        with _PDFIUM_LOCK:
            document = pdfium.PdfDocument(str(pdf_path))
            try:
                if not 1 <= number <= len(document):
                    return None
                page = document[number - 1]
                width, height = page.get_size()
                scale = min(width_px / max(width, 1.0), 3 * width_px / max(height, 1.0))
                image = page.render(scale=scale).to_pil()
                page.close()
                return image
            finally:
                document.close()
    except Exception:
        return None


def page_sizes(pdf_path: str | Path) -> list[tuple[float, float]]:
    """The `(width, height)` of every page of a PDF in points, in order; `[]` when unreadable."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    try:
        with _PDFIUM_LOCK:
            document = pdfium.PdfDocument(str(pdf_path))
            try:
                return [document.get_page_size(index) for index in range(len(document))]
            finally:
                document.close()
    except Exception:
        return []


def page_texts(pdf_path: str | Path) -> list[str]:
    """The text layer of every page of a PDF, in order; `[]` when the file cannot be read."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    try:
        with _PDFIUM_LOCK:
            document = pdfium.PdfDocument(str(pdf_path))
            count = len(document)
        texts: list[str] = []
        try:
            for index in range(count):
                with _PDFIUM_LOCK:
                    page = document[index]
                    textpage = page.get_textpage()
                    texts.append(textpage.get_text_bounded())
                    textpage.close()
                    page.close()
        finally:
            with _PDFIUM_LOCK:
                document.close()
        return texts
    except Exception:
        return []


# THE PAGE AS THE MODEL RECEIVES IT ----------------------------------------------------------------
#
# What reaches the model is bounded in BYTES, and a scanned page is where the bound bites: a
# photograph of paper does not compress as a PNG. Measured on 2026-09-15, the three exercise
# sheets of the nursing subject that were scans failed on EVERY page with Cerebras' 413
# «Request payload exceeds maximum size» (10 MiB a request); a scan whose page declares its
# pixels as points renders at 200 dpi to 6 892 × 9 745 px, a 9.4 MB PNG, and was refused the
# same way, while the same page as a 16 MP JPEG was read in 0.9 s — for 1 574 prompt tokens,
# exactly what the 7.7 MP one cost, because the endpoint resamples the picture anyway.

# A4 in points: the page every DPI setting of this route was measured on. How many of them
# one render may cover, and when a page leaves PNG for JPEG, are settings
# (`builders.transcribe_page_*`).
A4_AREA_PT = 595 * 842


def render_scale(width_pt: float, height_pt: float, dpi: int) -> float:
    """The scale a page is rendered at: the configured DPI, unless the page is too big for it."""
    scale = dpi / 72
    area = max(width_pt, 1.0) * max(height_pt, 1.0)
    ceiling = config.TRANSCRIBE_PAGE_MAX_A4_AREAS * A4_AREA_PT
    return scale if area <= ceiling else scale * (ceiling / area) ** 0.5


def encode_page(image, scanned: bool) -> bytes:
    """The rendered page as the bytes the model is sent: a PNG, or a JPEG for a photograph.

    A scanned page goes as JPEG without trying the PNG: its noise is incompressible losslessly
    and JPEG is what the scanner stored in the first place. A typeset page keeps the PNG it has
    always had — nothing about its cached transcription changes — unless that PNG is heavy,
    which is a page carrying a big photograph.
    """
    if not scanned:
        png = io.BytesIO()
        image.save(png, format="PNG")
        if png.tell() <= config.TRANSCRIBE_PAGE_PNG_MAX_BYTES:
            return png.getvalue()
    jpeg = io.BytesIO()
    image.convert("RGB").save(jpeg, format="JPEG", quality=config.TRANSCRIBE_PAGE_JPEG_QUALITY)
    return jpeg.getvalue()


def _scanned(page) -> bool:
    """Whether a page carries no text layer at all: a picture of a page, not a typeset one."""
    textpage = page.get_textpage()
    try:
        return textpage.count_chars() == 0
    finally:
        textpage.close()

"""The raw documents as their author laid them out: the original, one page at a time.

Step 1 opens a document beside its transcription, so whoever corrects a page reads the page
it came from. Every format takes one road: a PDF is read as it is, a Word or PowerPoint file
is exported to PDF by LibreOffice once, and a page is drawn by PDFium and kept as an image.
Both are kept under `cache/originals/` by the SOURCE's hash, so a replaced document is
exported again and a copied workspace is not.

The two views go page to page only where the transcription holds one page per page of that
very file: a PDF or a deck as it was read, no page inserted or deleted by hand. A Word file
is one transcribed page against the many of its export, and its two views then scroll apart;
`unpaired` says why, so the reader can say it too.

Nothing here raises to a route: a document with no original on disk, no LibreOffice or no
PDFium answers None, and the reader shows the transcription alone.
"""

import functools
import io
import os
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from variatio.builders import source_docs
from variatio.builders.source_docs.files import source_hash
from variatio.core.workspace import Workspace

# Twice a reading column on a dense screen; a page is drawn once and kept.
PAGE_WIDTH_PX = 1600
# How many times its width a drawn page may be tall (`pages.page_picture` caps it there).
TALLEST = 3
# A typeset page is a small PNG; one past this carries a photograph and goes as JPEG.
HEAVY_PNG_BYTES = 600_000
JPEG_QUALITY = 85
EXPORT_TIMEOUT_SECONDS = 180

# Where the tutor's reader kept these same files, under the same names, until the reader
# moved to step 1 (2026-10-08); adopted once per workspace so no export is done twice.
_LEGACY_DIR = "tutor_originals"

_MEDIA = {".png": "image/png", ".jpg": "image/jpeg"}
_export_lock = threading.Lock()
_unexportable: set[str] = set()
_adopted: set[Path] = set()


@dataclass(frozen=True)
class Original:
    """One raw document as a PDF to draw: the file, its pages' shapes, its source's hash."""

    pdf: Path
    ratios: tuple[float, ...]
    digest: str

    @property
    def pages(self) -> int:
        """How many pages the document has."""
        return len(self.ratios)

    @property
    def version(self) -> str:
        """What a page's address carries so a replaced document is never read from a cache."""
        return self.digest[:16]

    def summary(self, unpaired: str | None) -> dict:
        """Return what the reader is told: the pages, the version, each page's shape, the pairing.

        The shapes — each page's height over its width — let the reader lay the whole document
        out before a single page arrives, so scrolling through it never moves what is already
        on screen. `unpaired` is why the transcription does not go page to page with it, or
        None when it does (`unpaired` below).
        """
        return {
            "pages": self.pages,
            "version": self.version,
            "ratios": list(self.ratios),
            "paired": unpaired is None,
            "unpaired": unpaired,
        }


def original_for(ws: Workspace, source: Path) -> Original | None:
    """Return the original of one raw document as a PDF, exporting it if needed.

    `source` is a file the slot holds, checked by the caller (`raw_data.document`). None for
    plain text — its transcription IS the original — and whenever the PDF cannot be made or
    opened.
    """
    suffix = source.suffix.lower()
    if suffix not in source_docs.CONVERTED_EXTS or not source.is_file():
        return None
    _adopt_legacy(ws)
    stat = source.stat()
    digest = _digest(str(source), stat.st_size, stat.st_mtime_ns)
    pdf = source if suffix == ".pdf" else _exported(ws, source, digest)
    if pdf is None:
        return None
    ratios = tuple(
        round(min(height / max(width, 1.0), TALLEST), 4)
        for width, height in source_docs.page_sizes(pdf)
    )
    return Original(pdf, ratios, digest) if ratios else None


def unpaired(original: Original, meta: dict, pages: int) -> str | None:
    """Say why the transcription does not hold one page per page of this original, or None.

    `meta` is the page cache's record of the document and `pages` how many pages it holds.
    `moved`: a page was inserted or deleted by hand (`restructured`), which moves every page
    after it. `source`: the pages were read from other bytes than these. `count`: they are not
    as many as the original's — a Word file is read as one text.
    """
    if meta.get("restructured"):
        return "moved"
    if meta.get("source_sha256") != original.digest:
        return "source"
    if pages != original.pages:
        return "count"
    return None


def page_image(ws: Workspace, original: Original, number: int) -> tuple[bytes, str] | None:
    """Return one page of an original as image bytes and their media type, drawn once."""
    if not 1 <= number <= original.pages:
        return None
    directory = originals_dir(ws) / f"{original.digest}-{PAGE_WIDTH_PX}"
    for suffix, media in _MEDIA.items():
        kept = directory / f"{number:04d}{suffix}"
        if kept.is_file():
            return kept.read_bytes(), media
    image = source_docs.page_picture(original.pdf, number, PAGE_WIDTH_PX)
    if image is None:
        return None
    data, suffix = _encoded(image)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        working = directory / f".{number:04d}.{threading.get_ident()}.tmp"
        working.write_bytes(data)
        os.replace(working, directory / f"{number:04d}{suffix}")
    except OSError as e:
        logger.warning(f"[raw] No se pudo guardar la página {number} de '{original.pdf.name}' ({e})")
    return data, _MEDIA[suffix]


def originals_dir(ws: Workspace) -> Path:
    """The documents as PDFs and drawn pages, by the hash of their source."""
    return ws.cache_dir / "originals"


@functools.lru_cache(maxsize=64)
def _digest(path: str, size: int, mtime_ns: int) -> str:
    """Return a source's hash, remembered while its size and time stay what they were."""
    return source_hash(path)


def _adopt_legacy(ws: Workspace) -> None:
    """Take over the tutor reader's old cache once: moved where it is still missing, else dropped.

    The files are named by the source's hash in both places, so an Office document LibreOffice
    already exported is not exported again.
    """
    legacy = ws.cache_dir / _LEGACY_DIR
    with _export_lock:
        if legacy in _adopted:
            return
        _adopted.add(legacy)
        if not legacy.is_dir():
            return
        target = originals_dir(ws)
        try:
            if target.exists():
                shutil.rmtree(legacy)
            else:
                legacy.rename(target)
        except OSError as e:
            logger.warning(f"[raw] No se pudo recoger la caché de originales del tutor ({e})")


def _exported(ws: Workspace, source: Path, digest: str) -> Path | None:
    """Return the PDF of an Office document, asking LibreOffice for it the first time.

    One export at a time in the process, and a document LibreOffice could not export is not
    asked for again until a restart: a request must not wait out the timeout every time.
    """
    target = originals_dir(ws) / f"{digest}.pdf"
    with _export_lock:
        if target.is_file():
            return target
        if digest in _unexportable:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        workdir = Path(tempfile.mkdtemp(dir=target.parent, prefix=".export-"))
        try:
            made = source_docs.office.pdf_copy(source, workdir, EXPORT_TIMEOUT_SECONDS)
            if made is None:
                _unexportable.add(digest)
                logger.warning(
                    f"[raw] LibreOffice no pudo exportar '{source.name}' a PDF; "
                    "el lector muestra su transcripción"
                )
                return None
            os.replace(made, target)
            return target
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


def _encoded(image) -> tuple[bytes, str]:
    """Return a drawn page as PNG, or as JPEG when the PNG is heavy, with its suffix."""
    png = io.BytesIO()
    image.save(png, format="PNG", optimize=True)
    if png.tell() <= HEAVY_PNG_BYTES:
        return png.getvalue(), ".png"
    jpeg = io.BytesIO()
    image.convert("RGB").save(jpeg, format="JPEG", quality=JPEG_QUALITY)
    return jpeg.getvalue(), ".jpg"

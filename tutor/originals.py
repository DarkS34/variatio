"""The notes as their author laid them out: the original document, one page at a time.

The reader a reply's place opens shows the document itself — its layout, its figures, its
slides — and keeps the transcription the tutor searches as a second view. Every format
takes one road: a PDF is read as it is, a Word or PowerPoint file is exported to PDF by
LibreOffice once, and a page is drawn by PDFium and kept as an image. Both are kept under
`cache/tutor_originals/` by the SOURCE's hash, so a replaced document is exported again and
a copied workspace is not.

A place is a section of the transcription, so each section needs the page it starts on.
Where the page cache holds one file per page of the original — a PDF, a deck — that is
arithmetic: the offset of the section's heading in the joined text against the offset each
page starts at. Where it does not — a Word file is one cached page; a document whose pages
a person inserted or deleted — the heading is looked for in the PDF's own text, in order,
and a section not found opens where the one before it did. That answer is approximate, and
the reader lets the student turn the page.

Nothing here raises to a route: a document with no original on disk, no LibreOffice or no
PDFium answers None, and the reader shows the transcription as it always did.
"""

import functools
import io
import os
import re
import shutil
import tempfile
import threading
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from variatio.builders import source_docs
from variatio.builders.source_docs.files import source_hash
from variatio.builders.source_docs.markdown import CODE_FENCE_RE, HEADING_RE
from variatio.core.lexicon import fold
from variatio.core.workspace import Workspace

from . import paths

# Twice a reading column on a dense screen; a page is drawn once and kept.
PAGE_WIDTH_PX = 1600
# How many times its width a drawn page may be tall (`pages.page_picture` caps it there).
TALLEST = 3
# A typeset page is a small PNG; one past this carries a photograph and goes as JPEG.
HEAVY_PNG_BYTES = 600_000
JPEG_QUALITY = 85
EXPORT_TIMEOUT_SECONDS = 180
# A page listing this many section titles that are found again further on is a table of
# contents, and no section starts on it.
NAVIGATION_TITLES = 6

_MEDIA = {".png": "image/png", ".jpg": "image/jpeg"}
_export_lock = threading.Lock()
_unexportable: set[str] = set()


@dataclass(frozen=True)
class Original:
    """One document of the notes as a PDF to draw: the file, its pages' shapes, its source's hash."""

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

    def summary(self) -> dict:
        """Return what the reader is told: the pages, the version, and each page's height over its width.

        The shapes let the reader lay the whole document out before a single page arrives,
        so scrolling through it never moves what is already on screen.
        """
        return {"pages": self.pages, "version": self.version, "ratios": list(self.ratios)}


def original_for(ws: Workspace, name: str) -> Original | None:
    """Return the original of one document of the corpus as a PDF, exporting it if needed.

    None for a name that is not a file of the raw corpus, for plain text (its transcription
    IS the original) and whenever the PDF cannot be made or opened.
    """
    source = ws.raw_corpus_dir / name
    suffix = source.suffix.lower()
    if Path(name).name != name or suffix not in source_docs.CONVERTED_EXTS or not source.is_file():
        return None
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


def section_pages(
    original: Original,
    meta: dict,
    pages: list[str],
    seams: list[dict],
    sections: list[tuple[str, str, str]],
) -> list[int]:
    """Return the page of the original each section of `split_sections` starts on.

    One per section, never decreasing. Counted when the cache holds one page per page of
    this very file, searched in the PDF's text otherwise.
    """
    one_to_one = (
        meta.get("source_sha256") == original.digest
        and not meta.get("restructured")
        and len(pages) == original.pages
    )
    counted = _counted(pages, seams, sections) if one_to_one else None
    return counted if counted is not None else _searched(original, sections)


def page_image(ws: Workspace, original: Original, number: int) -> tuple[bytes, str] | None:
    """Return one page of an original as image bytes and their media type, drawn once."""
    if not 1 <= number <= original.pages:
        return None
    directory = paths.originals_dir(ws) / f"{original.digest}-{PAGE_WIDTH_PX}"
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
        logger.warning(f"[tutor] No se pudo guardar la página {number} de '{original.pdf.name}' ({e})")
    return data, _MEDIA[suffix]


@functools.lru_cache(maxsize=64)
def _digest(path: str, size: int, mtime_ns: int) -> str:
    """Return a source's hash, remembered while its size and time stay what they were."""
    return source_hash(path)


def _exported(ws: Workspace, source: Path, digest: str) -> Path | None:
    """Return the PDF of an Office document, asking LibreOffice for it the first time.

    One export at a time in the process, and a document LibreOffice could not export is not
    asked for again until a restart: a request must not wait out the timeout every time.
    """
    target = paths.originals_dir(ws) / f"{digest}.pdf"
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
                    f"[tutor] LibreOffice no pudo exportar '{source.name}' a PDF; "
                    "el lector muestra su transcripción"
                )
                return None
            os.replace(made, target)
            return target
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


def _counted(
    pages: list[str], seams: list[dict], sections: list[tuple[str, str, str]]
) -> list[int] | None:
    """Place each section by where its heading falls among the pages, or return None.

    `split_sections` opens one section per heading and, before the first, one for whatever
    text precedes it; None when the headings found here do not line up with that.
    """
    starts = source_docs.page_starts(pages, seams)
    headings = _heading_offsets(source_docs.join_pages(pages, seams))
    if len(headings) != sum(1 for location, _title, _body in sections if location):
        return None
    offsets = iter(headings)
    return [
        bisect_right(starts, next(offsets) if location else 0)
        for location, _title, _body in sections
    ]


def _heading_offsets(text: str) -> list[int]:
    """Return where each heading outside a code fence starts in `text`."""
    blanked = CODE_FENCE_RE.sub(lambda match: " " * len(match.group(0)), text)
    found: list[int] = []
    offset = 0
    for line in blanked.splitlines(keepends=True):
        if HEADING_RE.match(line):
            found.append(offset)
        offset += len(line)
    return found


def _searched(original: Original, sections: list[tuple[str, str, str]]) -> list[int]:
    """Place each section on the first page, from the last one found, that carries its title.

    A title counts where it stands as a line of its own, numbering and punctuation aside:
    a mention in a sentence is not a heading, and a line of a table of contents ends in a
    page number. A section whose title is on no page ahead stays with the one before it.
    """
    carried = [_title_lines(text) for text in source_docs.page_texts(original.pdf)]
    where: dict[str, list[int]] = {}
    for number, lines in enumerate(carried, 1):
        for line in lines:
            where.setdefault(line, []).append(number)
    titles = {_bare(title) for _location, title, _body in sections} - {""}
    navigation = {
        number
        for number, lines in enumerate(carried, 1)
        if sum(1 for title in titles & lines if where[title][-1] > number) >= NAVIGATION_TITLES
    }
    found: list[int] = []
    page = 1
    for _location, title, _body in sections:
        ahead = [n for n in where.get(_bare(title), []) if n >= page and n not in navigation]
        page = ahead[0] if ahead else page
        found.append(page)
    return found


def _title_lines(text: str) -> set[str]:
    """Return what a page's lines read as titles: each line, and each pair a title wrapped over."""
    lines = [bare for bare in (_bare(line) for line in text.splitlines()) if bare]
    return set(lines) | {f"{first} {second}" for first, second in zip(lines, lines[1:])}


def _bare(text: str) -> str:
    """Return a title or a line folded, without markdown emphasis, numbering or end punctuation."""
    return re.sub(r"^[\W\d_]+|[\W_]+$", "", fold(re.sub(r"[*_`]", "", text)))


def _encoded(image) -> tuple[bytes, str]:
    """Return a drawn page as PNG, or as JPEG when the PNG is heavy, with its suffix."""
    png = io.BytesIO()
    image.save(png, format="PNG", optimize=True)
    if png.tell() <= HEAVY_PNG_BYTES:
        return png.getvalue(), ".png"
    jpeg = io.BytesIO()
    image.convert("RGB").save(jpeg, format="JPEG", quality=JPEG_QUALITY)
    return jpeg.getvalue(), ".jpg"

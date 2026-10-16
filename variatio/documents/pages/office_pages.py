"""An Office document as pages: a deck one page per slide with its speaker notes, and the
body pictures of either kind read through the image cache.
"""

import base64
import hashlib
import tempfile
from pathlib import Path

from loguru import logger

from ... import wording as wording_sets
from ...core import progress
from .. import office
from ..markdown import (
    convert,
    export_markdown,
    picture_mark,
    pictures,
    slide_numbers,
    splice_pictures,
    tidy_markdown,
)
from .images import _encode_image, _read_image_cache, _transcribe_image, _write_image_cache
from .seams import PARAGRAPH

# THE PICTURES AND THE NOTES OF AN OFFICE DOCUMENT --------------------------------------------------
#
# Docling translates a `.docx` or `.pptx` faithfully — it declares its structure, so there is
# nothing to infer — and writes `<!-- image -->` for every picture, which is exactly the part
# of these documents that carries the formulas and the expected outputs. Each picture is one
# model call under the same rules a figure on a rendered page gets, and the answer is put
# back where the picture stood. A deck's speaker notes are the other thing Docling never
# opens, and they are read straight off the file and quoted under their slide: declared text,
# like the slide's own, and no call at all.


def transcribe_office(
    source: Path,
    converter,
    model: str,
    prompts,
    tag: str = "",
    images_dir: str | Path | None = None,
) -> tuple[list[str], dict]:
    """Convert an Office document with Docling, read its pictures one call each, add its notes.

    Returns the pages — one per slide for a deck, one for anything else — and a tally: how
    many pictures the body carried, how many left the unreadable mark, and how many slides
    carried speaker notes.
    """
    # The metafiles are rendered into a copy that Docling reads in the original's place;
    # the copy lives as long as the conversion and nothing keys on it.
    with tempfile.TemporaryDirectory(prefix="variatio-office-") as workdir:
        prepared = office.rasterised_copy(source, workdir) or source
        document = convert(converter, prepared)
    found = pictures(document)
    notes = office.speaker_notes(source)
    tally = {"images_total": len(found), "images_unreadable": 0, "notes_total": len(notes)}
    readings = (
        _read_pictures(source, found, model, prompts, tag, images_dir, tally) if found else {}
    )
    if notes:
        logger.info(f"{tag}{source.name}: speaker notes on {len(notes)} slide(s)")
    wording = wording_sets.beside(prompts)
    per_slide = source.suffix.lower() == ".pptx"
    return _office_pages(document, found, readings, notes, wording, per_slide), tally


def _read_pictures(
    source: Path,
    found: list[tuple[str, object]],
    model: str,
    prompts,
    tag: str,
    images_dir: str | Path | None,
    tally: dict,
) -> dict[str, str]:
    """Read every picture, one call each, through the memo and the content-hash cache.

    Returns `{self_ref: reading}`; an unreadable picture gets the mark and is counted in
    `tally["images_unreadable"]`.
    """
    logger.info(f"{tag}{source.name}: {len(found)} picture(s) to read with '{model}'")
    readings: dict[str, str] = {}
    memo: dict[str, str] = {}
    reused = 0
    unreadable = wording_sets.beside(prompts).UNREADABLE_IMAGE_MARK
    with progress.step(
        "transcribe_image", f"{source.name}: reading pictures", len(found)
    ) as reporter:
        for index, (ref, image) in enumerate(found, 1):
            progress.checkpoint()
            reporter.start(index, detail=f"picture {index}/{len(found)}")
            if image is None:
                readings[ref] = unreadable
                tally["images_unreadable"] += 1
                continue
            encoded = _encode_image(image)
            digest = hashlib.sha256(encoded).hexdigest()
            reading = memo.get(digest)
            if reading is None:
                reading = _read_image_cache(images_dir, digest, model)
            if reading is None:
                reading = _transcribe_image(
                    base64.b64encode(encoded).decode(), index, len(found), model, tag, prompts
                )
                if reading is None:
                    readings[ref] = unreadable
                    tally["images_unreadable"] += 1
                    continue
                _write_image_cache(images_dir, digest, model, reading)
            else:
                reused += 1
            memo[digest] = reading
            readings[ref] = reading
    logger.info(
        f"{tag}{source.name}: {len(found) - reused - tally['images_unreadable']} picture(s) "
        f"read, {reused} reused, {tally['images_unreadable']} unreadable"
    )
    return readings


def _office_pages(
    document,
    found: list[tuple[str, object]],
    readings: dict[str, str],
    notes: dict[int, str],
    wording,
    per_slide: bool,
) -> list[str]:
    """Serialise the document with its pictures' readings in place and its notes under each slide.

    Tidied with the picture marks still standing and the readings spliced in afterwards:
    the escape undo exists for Docling's output and must never touch what the model wrote —
    nor a note, which is the author's own text and is added after the same pass. A deck is
    one page per slide, EVERY slide, so page N is slide N whatever it holds — a slide with
    nothing on it is an empty page, exactly as a blank PDF page is; anything else is one
    page. A deck Docling handed over without slide numbers is one page with its notes in
    order under the text, rather than one with its notes lost.
    """
    marks = {ref: picture_mark(ref) for ref, _ in found}
    numbers = slide_numbers(document) if per_slide else []
    if not numbers:
        text = _slide_text(document, marks, readings).rstrip()
        quoted = [wording.speaker_notes_block(notes[n]) for n in sorted(notes)]
        return [_with_notes(text, quoted)]
    return [
        _with_notes(
            _slide_text(document, marks, readings, page=number).rstrip(),
            [wording.speaker_notes_block(notes[number])] if number in notes else [],
        )
        for number in numbers
    ]


def _with_notes(text: str, quoted: list[str]) -> str:
    """One page: the slide's text with its quoted notes under it, or nothing at all."""
    parts = [part for part in (text, *quoted) if part]
    return tidy_markdown("\n\n".join(parts)) if parts else ""


def slide_seams(pages: list[str]) -> list[dict]:
    """A paragraph seam between every two pages, for a document whose pages are slides.

    The deterministic rule reads a slide ending without a full stop and the next opening in
    lower case as one sentence cut by the page, and would join them with a space; a slide is
    a unit of its own, so the boundary is settled here and no model is asked.
    """
    return [
        {"page": index, "separator": PARAGRAPH, "drop_head_lines": 0}
        for index in range(2, len(pages) + 1)
    ]


def _slide_text(
    document, marks: dict[str, str], readings: dict[str, str], page: int | None = None
) -> str:
    """One export — the whole document, or one slide — with its pictures' readings spliced in."""
    marked = tidy_markdown(export_markdown(document, marks, page=page), converted=True)
    return tidy_markdown(splice_pictures(marked, readings))

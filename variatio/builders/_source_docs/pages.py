"""Transcribing a document page by page, from the page IMAGE and not from its text.

Docling reads these exercise PDFs as text and loses three things at once: it detaches a code
block from the question that cites it, it collapses the block's line breaks, and it drops
the colour that marks the correct option. All three are visible on a rendered page, so the
image is the honest source for this material.

The unit of work and of caching is the PAGE: a real boundary in the document, one model call
per bounded piece of work, and something small enough for a person to review and fix by hand.

An Office document (`.docx`, `.pptx`) declares its structure and Docling translates it, so
it has no page to render; its PICTURES are the part Docling cannot read, and they take the
same route one at a time — each is one model call under `IMAGE_RULES`, keyed by its own
content hash so the logo repeated on every document is read once for the whole workspace.
"""

import base64
import hashlib
import io
import json
import re
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path

from json_repair import repair_json
from loguru import logger

from ... import config
from ...core import inference, progress
from ...core.json_io import write_json
from ...prompts.marks import EMPTY_IMAGE_MARK, EMPTY_PAGE_MARK, SEAM_SEPARATORS
from . import office
from .files import PLAIN_TEXT_EXTS, SUPPORTED_EXTS, required_cache_dir, source_hash
from .markdown import (
    convert,
    export_markdown,
    page_mark,
    picture_mark,
    pictures,
    splice_pictures,
    tidy_markdown,
)

PAGE_FILE_RE = re.compile(r"^(\d{3})\.md$")
# PDFium is not thread-safe and this process calls it from two threads at once: the job
# thread rendering a page and the request thread counting pages for `/raw`. Interleaved,
# the library's global state corrupts and EVERY later load in the process answers
# «Data format error» until it is restarted. Every PDFium call goes through this lock,
# and the lock is released between pages so a model call never holds it.
_PDFIUM_LOCK = threading.RLock()
META_NAME = "_meta.json"
# Written after every page and removed when `_meta.json` lands: a directory holding one and
# not the other is an interrupted transcription, and nothing reads it as a finished document
# because `read_pages` asks for the meta.
PARTIAL_NAME = "_partial.json"
MD_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", re.DOTALL)

# What `_meta.json` holds beside the fingerprint, and therefore what is NOT compared when
# deciding whether the cached pages are still current.
META_EXTRA = (
    "pages",
    "seams",
    "seams_merged",
    "seams_failed",
    "failed_pages",
    "images_total",
    "images_unreadable",
)

FAILED_PAGE_PREFIX = "> [TRANSCRIPCIÓN FALLIDA"
# Left where a picture stood when nothing could be read off it — a metafile Pillow cannot
# open, or a call that failed after its retries. Visible on purpose, like the failed page:
# a formula that silently vanished from an exercise is worse than one that says it is gone.
UNREADABLE_IMAGE_MARK = "[IMAGEN NO LEGIBLE]"

# Where the transcription of each picture is cached, keyed by the picture's content and
# shared by every document of the workspace: one file per distinct image, so the header
# logo six documents repeat costs one call and not six.
IMAGES_DIR_NAME = "images"
# A picture is upscaled before the call until its longer side reaches this many pixels.
# Measured 2026-09-02 on `gemma-4-31b` over the five readable pictures of the two reference
# banks (188×30 to 1366×768): native and upscaled answered byte for byte the same, so on
# that model it buys nothing and costs a few hundred tokens. It stands for the local
# transcription model, which is unmeasured, and because compositing onto white is needed
# either way — a formula drawn in black on a transparent ground vanishes on a black pad.
IMAGE_MIN_LONG_SIDE = 1024

# The version of `markdown.undo_converter_escapes`, the cleanup applied to Docling's output
# and to nothing else. It is written into the DOCLING fingerprint ONLY: bumping it expires
# the pages that cleanup produced, which is seconds of Docling, while a key in the vlm
# fingerprint would re-transcribe every PDF ever read for a change that never touched them.
CONVERTER_CLEANUP_VERSION = 1


def document_cache_dir(source: str | Path, cache_dir: str | Path) -> Path:
    """Where the pages of one source document are cached."""
    source = Path(source)
    return Path(cache_dir) / source.parent.name / source.name


def _page_path(cache_dir: Path, index: int) -> Path:
    """The file holding page `index`, numbered from one."""
    return cache_dir / f"{index:03d}.md"


def _page_fingerprint(source: Path, mode: str, model: str, dpi: int, ocr: bool) -> dict:
    """Everything that decides what the pages CONTAIN, so that changing any of it expires them.

    The document is identified by its bytes and not by its mtime: a copied or restored
    workspace moves every timestamp and would throw away a whole corpus of transcriptions.
    `TRANSCRIBE_SEAM_CHARS` is deliberately absent — how much of a seam the model is shown
    does not change a single page, and the seam decisions live in `_meta.json` beside them.
    The model and the temperature are recorded on BOTH routes: on the Docling one they are
    what the pictures were read with, and a page carries those readings inline.
    """
    stat = source.stat()
    fingerprint = {
        "source": source.name,
        "source_sha256": source_hash(source),
        "source_bytes": stat.st_size,
        "mode": mode,
        "model": model,
        "dpi": dpi,
        "ocr": ocr,
        "prompt_version": config.TRANSCRIBE_PROMPT_VERSION,
        "temperature": config.TRANSCRIBE_TEMPERATURE,
    }
    if mode == "docling":
        fingerprint["cleanup"] = CONVERTER_CLEANUP_VERSION
        # Whether the metafiles could be rendered: installing LibreOffice has to expire
        # every Office document read without it, or its equations stay unreadable for ever.
        fingerprint["rasteriser"] = Path(office.rasteriser()).name if office.rasteriser() else ""
    return fingerprint


def fingerprint_for(source: Path, model: str, dpi: int, ocr: bool) -> dict:
    """The fingerprint of a document, on the route its extension takes it through."""
    is_pdf = source.suffix.lower() == ".pdf"
    return _page_fingerprint(
        source,
        mode="vlm" if is_pdf else "docling",
        model=model,
        dpi=dpi if is_pdf else 0,
        ocr=False if is_pdf else ocr,
    )


def same_document(stored: dict, fingerprint: dict) -> bool:
    """Say whether cached pages were produced for this exact document and settings.

    Pages written before the fingerprint stopped believing timestamps are adopted rather
    than re-transcribed: everything else about them still matches, and the mtime they
    recorded is exactly the field that cannot be trusted.
    """
    if stored == fingerprint:
        return True
    if "source_sha256" in stored or "source_mtime" not in stored:
        return False
    adopted = {k: v for k, v in stored.items() if k != "source_mtime"}
    return {**adopted, "source_sha256": fingerprint["source_sha256"]} == fingerprint


# What a fingerprint says about the document's LOCATION rather than about its content. Two
# copies of one file under two names, in two slots or in two workspaces, differ here and
# nowhere else, so this is exactly what `reuse_key` drops.
_PLACEMENT_FIELDS = ("source",)


def reuse_key(fingerprint: dict) -> tuple:
    """What identifies a transcription that another document could adopt whole.

    The fingerprint minus the file's NAME: everything left is either the bytes
    (`source_sha256`, `source_bytes`) or the settings the pages were produced under, so two
    documents agreeing on this key would be transcribed into the same pages, one model call
    at a time, for nothing. The name is dropped and not compared because it is the one field
    that says where a copy sits rather than what it holds.
    """
    return tuple(
        sorted(
            (key, _hashable(value))
            for key, value in fingerprint.items()
            if key not in _PLACEMENT_FIELDS
        )
    )


def _hashable(value):
    """Make one fingerprint value usable inside a key; every one of them is already flat."""
    return tuple(sorted(value.items())) if isinstance(value, dict) else value


def adopt_pages(donor_dir: str | Path, cache_dir: str | Path, fingerprint: dict) -> int:
    """Copy a finished transcription onto another document, under its own fingerprint.

    Returns how many pages were written, or 0 when the donor turns out not to hold a
    finished document after all — the caller checked its `_meta.json`, but the pages are
    read back from disk here and the two are separate files.

    The pages are COPIED and not linked: a hand correction on either side must not rewrite
    the other, and a workspace that is later deleted must not take somebody else's
    transcription with it. Only the name in the fingerprint differs from the donor's, so
    what lands is what the model would have written.
    """
    pages = read_pages(donor_dir)
    if not pages:
        return 0
    meta = read_meta(donor_dir)
    write_pages(
        cache_dir,
        pages,
        fingerprint,
        valid_seams(meta.get("seams")),
        {
            "images_total": meta.get("images_total", 0),
            "images_unreadable": meta.get("images_unreadable", 0),
        },
    )
    return len(pages)


def read_meta(cache_dir: str | Path) -> dict:
    """Read `_meta.json`, answering `{}` for anything unreadable."""
    meta_path = Path(cache_dir) / META_NAME
    if not meta_path.exists():
        return {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return meta if isinstance(meta, dict) else {}


def fingerprint_of(meta: dict) -> dict:
    """The fingerprint half of a `_meta.json`, without the counts written beside it."""
    return {k: v for k, v in meta.items() if k not in META_EXTRA}


def read_pages(cache_dir: str | Path) -> list[str]:
    """The cached pages of a finished document, or `[]` when any of them is missing."""
    cache_dir = Path(cache_dir)
    count = read_meta(cache_dir).get("pages")
    if not isinstance(count, int) or count < 1:
        return []
    paths = [_page_path(cache_dir, i) for i in range(1, count + 1)]
    if not all(path.exists() for path in paths):
        return []
    return [path.read_text(encoding="utf-8") for path in paths]


def _read_cached_pages(
    cache_dir: Path, fingerprint: dict
) -> tuple[list[str], list[dict]] | None:
    """The cached `(pages, seams)` when they are current, `None` otherwise."""
    meta = read_meta(cache_dir)
    if not meta:
        return None
    stored = fingerprint_of(meta)
    if not same_document(stored, fingerprint):
        return None

    # Read back rather than returning what was produced: a page a human corrected by hand
    # is the whole point of writing them out, and it must win over what the model said.
    pages = read_pages(cache_dir)
    if not pages:
        return None
    seams = valid_seams(meta.get("seams"))
    if stored != fingerprint:
        write_pages(cache_dir, pages, fingerprint, seams)
    return pages, seams


def _partial_path(cache_dir: Path) -> Path:
    """The marker recording how far an unfinished transcription got."""
    return cache_dir / PARTIAL_NAME


def read_partial(cache_dir: str | Path | None, fingerprint: dict) -> list[str]:
    """The pages an interrupted run of this same document already paid for."""
    if cache_dir is None:
        return []
    cache_dir = Path(cache_dir)
    path = _partial_path(cache_dir)
    if not path.exists():
        return []
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(marker, dict):
        return []
    stored = marker.get("fingerprint")
    done = marker.get("pages_done")
    if not isinstance(stored, dict) or not same_document(stored, fingerprint):
        return []
    if not isinstance(done, int) or done < 1:
        return []
    pages: list[str] = []
    for index in range(1, done + 1):
        page_path = _page_path(cache_dir, index)
        if not page_path.exists():
            break
        pages.append(page_path.read_text(encoding="utf-8"))
    return pages


def save_partial_page(
    cache_dir: str | Path | None, index: int, page: str, fingerprint: dict
) -> None:
    """Write one page and move the partial marker onto it."""
    if cache_dir is None:
        return
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    _page_path(cache_dir, index).write_text(page, encoding="utf-8")
    write_json(_partial_path(cache_dir), {"fingerprint": fingerprint, "pages_done": index})


def write_pages(
    cache_dir: str | Path,
    pages: list[str],
    fingerprint: dict,
    seams: list[dict] | None = None,
    images: dict | None = None,
) -> None:
    """Write a finished document's pages and its `_meta.json`, replacing what was there."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Wipe first: a source that lost pages would otherwise leave the previous run's trailing
    # files behind, and they would be read back as content. The partial marker goes with
    # them — what this function writes is a finished document.
    for stale in cache_dir.iterdir():
        if stale.is_file() and (
            PAGE_FILE_RE.match(stale.name) or stale.name in (META_NAME, PARTIAL_NAME)
        ):
            stale.unlink()
    for index, page in enumerate(pages, 1):
        _page_path(cache_dir, index).write_text(page, encoding="utf-8")
    _write_meta(cache_dir, fingerprint, pages, seams or [], images or {})


def _write_meta(
    cache_dir: Path, fingerprint: dict, pages: list[str], seams: list[dict], images: dict
) -> None:
    """Write `_meta.json`: the fingerprint plus what the screens read off it."""
    write_json(
        cache_dir / META_NAME,
        {
            **fingerprint,
            "pages": len(pages),
            "seams": [dict(record) for record in seams],
            "seams_merged": seams_merged(seams),
            "seams_failed": seams_failed(seams),
            "failed_pages": failed_pages(pages),
            "images_total": int(images.get("images_total", 0)),
            "images_unreadable": int(images.get("images_unreadable", 0)),
        },
    )


def seams_merged(seams) -> int:
    """How many seams were joined as a continuation rather than as a paragraph break."""
    return sum(
        1
        for record in valid_seams(seams)
        if record.get("separator", PARAGRAPH) != PARAGRAPH
    )


def seams_failed(seams) -> list[int]:
    """The pages whose seam the model could not review."""
    return [record["page"] for record in valid_seams(seams) if record.get("failed")]


def failed_pages(pages: list[str]) -> list[int]:
    """The pages that carry the failure marker instead of a transcription."""
    return [
        index
        for index, page in enumerate(pages, 1)
        if page.lstrip().startswith(FAILED_PAGE_PREFIX)
    ]


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


def page_images(pdf_path: Path, dpi: int, first: int = 1) -> tuple[int, Iterator[str]]:
    """`(page_count, generator of base64 PNGs)` — rendered one at a time, not all at once."""
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
        """Yield each page from `first` on as a base64 PNG.

        Each page is rendered whole under the lock — page, bitmap and PNG bytes — and only
        the bytes cross the `yield`, so nothing PDFium owns is touched while the model reads.
        """
        try:
            for index in range(max(first - 1, 0), count):
                with _PDFIUM_LOCK:
                    page = document[index]
                    # Colour is load-bearing: on these exam PDFs the correct option is
                    # marked by nothing but its colour. Never render greyscale to save bytes.
                    bitmap = page.render(scale=dpi / 72)
                    buffer = io.BytesIO()
                    bitmap.to_pil().save(buffer, format="PNG")
                    page.close()
                yield base64.b64encode(buffer.getvalue()).decode()
        finally:
            with _PDFIUM_LOCK:
                document.close()

    return count, render()


def _unwrap_markdown_fence(text: str) -> str:
    """Strip the ```markdown wrapper some models put around a whole page."""
    match = MD_FENCE_RE.match(text.strip())
    return match.group(1) if match else text.strip()


def _transcribe_page(
    image: str, index: int, count: int, model: str, tag: str, prompts
) -> str:
    """Transcribe one page image, retrying, and marking the page when it cannot be read."""
    prompt = prompts.transcribe_page_prompt(index, count)
    last_error: Exception | None = None
    for attempt in range(config.TRANSCRIBE_MAX_RETRIES + 1):
        try:
            response = inference.generate(
                model=model,
                prompt=prompt,
                think=config.THINK_TRANSCRIBE,
                images=[image],
                temperature=config.TRANSCRIBE_TEMPERATURE,
            ).response
            page = _unwrap_markdown_fence(response)
            stripped = page.strip()
            # Tolerant on purpose: models wrap the sentinel in backticks, or add a full
            # stop. Anything that is only the sentinel plus punctuation is an empty page.
            if not stripped or (
                EMPTY_PAGE_MARK in stripped and len(stripped) <= len(EMPTY_PAGE_MARK) + 16
            ):
                return ""
            return page
        except inference.InferenceError as e:
            last_error = e
            logger.warning(f"{tag}page {index}/{count}: transcription failed ({e})")
    logger.error(f"{tag}page {index}/{count}: giving up after the retries ({last_error})")
    # A lost page is lost exercises. Leave a marker a human will trip over in the cached
    # file rather than a silent gap that looks like a page with nothing on it.
    return f"> [TRANSCRIPCIÓN FALLIDA — página {index} de {count}: {last_error}]"


def transcribe_pdf(
    pdf_path: Path,
    model: str,
    dpi: int,
    prompts,
    tag: str = "",
    cache_dir: str | Path | None = None,
    fingerprint: dict | None = None,
) -> list[str]:
    """Transcribe every page of a PDF, resuming from what a previous run already paid for.

    A page costs one model call, so an interrupted run must not throw away its pages: they
    are on disk under the partial marker, and rendering restarts at the tail rather than
    re-rasterising the prefix.
    """
    resume = read_partial(cache_dir, fingerprint) if fingerprint else []
    count, images = page_images(pdf_path, dpi, first=len(resume) + 1)
    pages: list[str] = list(resume[:count])
    logger.info(f"{tag}{pdf_path.name}: transcribing {count} page(s) with '{model}'")
    if pages:
        logger.info(
            f"{tag}{pdf_path.name}: {len(pages)} page(s) already transcribed, "
            f"resuming at {len(pages) + 1}"
        )
    with progress.step(
        "transcribe", f"{pdf_path.name}: transcribiendo páginas", count
    ) as reporter:
        if pages:
            reporter.tick(len(pages), detail=f"página {len(pages)}/{count}")
        for index, image in enumerate(images, len(pages) + 1):
            progress.checkpoint()
            reporter.start(index, detail=f"página {index}/{count}")
            page = _transcribe_page(image, index, count, model, tag, prompts)
            pages.append(page)
            if fingerprint:
                save_partial_page(cache_dir, index, page, fingerprint)
    kept = sum(1 for page in pages if page.strip())
    logger.info(f"{tag}{pdf_path.name}: {kept}/{count} page(s) with content")
    return pages


def _transcribe(
    source: Path,
    is_pdf: bool,
    converter,
    model: str,
    seam_model: str,
    dpi: int,
    tag: str,
    prompts,
    cache_dir: str | Path | None = None,
    fingerprint: dict | None = None,
    images_dir: str | Path | None = None,
) -> tuple[list[str], list[dict], dict]:
    """Produce `(pages, seams, images)` for one document, by route.

    A PDF is rendered and read page by page; an Office file is Docling's, with its pictures
    read one by one and spliced back in; plain text reads as itself.
    """
    if source.suffix.lower() in PLAIN_TEXT_EXTS:
        return [tidy_markdown(source.read_text(encoding="utf-8"))], [], {}
    if not is_pdf:
        page, images = transcribe_office(
            source, converter, model, prompts, tag=tag, images_dir=images_dir
        )
        return [page], [], images
    pages = [
        tidy_markdown(page) if page.strip() else ""
        for page in transcribe_pdf(
            source, model, dpi, prompts, tag=tag, cache_dir=cache_dir, fingerprint=fingerprint
        )
    ]
    return pages, review_seams(pages, prompts, seam_model, tag=tag), {}


def _document(
    source: str | Path,
    prompts,
    converter=None,
    model: str = "",
    dpi: int = 0,
    ocr: bool = False,
    use_cache: bool = True,
    tag: str = "",
    cache_dir: str | Path | None = None,
    seam_model: str = "",
) -> tuple[list[str], list[dict]]:
    """The `(pages, seams)` of a document, from the cache when they are still current."""
    source = Path(source)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_EXTS:
        raise ValueError(f"Unsupported file extension: {suffix}")

    is_pdf = suffix == ".pdf"
    model = model or config.TRANSCRIBE_MODEL
    seam_model = seam_model or config.TRANSCRIBE_SEAM_MODEL
    dpi = dpi or config.TRANSCRIBE_DPI
    fingerprint = fingerprint_for(source, model, dpi, ocr)

    document_dir = (
        document_cache_dir(source, required_cache_dir(cache_dir, "document_pages"))
        if use_cache
        else None
    )
    if use_cache:
        cached = _read_cached_pages(document_dir, fingerprint)
        if cached is not None:
            logger.info(
                f"{tag}{source.name}: {len(cached[0])} page(s) reused from the cache"
            )
            return cached

    pages, seams, images = _transcribe(
        source,
        is_pdf,
        converter,
        model,
        seam_model,
        dpi,
        tag,
        prompts,
        cache_dir=document_dir,
        fingerprint=fingerprint,
        images_dir=Path(cache_dir) / IMAGES_DIR_NAME if use_cache else None,
    )

    if not pages:
        # Caching "nothing" would make the emptiness stick until the source file changes,
        # and an empty document is far more likely to be a transient failure than a fact.
        logger.warning(f"{tag}{source.name}: produced no pages; not cached")
        return pages, seams
    if use_cache:
        write_pages(document_dir, pages, fingerprint, seams, images)
    return pages, seams


def document_pages(
    source: str | Path,
    prompts,
    converter=None,
    model: str = "",
    dpi: int = 0,
    ocr: bool = False,
    use_cache: bool = True,
    tag: str = "",
    cache_dir: str | Path | None = None,
    seam_model: str = "",
) -> list[str]:
    """The document as a list of markdown pages, transcribed from images when it is a PDF.

    Non-PDF sources have no pages to render, so they keep the Docling/plain-text route and
    come back as a single piece — same directory layout, one file inside.
    """
    return _document(
        source,
        prompts,
        converter=converter,
        model=model,
        dpi=dpi,
        ocr=ocr,
        use_cache=use_cache,
        tag=tag,
        cache_dir=cache_dir,
        seam_model=seam_model,
    )[0]


def document_markdown(
    source: str | Path,
    prompts,
    converter=None,
    model: str = "",
    dpi: int = 0,
    ocr: bool = False,
    use_cache: bool = True,
    tag: str = "",
    cache_dir: str | Path | None = None,
    seam_model: str = "",
) -> str:
    """The whole document as one markdown string, stitched page by page.

    The seam decisions travel with the pages in `_meta.json`, so a rebuild reading the cache
    stitches exactly as the run that transcribed it did and pays no model call for it.
    """
    pages, seams = _document(
        source,
        prompts,
        converter=converter,
        model=model,
        dpi=dpi,
        ocr=ocr,
        use_cache=use_cache,
        tag=tag,
        cache_dir=cache_dir,
        seam_model=seam_model,
    )
    return join_pages(pages, seams)


# THE PICTURES OF AN OFFICE DOCUMENT ---------------------------------------------------------------
#
# Docling translates a `.docx` or `.pptx` faithfully — it declares its structure, so there is
# nothing to infer — and writes `<!-- image -->` for every picture, which is exactly the part
# of these documents that carries the formulas and the expected outputs. Each picture is one
# model call under the same rules a figure on a rendered page gets, and the answer is put
# back where the picture stood.


def transcribe_office(
    source: Path,
    converter,
    model: str,
    prompts,
    tag: str = "",
    images_dir: str | Path | None = None,
) -> tuple[str, dict]:
    """Convert an Office document with Docling and read its pictures, one call each.

    Returns the page and a tally: how many pictures the body carried, and how many left the
    unreadable mark.
    """
    # The metafiles are rendered into a copy that Docling reads in the original's place;
    # the copy lives as long as the conversion and nothing keys on it.
    with tempfile.TemporaryDirectory(prefix="variatio-office-") as workdir:
        prepared = office.rasterised_copy(source, workdir) or source
        document = convert(converter, prepared)
    found = pictures(document)
    tally = {"images_total": len(found), "images_unreadable": 0}
    text = tidy_markdown(export_markdown(document, {}), converted=True)
    if not found:
        return text, tally

    logger.info(f"{tag}{source.name}: {len(found)} picture(s) to read with '{model}'")
    readings: dict[str, str] = {}
    memo: dict[str, str] = {}
    reused = 0
    with progress.step(
        "transcribe_image", f"{source.name}: transcribiendo imágenes", len(found)
    ) as reporter:
        for index, (ref, image) in enumerate(found, 1):
            progress.checkpoint()
            reporter.start(index, detail=f"imagen {index}/{len(found)}")
            if image is None:
                readings[ref] = UNREADABLE_IMAGE_MARK
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
                    readings[ref] = UNREADABLE_IMAGE_MARK
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
    # Tidied with the marks still standing and the readings spliced in afterwards: the
    # escape undo exists for Docling's output and must never touch what the model wrote.
    marked = tidy_markdown(
        export_markdown(document, {ref: picture_mark(ref) for ref, _ in found}),
        converted=True,
    )
    return tidy_markdown(splice_pictures(marked, readings)), tally


def _encode_image(image) -> bytes:
    """Return the picture as PNG bytes, on white and no smaller than the model can read.

    Transparency is composited onto white: a formula drawn in black on a transparent ground
    is invisible on the black a preprocessor pads with. A small picture is upscaled by a
    whole factor until its longer side reaches `IMAGE_MIN_LONG_SIDE`.
    """
    from PIL import Image

    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    elif image.mode != "RGB":
        image = image.convert("RGB")
    longest = max(image.size)
    if 0 < longest < IMAGE_MIN_LONG_SIDE:
        factor = -(-IMAGE_MIN_LONG_SIDE // longest)
        image = image.resize(
            (image.width * factor, image.height * factor), Image.Resampling.LANCZOS
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _image_record_path(images_dir: Path, digest: str) -> Path:
    """The file holding one picture's reading, named by the picture's content."""
    return images_dir / f"{digest}.json"


def _read_image_cache(images_dir: str | Path | None, digest: str, model: str) -> str | None:
    """The cached reading of a picture, when it was made under the same model and prompt."""
    if images_dir is None:
        return None
    path = _image_record_path(Path(images_dir), digest)
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(record, dict) or not isinstance(record.get("text"), str):
        return None
    if (
        record.get("model") != model
        or record.get("prompt_version") != config.TRANSCRIBE_PROMPT_VERSION
        or record.get("temperature") != config.TRANSCRIBE_TEMPERATURE
    ):
        return None
    return record["text"]


def _write_image_cache(
    images_dir: str | Path | None, digest: str, model: str, text: str
) -> None:
    """Record one picture's reading beside what it was read with."""
    if images_dir is None:
        return
    write_json(
        _image_record_path(Path(images_dir), digest),
        {
            "sha256": digest,
            "model": model,
            "prompt_version": config.TRANSCRIBE_PROMPT_VERSION,
            "temperature": config.TRANSCRIBE_TEMPERATURE,
            "text": text,
        },
    )


def _transcribe_image(
    image: str, index: int, count: int, model: str, tag: str, prompts
) -> str | None:
    """Read one picture, retrying; `""` for one with nothing on it, `None` when it failed."""
    prompt = prompts.transcribe_image_prompt(index, count)
    last_error: Exception | None = None
    for attempt in range(config.TRANSCRIBE_MAX_RETRIES + 1):
        try:
            response = inference.generate(
                model=model,
                prompt=prompt,
                think=config.THINK_TRANSCRIBE_IMAGE,
                images=[image],
                temperature=config.TRANSCRIBE_TEMPERATURE,
            ).response
            reading = _unwrap_markdown_fence(response)
            stripped = reading.strip()
            if not stripped or (
                EMPTY_IMAGE_MARK in stripped and len(stripped) <= len(EMPTY_IMAGE_MARK) + 16
            ):
                return ""
            return stripped
        except inference.InferenceError as e:
            last_error = e
            logger.warning(f"{tag}picture {index}/{count}: transcription failed ({e})")
    logger.error(f"{tag}picture {index}/{count}: giving up after the retries ({last_error})")
    return None


# THE SEAM BETWEEN TWO PAGES ----------------------------------------------------------------------
#
# A page break is a fact about the paper and not about the text, so what has to be decided
# per seam is how much of a break it really is: joining every pair with a paragraph break
# cuts an exercise that spans two pages in half, closes a code fence in the middle of the
# block and loses the second half of a table.

SEPARATORS = {"none": "", "space": " ", "newline": "\n", "paragraph": "\n\n"}
PARAGRAPH = "paragraph"
NEWLINE = "newline"
SPACE = "space"

# A cap, not a knob: beyond a handful of lines the answer stops being «a repeated header»
# and starts being «a page I decided to drop», and losing content is the one failure this
# whole route exists to avoid.
MAX_SEAM_DROP_LINES = 3

_FENCE_LINE_RE = re.compile(r"^\s*```")
_HEADING_LINE_RE = re.compile(r"^\s{0,3}#{1,6}\s")
_BULLET_LINE_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_DIVIDER_RE = re.compile(r"^\s*\|(?:\s*:?-{2,}:?\s*\|)+\s*$")
_SENTENCE_END_RE = re.compile(r"[.!?:;…]['\"»”)\]]*$")
_CONTINUATION_HEADS = ",;:)]}»…"


def seam(left: str, right: str) -> tuple[str, bool]:
    """`(separator key, certain)` for the boundary between two consecutive pages."""
    if not left.strip() or not right.strip():
        return PARAGRAPH, True
    # An unbalanced fence is the one case that needs no judgement: the block is open, so the
    # next page is inside it whatever it looks like.
    if fence_is_open(left):
        return NEWLINE, True
    tail, head = _last_line(left), _first_line(right)
    if (
        _TABLE_ROW_RE.match(tail)
        and _TABLE_ROW_RE.match(head)
        and not _TABLE_DIVIDER_RE.match(head)
    ):
        return NEWLINE, False
    if _continues_sentence(tail, head):
        return SPACE, False
    return PARAGRAPH, False


def fence_is_open(text: str) -> bool:
    """Say whether the text ends inside a code fence."""
    return sum(1 for line in text.splitlines() if _FENCE_LINE_RE.match(line)) % 2 == 1


def _continues_sentence(tail: str, head: str) -> bool:
    """Say whether the second page's first line carries on the first page's last one."""
    if _HEADING_LINE_RE.match(tail) or _BULLET_LINE_RE.match(tail):
        return False
    if _TABLE_ROW_RE.match(tail) or _FENCE_LINE_RE.match(tail):
        return False
    if _SENTENCE_END_RE.search(tail.rstrip()):
        return False
    if _HEADING_LINE_RE.match(head) or _BULLET_LINE_RE.match(head):
        return False
    if _TABLE_ROW_RE.match(head) or _FENCE_LINE_RE.match(head):
        return False
    first = head.lstrip()[:1]
    return bool(first) and (first.islower() or first in _CONTINUATION_HEADS)


def _last_line(text: str) -> str:
    """The last line with anything on it."""
    return next((line for line in reversed(text.splitlines()) if line.strip()), "")


def _first_line(text: str) -> str:
    """The first line with anything on it."""
    return next((line for line in text.splitlines() if line.strip()), "")


def _trim(text: str) -> str:
    """Drop leading and trailing blank LINES, keeping the indentation of what survives.

    `strip()` would take the indentation of the first surviving line with them, and a page
    that continues a code block starts indented — flattening it is the corruption the whole
    page-image route exists to avoid.
    """
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _drop_lines(text: str, count: int) -> str:
    """Remove the first `count` non-blank lines of a page."""
    if count <= 0:
        return text
    lines = text.splitlines()
    dropped, index = 0, 0
    while index < len(lines) and dropped < count:
        if lines[index].strip():
            dropped += 1
        index += 1
    return _trim("\n".join(lines[index:]))


def _drop_reopened_fence(text: str) -> str:
    """Remove an opening fence a page repeated for a code block that is already open."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if _FENCE_LINE_RE.match(line):
            return _trim("\n".join(lines[:index] + lines[index + 1 :]))
        return text
    return text


def _drop_repeated_header(text: str) -> str:
    """Remove the header row and divider a page repeated for a table that continues."""
    lines = text.splitlines()
    body = [index for index, line in enumerate(lines) if line.strip()]
    if len(body) < 2:
        return text
    first, second = body[0], body[1]
    if _TABLE_ROW_RE.match(lines[first]) and _TABLE_DIVIDER_RE.match(lines[second]):
        return _trim("\n".join(lines[:first] + lines[second + 1 :]))
    return text


def _clamp_drop(value) -> int:
    """Read the model's line count as an integer within the cap, `0` for anything else."""
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_SEAM_DROP_LINES))


def valid_seams(records) -> list[dict]:
    """Keep the stored seam records that at least name the page they belong to."""
    if not isinstance(records, list):
        return []
    out = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("page"), int):
            continue
        out.append(record)
    return out


def join_pages(pages: list[str], seams: list[dict] | None = None) -> str:
    """The pages as one markdown document, each seam closed as tightly as it deserves."""
    decided = {record["page"]: record for record in valid_seams(seams)}
    out = ""
    for index, page in enumerate(pages, 1):
        body = _trim(page)
        if not body:
            continue
        if not out:
            out = body
            continue
        separator, certain = seam(out, body)
        record = decided.get(index)
        if record is not None and not certain:
            if record.get("separator") in SEPARATORS:
                separator = str(record["separator"])
            body = _drop_lines(body, _clamp_drop(record.get("drop_head_lines")))
        if separator == NEWLINE:
            body = (
                _drop_reopened_fence(body)
                if fence_is_open(out)
                else _drop_repeated_header(body)
            )
        if not body.strip():
            continue
        if separator == PARAGRAPH:
            out = f"{out}\n\n{page_mark(index)}\n\n{body}"
        else:
            out = f"{out}{SEPARATORS[separator]}{body}"
    return out


# THE SEAM, REVIEWED BY THE MODEL ------------------------------------------------------------------
#
# The model CLASSIFIES a seam and never rewrites a character: the transcription prompt is
# built on «copy character by character», and a second model allowed to redraft would undo
# it. All it may say is how the two pages are glued and how many of the second one's opening
# lines are repeated layout.

SEAM_SCHEMA = {
    "type": "object",
    "properties": {
        "continues": {"type": "boolean"},
        "separator": {"type": "string", "enum": list(SEAM_SEPARATORS)},
        "drop_head_lines": {"type": "integer"},
        "reason": {"type": "string"},
    },
    "required": ["continues", "separator", "drop_head_lines"],
}


def review_seams(pages: list[str], prompts, model: str = "", tag: str = "") -> list[dict]:
    """Ask the model about every seam the deterministic rule could not settle."""
    model = model or config.TRANSCRIBE_SEAM_MODEL
    boundaries = _boundaries(pages)
    if not boundaries:
        return []
    records: list[dict] = []
    with progress.step(
        "transcribe_seam", "Revisando las costuras entre páginas", len(boundaries)
    ) as reporter:
        for done, (left, right, index) in enumerate(boundaries, 1):
            progress.checkpoint()
            reporter.start(done, detail=f"costura {index - 1}→{index}")
            record = _review_seam(left, right, index, len(pages), model, tag, prompts)
            if record is not None:
                records.append(record)
    merged = sum(1 for record in records if record.get("separator", PARAGRAPH) != PARAGRAPH)
    if records:
        logger.info(f"{tag}{merged}/{len(boundaries)} seam(s) joined as a continuation")
    return records


def _boundaries(pages: list[str]) -> list[tuple[str, str, int]]:
    """The `(left, right, index)` seams between consecutive pages that have content."""
    out: list[tuple[str, str, int]] = []
    previous: str | None = None
    for index, page in enumerate(pages, 1):
        if not page.strip():
            continue
        if previous is not None:
            out.append((previous, page, index))
        previous = page
    return out


def _review_seam(
    left: str, right: str, index: int, count: int, model: str, tag: str, prompts
) -> dict | None:
    """Have the model classify one uncertain seam, failing open onto the rule.

    An engine that raises and an unreadable answer both record the seam as failed and leave
    the deterministic separator in place: one seam is never a reason to throw away a
    forty-page transcription.
    """
    if seam(left, right)[1]:
        return None
    tail = left.strip()[-config.TRANSCRIBE_SEAM_CHARS :]
    head = right.strip()[: config.TRANSCRIBE_SEAM_CHARS]
    if not tail or not head:
        return None
    try:
        response = inference.generate(
            model=model,
            prompt=prompts.merge_pages_prompt(tail, head, index, count),
            think=config.THINK_TRANSCRIBE_SEAM,
            format=None if config.THINK_TRANSCRIBE_SEAM else SEAM_SCHEMA,
            temperature=inference.judgement_temperature(config.THINK_TRANSCRIBE_SEAM),
        ).response
    except inference.InferenceError as e:
        logger.warning(f"{tag}seam {index - 1}→{index}: not reviewed ({e}); joined by rule")
        return {"page": index, "failed": True}
    parsed = _parse_seam(response)
    if parsed is None:
        logger.warning(
            f"{tag}seam {index - 1}→{index}: unreadable answer; joined by rule"
        )
        return {"page": index, "failed": True}
    return {"page": index, **parsed}


def _parse_seam(response: str) -> dict | None:
    """Read the seam answer, keeping only a separator the catalogue actually holds."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response.strip())
    try:
        raw = repair_json(cleaned, return_objects=True)
    except (ValueError, TypeError):
        return None
    if not isinstance(raw, dict) or raw.get("separator") not in SEAM_SEPARATORS:
        return None
    return {
        "separator": str(raw["separator"]),
        "drop_head_lines": _clamp_drop(raw.get("drop_head_lines")),
    }

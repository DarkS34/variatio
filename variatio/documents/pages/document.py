"""Reading a whole document: the cached pages when they are current, the failed ones again,
and the transcription of what is missing.
"""

from pathlib import Path

from loguru import logger

from ... import config
from ...core import progress
from ..files import PLAIN_TEXT_EXTS, SUPPORTED_EXTS, required_cache_dir
from ..markdown import tidy_markdown
from .cache import (
    document_cache_dir,
    failed_pages,
    fingerprint_for,
    fingerprint_of,
    looped_pages,
    read_meta,
    read_pages,
    read_partial,
    same_document,
    save_partial_page,
    write_pages,
)
from .images import IMAGES_DIR_NAME
from .office_pages import slide_seams, transcribe_office
from .render import page_count, page_images
from .seams import join_pages, review_seams, valid_seams
from .transcribe import _transcribe_page


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

    A `.docx` and a plain-text file have no pages to render, so they keep the Docling and
    plain-text routes and come back as a single piece — same directory layout, one file
    inside. A `.pptx` comes back as one page PER SLIDE, in the deck's own order.
    """
    return _read_document(
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
    pages, seams = _read_document(
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


def _read_document(
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
            retry = retryable_pages(source, document_dir, cached[0]) if is_pdf else []
            if not retry:
                logger.info(
                    f"{tag}{source.name}: {len(cached[0])} page(s) reused from the cache"
                )
                return cached
            return _read_failed_pages_again(
                source,
                cached,
                retry,
                document_dir,
                fingerprint,
                model,
                seam_model,
                dpi,
                tag,
                prompts,
            )

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


def retryable_pages(source: Path, cache_dir: str | Path, pages: list[str]) -> list[int]:
    """The failed pages of a finished PDF that its next read tries again, counted from 1.

    A failed page is work not done, and a later run is not the second attempt
    `_ask_twice` already made: that one asks again a second later under a prompt naming
    the loop, while this one comes after somebody pressed the button again — the output cap
    was raised, the endpoint stopped refusing the picture, or the runaway simply did not
    happen this time (measured at temperature 0 on Cerebras: it is not deterministic).

    A page whose cached text is a repetition loop the model stopped on its own is read
    again too (`looped_pages`): it was cached as a page with content, and it is not one.

    Nothing is retried once pages were inserted or deleted by hand: that renumbers every page
    after the edit, page N of the cache stops being page N of the PDF, and re-reading "the
    failed page 5" would write another page's text into it. Such a document keeps its markers
    for a person to correct, and so does one whose page count no longer matches the file's.
    The PDF is opened only when there is something to retry.
    """
    candidates = sorted({*failed_pages(pages), *looped_pages(pages)})
    if not candidates or read_meta(cache_dir).get("restructured"):
        return []
    if page_count(source) != len(pages):
        return []
    return candidates


def _read_failed_pages_again(
    source: Path,
    cached: tuple[list[str], list[dict]],
    numbers: list[int],
    cache_dir: Path,
    fingerprint: dict,
    model: str,
    seam_model: str,
    dpi: int,
    tag: str,
    prompts,
) -> tuple[list[str], list[dict]]:
    """Transcribe the failed pages again and keep every other page exactly as it is.

    Each page is written the moment it comes back, with the two seam records around it
    dropped — they were decided against the failure marker — so a cancelled run keeps what
    it paid for; the seams around the new pages are reviewed once all of them are in.
    """
    pages, seams = list(cached[0]), valid_seams(cached[1])
    count, images = page_images(source, dpi, numbers=numbers)
    logger.info(
        f"{tag}{source.name}: reading {len(numbers)} page(s) that failed or looped last "
        f"time with '{model}'"
    )
    touched: set[int] = set()
    with progress.step(
        "transcribe", f"{source.name}: reading the failed pages again", len(numbers)
    ) as reporter:
        for done, (number, image) in enumerate(zip(numbers, images), 1):
            progress.checkpoint()
            reporter.start(done, detail=f"page {number}/{count}")
            page = _transcribe_page(image, number, count, model, tag, prompts)
            pages[number - 1] = tidy_markdown(page) if page.strip() else ""
            touched.update((number, number + 1))
            seams = [record for record in seams if record["page"] not in touched]
            write_pages(cache_dir, pages, fingerprint, seams)
    reviewed = review_seams(pages, prompts, seam_model, tag=tag, only=touched)
    seams = sorted([*seams, *reviewed], key=lambda record: record["page"])
    write_pages(cache_dir, pages, fingerprint, seams)
    logger.info(
        f"{tag}{source.name}: {len(numbers) - len(failed_pages(pages))}/{len(numbers)} "
        "failed page(s) read this time"
    )
    return pages, seams


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
    read one by one and spliced back in, a deck one page per slide; plain text reads as
    itself.
    """
    if source.suffix.lower() in PLAIN_TEXT_EXTS:
        return [tidy_markdown(source.read_text(encoding="utf-8"))], [], {}
    if not is_pdf:
        pages, images = transcribe_office(
            source, converter, model, prompts, tag=tag, images_dir=images_dir
        )
        return pages, slide_seams(pages), images
    pages = [
        tidy_markdown(page) if page.strip() else ""
        for page in transcribe_pdf(
            source, model, dpi, prompts, tag=tag, cache_dir=cache_dir, fingerprint=fingerprint
        )
    ]
    return pages, review_seams(pages, prompts, seam_model, tag=tag), {}


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
        "transcribe", f"{pdf_path.name}: reading pages", count
    ) as reporter:
        if pages:
            reporter.tick(len(pages), detail=f"page {len(pages)}/{count}")
        for index, image in enumerate(images, len(pages) + 1):
            progress.checkpoint()
            reporter.start(index, detail=f"page {index}/{count}")
            page = _transcribe_page(image, index, count, model, tag, prompts)
            pages.append(page)
            if fingerprint:
                save_partial_page(cache_dir, index, page, fingerprint)
    kept = sum(1 for page in pages if page.strip())
    logger.info(f"{tag}{pdf_path.name}: {kept}/{count} page(s) with content")
    return pages

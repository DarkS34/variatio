import base64
import io
import json
import re
from collections.abc import Iterator
from pathlib import Path

from loguru import logger

from ... import config
from ...core import inference, progress
from ...prompts import EMPTY_PAGE_MARK, transcribe_page_prompt
from .files import SUPPORTED_EXTS, required_cache_dir
from .markdown import tidy_markdown, to_markdown

# Docling reads these exercise PDFs as text and loses three things at once: it detaches a
# code block from the question that cites it, it collapses the block's line breaks, and it
# drops the colour that marks the correct option. All three are visible on a rendered page,
# so the page image — not the extracted text — is the honest source for this material.
#
# The unit of work and of caching is the PAGE: it is a real boundary in the document, it
# keeps one model call to one bounded piece of work, and it gives a human something small
# enough to actually review and fix by hand.

PAGE_FILE_RE = re.compile(r"^(\d{3})\.md$")
META_NAME = "_meta.json"
MD_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", re.DOTALL)


def document_cache_dir(source: str | Path, cache_dir: str | Path) -> Path:
    source = Path(source)
    return Path(cache_dir) / source.parent.name / source.name


def _page_path(cache_dir: Path, index: int) -> Path:
    return cache_dir / f"{index:03d}.md"


# Everything that decides what the pages CONTAIN, so that changing any of it invalidates
# them. Timestamps alone cannot see a new model, a new DPI or an edited prompt.
def _page_fingerprint(source: Path, mode: str, model: str, dpi: int, ocr: bool) -> dict:
    stat = source.stat()
    return {
        "source": source.name,
        "source_mtime": round(stat.st_mtime, 3),
        "source_bytes": stat.st_size,
        "mode": mode,
        "model": model,
        "dpi": dpi,
        "ocr": ocr,
        "prompt_version": config.TRANSCRIBE_PROMPT_VERSION,
        "temperature": config.TRANSCRIBE_TEMPERATURE if mode == "vlm" else None,
    }


def _fingerprint_for(source: Path, model: str, dpi: int, ocr: bool) -> dict:
    is_pdf = source.suffix.lower() == ".pdf"
    return _page_fingerprint(
        source,
        mode="vlm" if is_pdf else "docling",
        model=model if is_pdf else "",
        dpi=dpi if is_pdf else 0,
        ocr=False if is_pdf else ocr,
    )


def _read_cached_pages(cache_dir: Path, fingerprint: dict) -> list[str] | None:
    meta_path = cache_dir / META_NAME
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if {k: v for k, v in meta.items() if k != "pages"} != fingerprint:
        return None

    count = meta.get("pages")
    if not isinstance(count, int) or count < 1:
        return None
    paths = [_page_path(cache_dir, i) for i in range(1, count + 1)]
    if not all(path.exists() for path in paths):
        return None
    # Read back rather than returning what was produced: a page a human corrected by hand
    # is the whole point of writing them out, and it must win over what the model said.
    return [path.read_text(encoding="utf-8") for path in paths]


def _write_pages(cache_dir: Path, pages: list[str], fingerprint: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Wipe first: a source that lost pages would otherwise leave the previous run's
    # trailing files behind, and they would be read back as content.
    for stale in cache_dir.iterdir():
        if stale.is_file() and (PAGE_FILE_RE.match(stale.name) or stale.name == META_NAME):
            stale.unlink()
    for index, page in enumerate(pages, 1):
        _page_path(cache_dir, index).write_text(page, encoding="utf-8")
    (cache_dir / META_NAME).write_text(
        json.dumps({**fingerprint, "pages": len(pages)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def page_images(pdf_path: Path, dpi: int) -> tuple[int, Iterator[str]]:
    """`(page_count, generator of base64 PNGs)` — rendered one at a time, not all at once."""
    try:
        import pypdfium2 as pdfium
    except ImportError as e:
        raise ImportError(
            "Rendering PDF pages needs pypdfium2, which ships with the builders extra. "
            "Install it with: uv sync --extra builders"
        ) from e

    document = pdfium.PdfDocument(str(pdf_path))
    count = len(document)

    def render():
        for index in range(count):
            # Colour is load-bearing: on these exam PDFs the correct option is marked by
            # nothing but its colour. Never render these greyscale to save bytes.
            bitmap = document[index].render(scale=dpi / 72)
            buffer = io.BytesIO()
            bitmap.to_pil().save(buffer, format="PNG")
            yield base64.b64encode(buffer.getvalue()).decode()

    return count, render()


def _unwrap_markdown_fence(text: str) -> str:
    match = MD_FENCE_RE.match(text.strip())
    return match.group(1) if match else text.strip()


def _transcribe_page(image: str, index: int, count: int, model: str, tag: str) -> str:
    prompt = transcribe_page_prompt(index, count)
    last_error: Exception | None = None
    for attempt in range(config.TRANSCRIBE_MAX_RETRIES + 1):
        try:
            response = inference.generate(
                model=model,
                prompt=prompt,
                think=config.THINK_EXEMPLARS_TRANSCRIBE,
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
            logger.warning(f"{tag}página {index}/{count}: falló la transcripción ({e})")
    logger.error(f"{tag}página {index}/{count}: se abandona tras los reintentos ({last_error})")
    # A lost page is lost exercises. Leave a marker a human will trip over in the cached
    # file rather than a silent gap that looks like a page with nothing on it.
    return f"> [TRANSCRIPCIÓN FALLIDA — página {index} de {count}: {last_error}]"


def transcribe_pdf(pdf_path: Path, model: str, dpi: int, tag: str = "") -> list[str]:
    count, images = page_images(pdf_path, dpi)
    logger.info(f"{tag}{pdf_path.name}: transcribiendo {count} página(s) con '{model}'")
    pages: list[str] = []
    with progress.step(
        "transcribe", f"{pdf_path.name}: transcribiendo páginas", count
    ) as reporter:
        for index, image in enumerate(images, 1):
            progress.checkpoint()
            reporter.tick(index, detail=f"página {index}/{count}")
            pages.append(_transcribe_page(image, index, count, model, tag))
    kept = sum(1 for page in pages if page.strip())
    logger.info(f"{tag}{pdf_path.name}: {kept}/{count} página(s) con contenido")
    return pages


def document_pages(
    source: str | Path,
    converter=None,
    model: str = "",
    dpi: int = 0,
    ocr: bool = False,
    use_cache: bool = True,
    tag: str = "",
    cache_dir: str | Path | None = None,
) -> list[str]:
    """The document as a list of markdown pages, transcribed from images when it is a PDF.

    Non-PDF sources have no pages to render, so they keep the Docling/plain-text route and
    come back as a single piece — same directory layout, one file inside.
    """
    source = Path(source)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_EXTS:
        raise ValueError(f"Unsupported file extension: {suffix}")

    is_pdf = suffix == ".pdf"
    model = model or config.EXEMPLARS_TRANSCRIBE_MODEL
    dpi = dpi or config.TRANSCRIBE_DPI
    fingerprint = _fingerprint_for(source, model, dpi, ocr)

    document_dir = (
        document_cache_dir(source, required_cache_dir(cache_dir, "document_pages"))
        if use_cache
        else None
    )
    if use_cache:
        cached = _read_cached_pages(document_dir, fingerprint)
        if cached is not None:
            logger.info(f"{tag}{source.name}: {len(cached)} página(s) reutilizadas de la caché")
            return cached

    if is_pdf:
        pages = [tidy_markdown(page) if page.strip() else "" for page in
                 transcribe_pdf(source, model, dpi, tag=tag)]
    else:
        pages = [to_markdown(converter, source, use_cache=False)]

    if not pages:
        # Caching "nothing" would make the emptiness stick until the source file changes,
        # and an empty document is far more likely to be a transient failure than a fact.
        logger.warning(f"{tag}{source.name}: no produjo páginas; no se guarda en caché")
        return pages
    if use_cache:
        _write_pages(document_dir, pages, fingerprint)
    return pages


def join_pages(pages: list[str]) -> str:
    return "\n\n".join(page.strip() for page in pages if page.strip())

import base64
import io
import json
import re
from collections.abc import Iterator
from pathlib import Path

from json_repair import repair_json
from loguru import logger

from ... import config
from ...core import inference, progress
from ...core.json_io import write_json
from ...prompts.marks import EMPTY_PAGE_MARK, SEAM_SEPARATORS
from .files import SUPPORTED_EXTS, required_cache_dir, source_hash
from .markdown import page_mark, tidy_markdown, to_markdown

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
# Written after every page, removed when `_meta.json` lands. A directory that has one and
# not the other is a transcription that was interrupted: the pages in it are real, and
# nothing reads them as a finished document because `read_pages` asks for the meta.
PARTIAL_NAME = "_partial.json"
MD_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*)\n```\s*$", re.DOTALL)

# What `_meta.json` holds beside the fingerprint, and therefore what is NOT compared when
# deciding whether the cached pages are still current.
META_EXTRA = ("pages", "seams", "seams_merged", "seams_failed", "failed_pages")

FAILED_PAGE_PREFIX = "> [TRANSCRIPCIÓN FALLIDA"

# The version of `markdown.undo_converter_escapes`, the cleanup applied to Docling's output
# and to nothing else. Bumping it expires the pages that cleanup produced, because what is
# on disk is no longer what the converter says — and re-running Docling over a `.docx` is
# seconds and not one model call. It is written into the DOCLING fingerprint only: adding a
# key to the vlm one would expire every PDF ever transcribed, which is hours of model time
# for a change that never touched them.
CONVERTER_CLEANUP_VERSION = 1


def document_cache_dir(source: str | Path, cache_dir: str | Path) -> Path:
    source = Path(source)
    return Path(cache_dir) / source.parent.name / source.name


def _page_path(cache_dir: Path, index: int) -> Path:
    return cache_dir / f"{index:03d}.md"


# Everything that decides what the pages CONTAIN, so that changing any of it invalidates
# them: the document itself cannot see a new model, a new DPI or an edited prompt. The
# document is identified by its bytes and not by its mtime — a copied or restored workspace
# moves every timestamp and would throw away a whole corpus of transcriptions.
def _page_fingerprint(source: Path, mode: str, model: str, dpi: int, ocr: bool) -> dict:
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
        "temperature": config.TRANSCRIBE_TEMPERATURE if mode == "vlm" else None,
    }
    if mode == "docling":
        fingerprint["cleanup"] = CONVERTER_CLEANUP_VERSION
    return fingerprint


def fingerprint_for(source: Path, model: str, dpi: int, ocr: bool) -> dict:
    is_pdf = source.suffix.lower() == ".pdf"
    return _page_fingerprint(
        source,
        mode="vlm" if is_pdf else "docling",
        model=model if is_pdf else "",
        dpi=dpi if is_pdf else 0,
        ocr=False if is_pdf else ocr,
    )


# Pages written before the fingerprint stopped believing timestamps are adopted instead of
# re-transcribed: everything else about them still matches, and the mtime they recorded is
# exactly the field that cannot be trusted.
def same_document(stored: dict, fingerprint: dict) -> bool:
    if stored == fingerprint:
        return True
    if "source_sha256" in stored or "source_mtime" not in stored:
        return False
    adopted = {k: v for k, v in stored.items() if k != "source_mtime"}
    return {**adopted, "source_sha256": fingerprint["source_sha256"]} == fingerprint


def read_meta(cache_dir: str | Path) -> dict:
    meta_path = Path(cache_dir) / META_NAME
    if not meta_path.exists():
        return {}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return meta if isinstance(meta, dict) else {}


def fingerprint_of(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if k not in META_EXTRA}


def read_pages(cache_dir: str | Path) -> list[str]:
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
    return cache_dir / PARTIAL_NAME


def read_partial(cache_dir: str | Path | None, fingerprint: dict) -> list[str]:
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
) -> None:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Wipe first: a source that lost pages would otherwise leave the previous run's
    # trailing files behind, and they would be read back as content. The partial marker
    # goes with them — what this function writes is a finished document.
    for stale in cache_dir.iterdir():
        if stale.is_file() and (
            PAGE_FILE_RE.match(stale.name) or stale.name in (META_NAME, PARTIAL_NAME)
        ):
            stale.unlink()
    for index, page in enumerate(pages, 1):
        _page_path(cache_dir, index).write_text(page, encoding="utf-8")
    _write_meta(cache_dir, fingerprint, pages, seams or [])


def _write_meta(
    cache_dir: Path, fingerprint: dict, pages: list[str], seams: list[dict]
) -> None:
    write_json(
        cache_dir / META_NAME,
        {
            **fingerprint,
            "pages": len(pages),
            "seams": [dict(record) for record in seams],
            "seams_merged": seams_merged(seams),
            "seams_failed": seams_failed(seams),
            "failed_pages": failed_pages(pages),
        },
    )


def seams_merged(seams) -> int:
    return sum(
        1
        for record in valid_seams(seams)
        if record.get("separator", PARAGRAPH) != PARAGRAPH
    )


def seams_failed(seams) -> list[int]:
    return [record["page"] for record in valid_seams(seams) if record.get("failed")]


def failed_pages(pages: list[str]) -> list[int]:
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
        return len(pdfium.PdfDocument(str(pdf_path)))
    except Exception:
        return 0


def page_images(pdf_path: Path, dpi: int, first: int = 1) -> tuple[int, Iterator[str]]:
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
        for index in range(max(first - 1, 0), count):
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


def _transcribe_page(
    image: str, index: int, count: int, model: str, tag: str, prompts
) -> str:
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
    # A page costs one model call, so an interrupted run must not throw away the ones it
    # already paid for. They are on disk under the partial marker; what is left is the
    # tail, and `page_images` renders from there rather than re-rasterising the prefix.
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
            reporter.tick(index, detail=f"página {index}/{count}")
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
) -> tuple[list[str], list[dict]]:
    if not is_pdf:
        return [to_markdown(converter, source, use_cache=False)], []
    pages = [
        tidy_markdown(page) if page.strip() else ""
        for page in transcribe_pdf(
            source, model, dpi, prompts, tag=tag, cache_dir=cache_dir, fingerprint=fingerprint
        )
    ]
    return pages, review_seams(pages, prompts, seam_model, tag=tag)


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

    pages, seams = _transcribe(
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
    )

    if not pages:
        # Caching "nothing" would make the emptiness stick until the source file changes,
        # and an empty document is far more likely to be a transient failure than a fact.
        logger.warning(f"{tag}{source.name}: produced no pages; not cached")
        return pages, seams
    if use_cache:
        write_pages(document_dir, pages, fingerprint, seams)
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


# THE SEAM BETWEEN TWO PAGES ----------------------------------------------------------------------
#
# `"\n\n".join(...)` put a PARAGRAPH break between page N and page N+1 whatever fell there,
# so an exercise spanning two pages arrived at the extractor cut in half, a code block came
# back with its fence closed in the middle and a table lost its second half. The page break
# is a fact about the paper, not about the text: what has to be decided per seam is how much
# of a break it really is.

SEPARATORS = {"none": "", "space": " ", "newline": "\n", "paragraph": "\n\n"}
PARAGRAPH = "paragraph"
NEWLINE = "newline"
SPACE = "space"

# A cap, not a knob: the model is asked how many head lines are layout rather than content,
# and beyond a handful the answer stops being «a repeated header» and starts being «a page
# I decided to drop». Losing content is the one failure this whole route exists to avoid.
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
    return sum(1 for line in text.splitlines() if _FENCE_LINE_RE.match(line)) % 2 == 1


def _continues_sentence(tail: str, head: str) -> bool:
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
    return next((line for line in reversed(text.splitlines()) if line.strip()), "")


def _first_line(text: str) -> str:
    return next((line for line in text.splitlines() if line.strip()), "")


# `strip()` would take the INDENTATION of the first surviving line with the blank lines, and
# a page that continues a code block starts indented. Flattening it is the corruption the
# whole page-image route exists to avoid, so only whole blank lines go.
def _trim(text: str) -> str:
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _drop_lines(text: str, count: int) -> str:
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
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if _FENCE_LINE_RE.match(line):
            return _trim("\n".join(lines[:index] + lines[index + 1 :]))
        return text
    return text


def _drop_repeated_header(text: str) -> str:
    lines = text.splitlines()
    body = [index for index, line in enumerate(lines) if line.strip()]
    if len(body) < 2:
        return text
    first, second = body[0], body[1]
    if _TABLE_ROW_RE.match(lines[first]) and _TABLE_DIVIDER_RE.match(lines[second]):
        return _trim("\n".join(lines[:first] + lines[second + 1 :]))
    return text


def _clamp_drop(value) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_SEAM_DROP_LINES))


def valid_seams(records) -> list[dict]:
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
# It CLASSIFIES the seam and never rewrites a character: the transcription prompt is built
# on «copy character by character», and a second model allowed to redraft would undo it. All
# it may say is how the two pages are glued and how many of the second one's opening lines
# are repeated layout. Everything it answers is checked against the catalogue before it is
# believed, and anything unreadable falls back to the deterministic rule — one seam is never
# a reason to throw away a forty-page transcription.

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
            reporter.tick(done, detail=f"costura {index - 1}→{index}")
            record = _review_seam(left, right, index, len(pages), model, tag, prompts)
            if record is not None:
                records.append(record)
    merged = sum(1 for record in records if record.get("separator", PARAGRAPH) != PARAGRAPH)
    if records:
        logger.info(f"{tag}{merged}/{len(boundaries)} seam(s) joined as a continuation")
    return records


def _boundaries(pages: list[str]) -> list[tuple[str, str, int]]:
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

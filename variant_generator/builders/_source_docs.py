import json
import re
import unicodedata
from pathlib import Path

from loguru import logger

from .. import config

SUPPORTED_EXTS = (".pdf", ".docx", ".md", ".txt")
PLAIN_TEXT_EXTS = (".md", ".txt")
CONVERTED_EXTS = (".pdf", ".docx")

CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
SEPARATOR_RE = re.compile(r"^\s*---\s*$", re.MULTILINE)
FENCE_TOKEN_RE = re.compile(r"§§FENCE(\d+)§§")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
PAGE_NUMBER_RE = re.compile(r"^[ \t]*\d{1,4}[ \t]*$", re.MULTILINE)
HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
BLANK_RUN_RE = re.compile(r"\n{3,}")
TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)

# PDFs typeset with TeX carry their accents as a separate glyph placed BEFORE the vowel,
# and every PDF backend hands them over that way: `M´etodo`, `tama˜no`, `n´umero`. Docling
# does not recompose them, so the corruption reaches the concept names ("Documentaci´on")
# and, worse, splits one concept into an accented and an unaccented spelling that no merge
# pass can see as the same word. Only the SPACING accent characters are listed: the ASCII
# backtick, `~` and `^` are markdown and would eat strikethrough and exponents.
SPACING_ACCENTS = {"´": "́", "˜": "̃", "¨": "̈", "ˆ": "̂"}
# TeX writes an accented i as \'\i, so the vowel underneath arrives DOTLESS: `l´ınea` is
# not `l´inea`. Restoring the dot is part of recomposing, not a separate concern.
DOTLESS = {"ı": "i", "ȷ": "j"}
TEX_ACCENT_RE = re.compile(f"([{''.join(SPACING_ACCENTS)}])([a-zA-Z{''.join(DOTLESS)}])")


def default_converter(ocr: bool = False, table_structure: bool = True):
    try:
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import (
            DocumentConverter,
            InputFormat,
            PdfFormatOption,
        )
    except ImportError as e:
        raise ImportError(
            "The builders need Docling, which is an optional extra. "
            "Install it with: uv sync --extra builders"
        ) from e

    pdf_options = PdfPipelineOptions()
    pdf_options.do_ocr = ocr
    pdf_options.do_table_structure = table_structure

    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pdf_options, backend=PyPdfiumDocumentBackend
            )
        },
    )


def list_source_files(input_dir: str | Path, recursive: bool = False) -> list[Path]:
    root = Path(input_dir)
    candidates = root.rglob("*") if recursive else root.iterdir()
    return sorted(p for p in candidates if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS)


# MARKDOWN ------------------------------------------------------------------------------------

# The markdown is the real input of every builder, so it is materialised instead of being
# rebuilt in memory on each run: Docling is the slowest and most fragile step, and once the
# text is on disk a rebuild needs no Docling at all and a failed extraction can be blamed on
# the right stage by reading the file. Freshness is make-style — the cache is used while it
# is newer than its source — which also means a hand-fixed markdown survives until the
# original document itself changes.
def markdown_cache_path(source: str | Path) -> Path:
    source = Path(source)
    return Path(config.MARKDOWN_CACHE_DIR) / source.parent.name / f"{source.name}.md"


def to_markdown(converter, input_path: Path, use_cache: bool = True) -> str:
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    if suffix in PLAIN_TEXT_EXTS:
        return tidy_markdown(input_path.read_text(encoding="utf-8"))
    if suffix not in CONVERTED_EXTS:
        raise ValueError(f"Unsupported file extension: {suffix}")

    cached = markdown_cache_path(input_path) if use_cache else None
    if cached is not None and cached.exists():
        if cached.stat().st_mtime >= input_path.stat().st_mtime:
            logger.info(f"[{input_path.name}] markdown reused from {cached}")
            # Re-tidied on the way out, and rewritten when that changes anything: Docling is
            # the expensive half and its output does not change, so an improvement to the
            # cleanup must not cost a reconversion of the whole corpus to take effect.
            return _refresh(cached, tidy_markdown(cached.read_text(encoding="utf-8")))
        logger.info(f"[{input_path.name}] source is newer than its markdown; reconverting")

    text = tidy_markdown(converter.convert(str(input_path)).document.export_to_markdown())
    if cached is not None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(text, encoding="utf-8")
        logger.info(f"[{input_path.name}] markdown written to {cached}")
    return text


def _refresh(path: Path, text: str) -> str:
    if text != path.read_text(encoding="utf-8"):
        path.write_text(text, encoding="utf-8")
        logger.info(f"[{path.name}] cached markdown re-tidied in place")
    return text


# Only what is unambiguous. Header/footer boilerplate is NOT removed here on purpose: the
# rule that catches it ("a short line repeated many times") also eats legitimately repeated
# lines like a "Solución:" label in an exercise sheet, and this text feeds the bank builder
# too. Materialising the markdown is precisely what makes that a reviewable step later.
def tidy_markdown(text: str) -> str:
    masked, fences = _mask_fences(text)
    masked = TRAILING_WS_RE.sub("", masked)
    masked = HYPHEN_BREAK_RE.sub(r"\1\2", masked)
    masked = _recompose_accents(masked)
    masked = PAGE_NUMBER_RE.sub("", masked)
    masked = BLANK_RUN_RE.sub("\n\n", masked)
    return _restore_fences(masked, fences).strip() + "\n"


# Only rewrite when the pair really composes into one character: `˜` before a letter that
# takes no tilde must be left exactly as it was, not turned into a letter with a dangling
# combining mark, which would be worse than the corruption it tries to fix.
def _recompose_accents(text: str) -> str:
    def _compose(match: re.Match) -> str:
        letter = DOTLESS.get(match.group(2), match.group(2))
        composed = unicodedata.normalize("NFC", letter + SPACING_ACCENTS[match.group(1)])
        return composed if len(composed) == 1 else match.group(0)

    return TEX_ACCENT_RE.sub(_compose, text)


def _mask_fences(text: str) -> tuple[str, list[str]]:
    fences: list[str] = []

    def _stash(match):
        fences.append(match.group(0))
        return f"§§FENCE{len(fences) - 1}§§"

    return CODE_FENCE_RE.sub(_stash, text), fences


def _restore_fences(text: str, fences: list[str]) -> str:
    return FENCE_TOKEN_RE.sub(lambda m: fences[int(m.group(1))], text)


def headings_by_level(text: str) -> dict[int, list[str]]:
    masked, _ = _mask_fences(text)
    levels: dict[int, list[str]] = {}
    seen: dict[int, set[str]] = {}
    for line in masked.splitlines():
        heading = HEADING_RE.match(line)
        if not heading:
            continue
        level = len(heading.group(1))
        title = " ".join(heading.group(2).split())
        key = title.casefold()
        if key in seen.setdefault(level, set()):
            continue
        seen[level].add(key)
        levels.setdefault(level, []).append(title)
    return levels


def split_blocks(text: str) -> list[str]:
    masked, fences = _mask_fences(text)
    pieces = (
        SEPARATOR_RE.split(masked)
        if SEPARATOR_RE.search(masked)
        else re.split(r"\n\s*\n", masked)
    )
    return [
        restored for restored in (_restore_fences(p, fences).strip() for p in pieces) if restored
    ]


# CHUNKING ------------------------------------------------------------------------------------


def chunk_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks


# A chunk that starts mid-section is a fragment nobody can name consistently: the extractor
# sees prose with no idea which part of the syllabus it belongs to, and the same idea comes
# out named differently from two neighbouring chunks. Cutting on headings instead, and
# handing the heading path over with the text, is what lets the naming canon be applied.
# Sections are PACKED up to the budget rather than emitted one per heading, because a
# heavily subdivided document would otherwise multiply the number of model calls.
def chunk_markdown(text: str, max_chars: int) -> list[tuple[str, str]]:
    sections = _sections(text)
    if not sections:
        return [("", chunk) for chunk in chunk_text(text, max_chars)]

    chunks: list[tuple[str, str]] = []
    buffer: list[str] = []
    paths: list[str] = []

    def flush() -> None:
        if buffer:
            chunks.append((_common_path(paths), "\n\n".join(buffer)))
            buffer.clear()
            paths.clear()

    for path, body in sections:
        if len(body) > max_chars:
            flush()
            chunks.extend((path, piece) for piece in chunk_text(body, max_chars))
            continue
        pending = sum(len(b) + 2 for b in buffer)
        if buffer and pending + len(body) > max_chars:
            flush()
        buffer.append(body)
        paths.append(path)
    flush()
    return chunks


def _sections(text: str) -> list[tuple[str, str]]:
    masked, fences = _mask_fences(text)
    stack: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: list[str] = []
    path = ""

    def close() -> None:
        if any(line.strip() for line in current):
            sections.append((path, list(current)))
        current.clear()

    for line in masked.splitlines():
        heading = HEADING_RE.match(line)
        if not heading:
            current.append(line)
            continue
        close()
        level = len(heading.group(1))
        del stack[level - 1 :]
        stack.extend([""] * (level - 1 - len(stack)))
        stack.append(heading.group(2).strip())
        path = " > ".join(part for part in stack if part)
        current.append(line)
    close()

    return [
        (p, body)
        for p, lines in sections
        if (body := _restore_fences("\n".join(lines), fences).strip())
    ]


def _common_path(paths: list[str]) -> str:
    parts = [p.split(" > ") for p in paths if p]
    if not parts:
        return ""
    common = parts[0]
    for other in parts[1:]:
        shared: list[str] = []
        for mine, theirs in zip(common, other):
            if mine != theirs:
                break
            shared.append(mine)
        common = shared
        if not common:
            break
    return " > ".join(common)


def save_json(data: dict, output_file_path: str | Path) -> None:
    output_path = Path(output_file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

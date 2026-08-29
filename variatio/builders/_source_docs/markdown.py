"""Markdown for the builders: converting a document to it, caching it and tidying it up.

The markdown is the real input of every builder, so it is materialised on disk rather than
rebuilt in memory on each run: conversion is the slowest and most fragile step, a rebuild
then needs no Docling at all, and a bad extraction can be blamed on the right stage by
reading the file.
"""

import json
import re
import unicodedata
from pathlib import Path

from loguru import logger

from .files import (
    CONVERTED_EXTS,
    PLAIN_TEXT_EXTS,
    required_cache_dir,
    resolve_converter,
    source_hash,
)

META_SUFFIX = ".source.json"

CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
SEPARATOR_RE = re.compile(r"^\s*---\s*$", re.MULTILINE)
FENCE_TOKEN_RE = re.compile(r"§§FENCE(\d+)§§")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
# Where a page ENDED, kept in the joined markdown so a transcription can still be read page
# by page and removed before anything is chunked: a comment that survived into a chunk would
# be quoted back as an item's statement or as a concept's corpus passage.
PAGE_MARK_RE = re.compile(r"^[ \t]*<!--\s*pág\.\s*\d+\s*-->[ \t]*(?:\n|$)", re.MULTILINE)
PAGE_NUMBER_RE = re.compile(r"^[ \t]*\d{1,4}[ \t]*$", re.MULTILINE)
HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
BLANK_RUN_RE = re.compile(r"\n{3,}")
TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)

# PDFs typeset with TeX carry their accents as a separate glyph placed BEFORE the vowel
# (`M´etodo`, `tama˜no`), and no PDF backend recomposes them, so the corruption reaches the
# concept names and splits one concept into an accented and an unaccented spelling. Only the
# SPACING accents are listed: the ASCII backtick, `~` and `^` are markdown and would eat
# strikethrough and exponents.
SPACING_ACCENTS = {"´": "́", "˜": "̃", "¨": "̈", "ˆ": "̂"}
# TeX writes an accented i as \'\i, so the vowel underneath arrives DOTLESS: `l´ınea`.
DOTLESS = {"ı": "i", "ȷ": "j"}
TEX_ACCENT_RE = re.compile(f"([{''.join(SPACING_ACCENTS)}])([a-zA-Z{''.join(DOTLESS)}])")

# Docling's markdown serializer post-processes every text span it writes with exactly two
# escapes: `re.sub(r"(?<!\\)_", r"\_")` and `html.escape(res, quote=False)`. Measured over
# the three reference instances the whole damage is those four sequences and nothing else.
# `html.escape` writes `&` first, so a source `&lt;` leaves as `&amp;lt;`; one left-to-right
# pass over all three entities inverts that exactly, since `re.sub` never rescans a
# replacement.
CONVERTER_ENTITY_RE = re.compile(r"&(amp|lt|gt);")
CONVERTER_ENTITIES = {"amp": "&", "lt": "<", "gt": ">"}
CONVERTER_UNDERSCORE_RE = re.compile(r"\\_")


def markdown_cache_path(source: str | Path, cache_dir: str | Path) -> Path:
    """Where the markdown of a source document is cached."""
    source = Path(source)
    return Path(cache_dir) / source.parent.name / f"{source.name}.md"


def markdown_meta_path(cached: str | Path) -> Path:
    """Where the sidecar recording which bytes a cached markdown came from lives."""
    cached = Path(cached)
    return cached.with_name(cached.name + META_SUFFIX)


def _recorded_source(cached: Path) -> str | None:
    """Return the source digest the sidecar records, or `None` when there is none."""
    meta_path = markdown_meta_path(cached)
    if not meta_path.exists():
        return None
    try:
        recorded = json.loads(meta_path.read_text(encoding="utf-8")).get("source_sha256")
    except (json.JSONDecodeError, OSError):
        return None
    return recorded if isinstance(recorded, str) else None


def _record_source(cached: Path, source: Path, digest: str) -> None:
    """Write the sidecar naming the source document and its digest."""
    markdown_meta_path(cached).write_text(
        json.dumps(
            {"source": source.name, "source_sha256": digest},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _is_current(cached: Path, input_path: Path, digest: str) -> bool:
    """Say whether the cached markdown still corresponds to the source document.

    Freshness is the source's BYTES, so a hand-fixed markdown survives until the original
    changes and a document that was merely copied or restored has not changed. Make-style
    mtime is only for a cache written before the sidecar existed, which has nothing else to
    go on.
    """
    recorded = _recorded_source(cached)
    if recorded is not None:
        return recorded == digest
    return cached.stat().st_mtime >= input_path.stat().st_mtime


def to_markdown(
    converter,
    input_path: Path,
    use_cache: bool = True,
    cache_dir: str | Path | None = None,
) -> str:
    """Convert one document to markdown, through the cache when there is one."""
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()
    if suffix in PLAIN_TEXT_EXTS:
        return tidy_markdown(input_path.read_text(encoding="utf-8"))
    if suffix not in CONVERTED_EXTS:
        raise ValueError(f"Unsupported file extension: {suffix}")

    cached = (
        markdown_cache_path(input_path, required_cache_dir(cache_dir, "to_markdown"))
        if use_cache
        else None
    )
    digest = source_hash(input_path) if cached is not None else ""
    if cached is not None and cached.exists():
        if _is_current(cached, input_path, digest):
            logger.debug(f"[{input_path.name}] markdown reused from {cached}")
            _record_source(cached, input_path, digest)
            # Re-tidied on the way out: conversion is the expensive half and its output does
            # not change, so improving the cleanup must not cost a whole reconversion.
            return _refresh(
                cached, tidy_markdown(cached.read_text(encoding="utf-8"), converted=True)
            )
        logger.info(f"[{input_path.name}] the document changed; reconverting")

    # The one place a converter is ever used, and therefore the only place a lazy one has to
    # be resolved: everything above returns without Docling — plain text, and a cache hit.
    document = resolve_converter(converter).convert(str(input_path)).document
    text = tidy_markdown(document.export_to_markdown(), converted=True)
    if cached is not None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(text, encoding="utf-8")
        _record_source(cached, input_path, digest)
        logger.debug(f"[{input_path.name}] markdown written to {cached}")
    return text


def _refresh(path: Path, text: str) -> str:
    """Rewrite the cached file when re-tidying changed it, and return the text."""
    if text != path.read_text(encoding="utf-8"):
        path.write_text(text, encoding="utf-8")
        logger.debug(f"[{path.name}] cached markdown reformatted")
    return text


def tidy_markdown(text: str, converted: bool = False) -> str:
    """Clean up markdown, undoing the converter's own escapes when it wrote it.

    Only what is unambiguous. Header/footer boilerplate is deliberately NOT removed: the
    rule that catches it ("a short line repeated many times") also eats a legitimately
    repeated `Solución:` label, and this text feeds the exemplars bank too.
    """
    masked, fences = mask_fences(text)
    masked = TRAILING_WS_RE.sub("", masked)
    if converted:
        masked = undo_converter_escapes(masked)
    masked = HYPHEN_BREAK_RE.sub(r"\1\2", masked)
    masked = _recompose_accents(masked)
    masked = PAGE_NUMBER_RE.sub("", masked)
    masked = BLANK_RUN_RE.sub("\n\n", masked)
    return restore_fences(masked, fences).strip() + "\n"


def undo_converter_escapes(text: str) -> str:
    """Invert Docling's two post-processing escapes, and nothing else.

    For converter output only — never a `.md` a person wrote, where `&gt;` is what they
    typed, and never a transcribed page, where the VLM writes `\\|`, `\\#` and `\\$` on
    purpose inside LaTeX and table cells. Fences are already masked when this runs, which is
    load-bearing: Docling serialises code with both escapes off. A literal backslash-
    underscore in the source is the one thing it cannot tell from an escaped one, and that
    is given up deliberately.
    """
    text = CONVERTER_ENTITY_RE.sub(lambda m: CONVERTER_ENTITIES[m.group(1)], text)
    return CONVERTER_UNDERSCORE_RE.sub("_", text)


def _recompose_accents(text: str) -> str:
    """Glue a spacing accent onto the letter that follows it, where the two compose."""

    def _compose(match: re.Match) -> str:
        """Compose one accent/letter pair, or leave it exactly as it was."""
        letter = DOTLESS.get(match.group(2), match.group(2))
        composed = unicodedata.normalize("NFC", letter + SPACING_ACCENTS[match.group(1)])
        # Only when the pair really becomes ONE character: a letter left carrying a dangling
        # combining mark is worse than the corruption this tries to fix.
        return composed if len(composed) == 1 else match.group(0)

    return TEX_ACCENT_RE.sub(_compose, text)


def mask_fences(text: str) -> tuple[str, list[str]]:
    """Replace every code fence with a token, returning the text and the fences."""
    fences: list[str] = []

    def _stash(match):
        """Store one fence and return the token standing in for it."""
        fences.append(match.group(0))
        return f"§§FENCE{len(fences) - 1}§§"

    return CODE_FENCE_RE.sub(_stash, text), fences


def restore_fences(text: str, fences: list[str]) -> str:
    """Put the masked code fences back where their tokens are."""
    return FENCE_TOKEN_RE.sub(lambda m: fences[int(m.group(1))], text)


def headings_by_level(text: str) -> dict[int, list[str]]:
    """The document's headings, deduplicated case-insensitively and grouped by level."""
    masked, _ = mask_fences(text)
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


def page_mark(index: int) -> str:
    """The comment marking where page `index` ended."""
    return f"<!-- pág. {index} -->"


def strip_page_marks(text: str) -> str:
    """Remove the page marks, leaving the ones inside a code fence alone."""
    masked, fences = mask_fences(text)
    masked = BLANK_RUN_RE.sub("\n\n", PAGE_MARK_RE.sub("", masked))
    return restore_fences(masked, fences).strip()


def split_blocks(text: str) -> list[str]:
    """Split the document into blocks, on `---` rules when it has any and on blank lines."""
    masked, fences = mask_fences(strip_page_marks(text))
    pieces = (
        SEPARATOR_RE.split(masked)
        if SEPARATOR_RE.search(masked)
        else re.split(r"\n\s*\n", masked)
    )
    return [
        restored for restored in (restore_fences(p, fences).strip() for p in pieces) if restored
    ]

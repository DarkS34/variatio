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
# Where a page ENDED, kept in the joined markdown so the transcription of a document can
# still be read page by page, and removed before anything is chunked: an HTML comment that
# survived into a chunk would be quoted back as an item's statement or as a concept's
# corpus passage. Written only on a seam that is a paragraph break anyway, so it never
# lands inside a fence, a table or a sentence.
PAGE_MARK_RE = re.compile(r"^[ \t]*<!--\s*pág\.\s*\d+\s*-->[ \t]*(?:\n|$)", re.MULTILINE)
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


# The markdown is the real input of every builder, so it is materialised instead of being
# rebuilt in memory on each run: Docling is the slowest and most fragile step, and once the
# text is on disk a rebuild needs no Docling at all and a failed extraction can be blamed on
# the right stage by reading the file. Freshness is the SOURCE'S BYTES, recorded beside the
# markdown: a hand-fixed markdown survives until the original document itself changes, and
# a document that was merely copied or restored has not changed. Make-style mtime is kept
# only for a cache written before the sidecar existed, which has nothing else to go on.
def markdown_cache_path(source: str | Path, cache_dir: str | Path) -> Path:
    source = Path(source)
    return Path(cache_dir) / source.parent.name / f"{source.name}.md"


def markdown_meta_path(cached: str | Path) -> Path:
    cached = Path(cached)
    return cached.with_name(cached.name + META_SUFFIX)


def _recorded_source(cached: Path) -> str | None:
    meta_path = markdown_meta_path(cached)
    if not meta_path.exists():
        return None
    try:
        recorded = json.loads(meta_path.read_text(encoding="utf-8")).get("source_sha256")
    except (json.JSONDecodeError, OSError):
        return None
    return recorded if isinstance(recorded, str) else None


def _record_source(cached: Path, source: Path, digest: str) -> None:
    markdown_meta_path(cached).write_text(
        json.dumps(
            {"source": source.name, "source_sha256": digest},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _is_current(cached: Path, input_path: Path, digest: str) -> bool:
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
            # Re-tidied on the way out, and rewritten when that changes anything: Docling is
            # the expensive half and its output does not change, so an improvement to the
            # cleanup must not cost a reconversion of the whole corpus to take effect.
            return _refresh(cached, tidy_markdown(cached.read_text(encoding="utf-8")))
        logger.info(f"[{input_path.name}] the document changed; reconverting")

    # The one place a converter is ever used, and therefore the only place a lazy one has to
    # be resolved: everything above returns without Docling — plain text, and a cache hit.
    document = resolve_converter(converter).convert(str(input_path)).document
    text = tidy_markdown(document.export_to_markdown())
    if cached is not None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(text, encoding="utf-8")
        _record_source(cached, input_path, digest)
        logger.debug(f"[{input_path.name}] markdown written to {cached}")
    return text


def _refresh(path: Path, text: str) -> str:
    if text != path.read_text(encoding="utf-8"):
        path.write_text(text, encoding="utf-8")
        logger.debug(f"[{path.name}] cached markdown reformatted")
    return text


# Only what is unambiguous. Header/footer boilerplate is NOT removed here on purpose: the
# rule that catches it ("a short line repeated many times") also eats legitimately repeated
# lines like a "Solución:" label in an exercise sheet, and this text feeds the bank builder
# too. Materialising the markdown is precisely what makes that a reviewable step later.
def tidy_markdown(text: str) -> str:
    masked, fences = mask_fences(text)
    masked = TRAILING_WS_RE.sub("", masked)
    masked = HYPHEN_BREAK_RE.sub(r"\1\2", masked)
    masked = _recompose_accents(masked)
    masked = PAGE_NUMBER_RE.sub("", masked)
    masked = BLANK_RUN_RE.sub("\n\n", masked)
    return restore_fences(masked, fences).strip() + "\n"


# Only rewrite when the pair really composes into one character: `˜` before a letter that
# takes no tilde must be left exactly as it was, not turned into a letter with a dangling
# combining mark, which would be worse than the corruption it tries to fix.
def _recompose_accents(text: str) -> str:
    def _compose(match: re.Match) -> str:
        letter = DOTLESS.get(match.group(2), match.group(2))
        composed = unicodedata.normalize("NFC", letter + SPACING_ACCENTS[match.group(1)])
        return composed if len(composed) == 1 else match.group(0)

    return TEX_ACCENT_RE.sub(_compose, text)


def mask_fences(text: str) -> tuple[str, list[str]]:
    fences: list[str] = []

    def _stash(match):
        fences.append(match.group(0))
        return f"§§FENCE{len(fences) - 1}§§"

    return CODE_FENCE_RE.sub(_stash, text), fences


def restore_fences(text: str, fences: list[str]) -> str:
    return FENCE_TOKEN_RE.sub(lambda m: fences[int(m.group(1))], text)


def headings_by_level(text: str) -> dict[int, list[str]]:
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
    return f"<!-- pág. {index} -->"


def strip_page_marks(text: str) -> str:
    masked, fences = mask_fences(text)
    masked = BLANK_RUN_RE.sub("\n\n", PAGE_MARK_RE.sub("", masked))
    return restore_fences(masked, fences).strip()


def split_blocks(text: str) -> list[str]:
    masked, fences = mask_fences(strip_page_marks(text))
    pieces = (
        SEPARATOR_RE.split(masked)
        if SEPARATOR_RE.search(masked)
        else re.split(r"\n\s*\n", masked)
    )
    return [
        restored for restored in (restore_fences(p, fences).strip() for p in pieces) if restored
    ]

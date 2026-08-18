import re
import unicodedata
from pathlib import Path

from loguru import logger

from .files import CONVERTED_EXTS, PLAIN_TEXT_EXTS, required_cache_dir

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


# The markdown is the real input of every builder, so it is materialised instead of being
# rebuilt in memory on each run: Docling is the slowest and most fragile step, and once the
# text is on disk a rebuild needs no Docling at all and a failed extraction can be blamed on
# the right stage by reading the file. Freshness is make-style — the cache is used while it
# is newer than its source — which also means a hand-fixed markdown survives until the
# original document itself changes.
def markdown_cache_path(source: str | Path, cache_dir: str | Path) -> Path:
    source = Path(source)
    return Path(cache_dir) / source.parent.name / f"{source.name}.md"


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
    if cached is not None and cached.exists():
        if cached.stat().st_mtime >= input_path.stat().st_mtime:
            logger.debug(f"[{input_path.name}] markdown reutilizado de {cached}")
            # Re-tidied on the way out, and rewritten when that changes anything: Docling is
            # the expensive half and its output does not change, so an improvement to the
            # cleanup must not cost a reconversion of the whole corpus to take effect.
            return _refresh(cached, tidy_markdown(cached.read_text(encoding="utf-8")))
        logger.info(f"[{input_path.name}] el origen es más nuevo que su markdown; reconvirtiendo")

    text = tidy_markdown(converter.convert(str(input_path)).document.export_to_markdown())
    if cached is not None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(text, encoding="utf-8")
        logger.debug(f"[{input_path.name}] markdown escrito en {cached}")
    return text


def _refresh(path: Path, text: str) -> str:
    if text != path.read_text(encoding="utf-8"):
        path.write_text(text, encoding="utf-8")
        logger.debug(f"[{path.name}] markdown en caché reformateado")
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


def split_blocks(text: str) -> list[str]:
    masked, fences = mask_fences(text)
    pieces = (
        SEPARATOR_RE.split(masked)
        if SEPARATOR_RE.search(masked)
        else re.split(r"\n\s*\n", masked)
    )
    return [
        restored for restored in (restore_fences(p, fences).strip() for p in pieces) if restored
    ]

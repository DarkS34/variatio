import re
import unicodedata

from .. import config

MIN_NEEDLE_LENGTH = 3
MAX_INFLECTION_SLACK = 2

_STOPWORDS = frozenset(
    {"de", "del", "la", "el", "los", "las", "en", "y", "o", "a", "un", "una", "por", "con", "para"}
)


def _singular(word: str) -> str:
    for suffix in config.KG_BUILDER_PLURAL_SUFFIXES:
        if len(word) > MIN_NEEDLE_LENGTH and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _stems(text: str) -> set[str]:
    return {_singular(w) for w in re.findall(r"\w+", fold(text))}


def mentions(text: str, concept: str) -> bool:
    if re.search(rf"(?<!\w){re.escape(fold(concept))}(?!\w)", fold(text)):
        return True
    needles = [
        _singular(w)
        for w in re.findall(r"\w+", fold(concept))
        if w not in _STOPWORDS and len(w) >= MIN_NEEDLE_LENGTH
    ]
    if not needles:
        return False
    stems = _stems(text)
    return all(
        any(
            stem.startswith(needle) and len(stem) - len(needle) <= MAX_INFLECTION_SLACK
            for stem in stems
        )
        for needle in needles
    )


def fold(text: str) -> str:
    lowered = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(c for c in lowered if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped)

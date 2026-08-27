from ..core import languages
from . import en, es
from .marks import CORRECT_ANSWER_MARK, EMPTY_PAGE_MARK, SEAM_SEPARATORS

_SETS = {"es": es, "en": en}


def of(language: str | None):
    return _SETS[languages.resolve(language)]


__all__ = [
    "CORRECT_ANSWER_MARK",
    "EMPTY_PAGE_MARK",
    "SEAM_SEPARATORS",
    "of",
]

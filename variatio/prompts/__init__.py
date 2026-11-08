"""The two prompt sets, and the resolver a workspace's language goes through.

`es/` and `en/` export the same names with the same signatures, so a caller holds one of
them without knowing which. The marks are shared rather than declared twice: they are
protocol tokens, not prose.
"""

from ..utils import languages
from . import en, es
from .marks import CORRECT_ANSWER_MARK, EMPTY_IMAGE_MARK, EMPTY_PAGE_MARK, SEAM_SEPARATORS

_SETS = {"es": es, "en": en}


def of(language: str | None):
    """Return the prompt set for `language`, falling back to the default when unknown."""
    return _SETS[languages.resolve(language)]


def difficulty(language: str | None) -> tuple[str, list[str]]:
    """Return the difficulty field name and its rungs, as the prompt set of `language` writes them.

    One call returns both so no caller pairs one set's field NAME — `nivel_dificultad` in
    Spanish, `difficulty_level` in English — with the other set's ladder.
    """
    module = of(language)
    return module.DIFFICULTY_FIELD, list(module.DIFFICULTY_LEVELS)


__all__ = [
    "CORRECT_ANSWER_MARK",
    "EMPTY_IMAGE_MARK",
    "EMPTY_PAGE_MARK",
    "SEAM_SEPARATORS",
    "difficulty",
    "of",
]

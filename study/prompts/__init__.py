"""The two baseline prompts of the reference arms, in one set per language.

Same resolver and same rule as `variatio.prompts`: a session runs inside ONE workspace, so
the three arms are prompted in the language that workspace's own prompts are written in —
otherwise the comparison measures a language difference and calls it an architecture
difference. Both sets are deliberately POOR, and translating one is not an occasion to
improve it.
"""

from variatio.core import languages

from . import en, es

_SETS = {"es": es, "en": en}


def of(language: str | None):
    """Return the prompt set for a workspace's language, falling back to the default."""
    return _SETS[languages.resolve(language)]


__all__ = ["of"]

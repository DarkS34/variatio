"""The tutor's prompts and fixed texts, one set per workspace language.

Same resolver and same rule as `variatio.prompts`: a conversation happens inside ONE
workspace, so the tutor speaks the language that workspace's own prompts are written in, and
the fixed answers a student reads — the off-topic offer, the refusal, the fallback question —
come from the same set as the replies around them.
"""

from variatio.core import languages

from . import en, es

_SETS = {"es": es, "en": en}


def of(language: str | None):
    """Return the prompt set for a workspace's language, falling back to the default."""
    return _SETS[languages.resolve(language)]


__all__ = ["of"]

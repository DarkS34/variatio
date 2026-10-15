"""The free chat's prompts and fixed texts, one set per workspace language.

Same resolver and same rule as `variatio.prompts`: a conversation happens inside ONE
workspace, so the chat speaks the language that workspace's own prompts are written in, and
the fixed answer a student reads — the refusal of the guardrail — comes from the same set as
the replies around it. Both sets export the same names with the same signatures.
"""

from variatio.core import languages

from . import en, es

_SETS = {"es": es, "en": en}


def of(language: str | None):
    """Return the prompt set for a workspace's language, falling back to the default."""
    return _SETS[languages.resolve(language)]


__all__ = ["of"]

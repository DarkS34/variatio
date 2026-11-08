"""The blocks of a chat-like system prompt, one set per language, and the facts they read (D-235).

A consumer writes its role and its way of helping; the subject, the language of the reply,
the scope and the format are said here, in a fixed order. The free chat is built on them. The
tutor keeps its own method (it lost against it three times in plan-prompts F8) and takes only
`instruction_code`. A consumer imports this; nothing here imports a consumer (D-004, D-007).
`es/conversation.py` and `en/conversation.py` hold the blocks; this module resolves them and
reads the facts. In `server/conversations/prompts/` until 2026-11-08.

The reply is in the subject's language of instruction, never in the account's interface
language nor in the one the student writes in (the user's decision P5, 2026-10-31).
"""

import re

from ..utils import languages
from ..utils.lexicon import fold

from .en import conversation as en
from .es import conversation as es

_SETS = {"es": es, "en": en}

# How a free-text language fact names the languages we speak, folded.
_NAMES = {"es": ("espanol", "castellano", "spanish"), "en": ("english", "ingles")}


def of(language: str | None):
    """Return the block set for a prompt language, falling back to the default."""
    return _SETS[languages.resolve(language)]


def instruction_code(fact: str | None) -> str | None:
    """Return the code of the subject's language of instruction when we speak it, else None.

    `fact` is `content_context.language_of_instruction`, free text («Español», «English»,
    «castellano (España)»); a language we have no prompt set or patterns for gives None.
    """
    folded = fold(fact or "")
    for code, names in _NAMES.items():
        if any(name in folded for name in names):
            return code
    return languages.normalise(fact)


# A fence, an inline span, or a line that ends a statement or opens a block the way code does.
_CODE = re.compile(r"```|`[^`\n]+`|^\s*\S.*(?:[;{}]|\)\s*:|:=)\s*$", re.MULTILINE)


def has_code(texts: list[str]) -> bool:
    """Return whether any of `texts` (message, history, exercise) carries code."""
    return any(_CODE.search(text or "") for text in texts)


__all__ = ["has_code", "instruction_code", "of"]

"""The half of the wording that is the same in every language.

Prompt injection is written in English whatever the reader speaks — "ignore previous
instructions" is the canonical attempt and arrives at a Spanish workspace as often as at
an English one — so the English attack vocabulary is not the English set's, it is
everybody's, and each language adds its own on top of it.
"""

OVERRIDE_VERBS: str = r"forget|ignore|disregard|bypass|override|stop following|do not follow"

OVERRIDE_OBJECTS: str = (
    r"instruction(?:s)?|rule(?:s)?|constraint(?:s)?|directive(?:s)?|guideline(?:s)?|prompt(?:s)?"
)

OVERRIDE_QUALIFIERS: str = r"previous|prior|above|earlier"

INJECTION_PATTERNS: tuple[str, ...] = (r"\b(?:system|previous|prior) prompt\b",)

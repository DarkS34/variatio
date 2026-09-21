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


def quote_block(label: str, text: str) -> str:
    """Wrap `text` in a markdown blockquote opened by `label` in bold.

    A blockquote is what keeps a slide's speaker notes distinguishable from the slide's own
    text once both are one page: an aside, in the document's own grammar, that `split_blocks`
    carries whole. Every line of the text is prefixed, a blank one with a bare `>`, so a
    note of several paragraphs stays one quote.
    """
    lines = [f"> {line}" if line else ">" for line in text.strip().splitlines()]
    return "\n".join([f"> **{label}**", ">", *lines])

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

# A requester taking back an instruction of their own ("forget the rules I gave you") is
# revising the commission, not attacking it; each language adds its own phrasing.
OWN_INSTRUCTIONS: str = r"(?:that )?i (?:gave|have given|'ve given|wrote|asked for)(?: you)?"

# Beyond the override verbs (plan F6, 2026-11-02): asking for the text above to be repeated,
# for one's own configuration, a note addressed to the model, and a role-play that hands the
# model another part. The four passed the screen in the F3 gold in both languages.
INJECTION_PATTERNS: tuple[str, ...] = (
    r"\b(?:system|previous|prior) prompt\b",
    r"\brepeat\b[^.;!?]{0,40}\b(?:text|everything|what(?:'s| is)?(?: written)?)\b[^.;!?]{0,20}\babove\b",
    r"\byour (?:configuration|initial|original|internal|hidden|setup) (?:instructions|prompt|rules|settings)\b",
    r"\b(?:p\.? ?s\.?|note|message) (?:to|for) the (?:model|ai|assistant|system)\b",
    r"\blet'?s play a game\b[^.;!?]{0,30}\b(?:you'?re|you are|pretend|act as)\b",
)


def quote_block(label: str, text: str) -> str:
    """Wrap `text` in a markdown blockquote opened by `label` in bold.

    A blockquote is what keeps a slide's speaker notes distinguishable from the slide's own
    text once both are one page: an aside, in the document's own grammar, that `split_blocks`
    carries whole. Every line of the text is prefixed, a blank one with a bare `>`, so a
    note of several paragraphs stays one quote.
    """
    lines = [f"> {line}" if line else ">" for line in text.strip().splitlines()]
    return "\n".join([f"> **{label}**", ">", *lines])

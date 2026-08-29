"""The tokens both prompt sets share, in neither language.

They travel between calls instead of being read by a person: the page transcription adds
`CORRECT_ANSWER_MARK` and the bank extraction strips it, `pages.py` matches
`EMPTY_PAGE_MARK` against what it cached, and `SEAM_SEPARATORS` are the values the seam
grammar pins. Translating one would strand every page already transcribed.
"""

CORRECT_ANSWER_MARK = "✔"

EMPTY_PAGE_MARK = "[PÁGINA SIN CONTENIDO]"

SEAM_SEPARATORS = ("none", "space", "newline", "paragraph")

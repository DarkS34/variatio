"""The tokens both prompt sets share, in neither language.

They travel between calls instead of being read by a person: the page transcription adds
`CORRECT_ANSWER_MARK` and the bank extraction strips it, `pages.py` matches
`EMPTY_PAGE_MARK` and `EMPTY_IMAGE_MARK` against what the model answered, and
`SEAM_SEPARATORS` are the values the seam grammar pins. Translating one would strand every
page already transcribed.
"""

CORRECT_ANSWER_MARK = "✔"

EMPTY_PAGE_MARK = "[PÁGINA SIN CONTENIDO]"

# What the image transcription answers for a logo, a crest or an ornament: the picture is
# dropped from the document instead of being described.
EMPTY_IMAGE_MARK = "[IMAGEN SIN CONTENIDO]"

SEAM_SEPARATORS = ("none", "space", "newline", "paragraph")

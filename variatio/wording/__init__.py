"""The words the pipeline composes itself, in the language of the workspace it runs on.

`prompts/` owns whole documents; this owns the strings the CODE builds — the fragments a
prompt block is assembled from, the sentences the checks write, the marks a transcription
leaves on a page, and the patterns that only match text written in one language. All of
them used to be Spanish literals wherever they happened to be needed, so an English
workspace was read by a Spanish injection regex, judged by a Spanish catalogue and handed
prompt blocks half in the other language.

`es` and `en` export the same names with the same shapes, exactly as the two prompt sets
do, and `beside(prompts)` is what a component holding a prompt set uses so that the two can
never be paired across languages.
"""

from ..core import languages
from . import en, es

_SETS = {"es": es, "en": en}


def beside(prompts):
    """Return the wording that goes with a prompt set already resolved.

    A component is handed one prompt module and must not resolve the wording from anything
    else: the two are read by the same model in the same call, so pairing them across
    languages is the defect this exists to prevent.
    """
    return of(getattr(prompts, "LANGUAGE", None))


def of(language: str | None):
    """Return the wording for `language`, falling back to the default when unknown."""
    return _SETS[languages.resolve(language)]


__all__ = ["beside", "of"]

from variatio.core import languages

from . import en, es

_SETS = {"es": es, "en": en}


# The same resolver `variatio.prompts` has, for the same reason and with the same rule: a
# session runs inside ONE workspace, so the three arms have to be prompted in the language
# that workspace's own prompts are written in — otherwise the comparison measures a
# language difference and calls it an architecture difference.
#
# What this does NOT change is that these two prompts are deliberately POOR. They are the
# baseline; translating one is not an occasion to improve it.
def of(language: str | None):
    return _SETS[languages.resolve(language)]


__all__ = ["of"]

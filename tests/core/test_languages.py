"""The vocabulary of languages, and why there is exactly one of it.

Two different questions get answered with a language in this project — what a person READS
and what a model is INSTRUCTED in — and the whole reason they can stay separate without
drifting is that the set of admissible values is declared once, in a module that imports
nothing, the same trick `workspace.py` and `relations.py` use.
"""

import pytest

from variatio.core import languages
from variatio.core.workspace import Workspace


def test_the_two_languages_are_the_declared_ones():
    assert languages.LANGUAGES == ("es", "en")
    assert languages.DEFAULT in languages.LANGUAGES


def test_every_language_has_a_name_in_its_own_language():
    # A language picker that says "Inglés" to somebody who only reads English is a picker
    # they cannot use, so each name is written in the language it names.
    assert set(languages.NAMES) == set(languages.LANGUAGES)
    assert all(name.strip() for name in languages.NAMES.values())


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("es", "es"),
        ("EN", "en"),
        # What a browser sends. `navigator.language` is a BCP-47 tag and never a bare code,
        # so a registration form seeding itself from it would otherwise always miss.
        ("es-ES", "es"),
        ("en-GB", "en"),
        ("en_US", "en"),
        ("  es  ", "es"),
    ],
)
def test_a_regional_tag_folds_onto_its_language(raw, expected):
    assert languages.normalise(raw) == expected


@pytest.mark.parametrize("raw", ["fr", "de-DE", "", "   ", None, "esperanto"])
def test_what_the_installation_does_not_speak_is_not_normalised_into_something(raw):
    assert languages.normalise(raw) is None


def test_resolve_falls_back_and_normalise_does_not():
    # The difference is the point: `resolve` is for a caller that must end up with A
    # language, `normalise` for one that has to be able to tell "unknown" apart.
    assert languages.resolve("fr") == languages.DEFAULT
    assert languages.resolve(None) == languages.DEFAULT
    assert languages.resolve(None, "en") == "en"
    assert languages.normalise("fr") is None


def test_the_error_names_the_value_and_the_alternatives():
    assert languages.error("es") is None
    message = languages.error("fr")
    assert "fr" in message
    for code in languages.LANGUAGES:
        assert code in message


def test_the_locale_file_is_undotted_and_lives_in_the_instance(tmp_path):
    # Undotted because it is not host state: it travels with `export-instance`, and a
    # workspace handed over without it is a workspace whose prompts nobody can reproduce.
    ws = Workspace(root=tmp_path, slug="x")
    assert ws.locale_path.name == "locale.json"
    assert ws.locale_path.parent == ws.instance_dir

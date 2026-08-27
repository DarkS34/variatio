"""What a workspace declares about the language of its own prompts.

It is read BEFORE anything is built — it is what the builders' instructions are written in
— which is the whole reason it cannot live in `content_context.json`, the artifact a build
produces. Absent means «es», because that is what every workspace written before this
factually was, so the file arriving is a change and its absence is not.
"""

import json

import pytest

from variatio.core import languages
from variatio.core.workspace import Workspace
from variatio.instance import locale


@pytest.fixture
def ws(tmp_path):
    return Workspace(root=tmp_path, slug="aula")


def test_a_workspace_with_no_file_reads_as_spanish(ws):
    assert not ws.locale_path.exists()
    assert locale.prompt_language(ws) == "es"


def test_what_was_written_is_what_is_read_back(ws):
    locale.set_prompt_language(ws, "en")
    assert locale.prompt_language(ws) == "en"
    assert json.loads(ws.locale_path.read_text(encoding="utf-8")) == {"prompt_language": "en"}


def test_a_regional_tag_is_stored_folded(ws):
    assert locale.set_prompt_language(ws, "en-GB") == "en"
    assert json.loads(ws.locale_path.read_text(encoding="utf-8")) == {"prompt_language": "en"}


def test_a_language_the_installation_does_not_speak_is_refused_on_the_way_in(ws):
    with pytest.raises(ValueError) as refused:
        locale.set_prompt_language(ws, "fr")
    assert "fr" in str(refused.value)
    # And nothing was written: a refused save must not leave a file claiming otherwise.
    assert not ws.locale_path.exists()


def test_an_unreadable_file_warns_and_falls_back_rather_than_stopping_the_process(ws):
    # The same rule the settings store follows: an invalid value never keeps the process
    # from starting, because the alternative is an installation nobody can log into to fix.
    ws.locale_path.parent.mkdir(parents=True, exist_ok=True)
    ws.locale_path.write_text("{not json", encoding="utf-8")
    assert locale.prompt_language(ws) == languages.DEFAULT


def test_an_unknown_language_in_the_file_falls_back_too(ws):
    ws.locale_path.parent.mkdir(parents=True, exist_ok=True)
    ws.locale_path.write_text('{"prompt_language": "fr"}', encoding="utf-8")
    assert locale.prompt_language(ws) == languages.DEFAULT


def test_two_workspaces_do_not_share_a_language(tmp_path):
    # The point of the whole file: a language is a property of ONE instance, so an English
    # workspace beside a Spanish one has to leave the Spanish one alone.
    spanish = Workspace(root=tmp_path / "es", slug="es")
    english = Workspace(root=tmp_path / "en", slug="en")
    locale.set_prompt_language(spanish, "es")
    locale.set_prompt_language(english, "en")
    assert locale.prompt_language(spanish) == "es"
    assert locale.prompt_language(english) == "en"

"""The grammar the bank extraction sends, and the one case where it must not send one.

Measured against Cerebras: a remotely served model under constrained decoding stops
emitting raw UTF-8 inside a JSON string and writes `\\u00` plus two wrong hex digits for
every non-ASCII character, so the accented Spanish this phase copies verbatim reaches the
bank as control characters. The grammar is dropped there, on the extraction call and on
the repair that would otherwise re-emit the same paragraphs under one.
"""

import json

import pytest

from variatio import config
from variatio.builders.exemplars_bank_builder import ExemplarsBankBuilder
from variatio.core import inference
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ExemplarsProfile

PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "fields": {
                "enunciado": {"schema": {"type": "string"}, "description": "El texto."},
            },
        }
    }
}

REPLY = json.dumps([{"enunciado": "¿Qué representan las siglas BNF?"}], ensure_ascii=False)


@pytest.fixture
def builder(tmp_path):
    path = tmp_path / "exemplars_profile.json"
    path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return ExemplarsBankBuilder(
        ExemplarsProfile(path),
        workspace=Workspace(tmp_path, "pruebas"),
        verbose=False,
    )


@pytest.fixture
def calls(monkeypatch):
    """Record every generation call and answer each with one valid item."""
    seen: list[dict] = []

    def _generate(**kwargs):
        seen.append(kwargs)
        return type("R", (), {"response": REPLY, "thinking": ""})()

    monkeypatch.setattr(inference, "generate", _generate)
    monkeypatch.setattr(config, "THINK_EB_EXTRACT", False)
    monkeypatch.setattr(config, "EB_EXTRACT_MODEL", "gemma-4-31b")
    monkeypatch.setattr(config, "REPAIR_LLM", "gemma-4-31b")
    return seen


def _local(monkeypatch):
    monkeypatch.setattr(inference, "remote_models", frozenset)


def _remote(monkeypatch):
    monkeypatch.setattr(inference, "remote_models", lambda: frozenset({"gemma-4-31b"}))


# THE EXTRACTION CALL -----------------------------------------------------------------------------


def test_a_local_model_still_gets_the_grammar(builder, calls, monkeypatch):
    _local(monkeypatch)
    builder._extract_batch("un lote", "tag")
    assert calls[0]["format"] == builder._extraction_schema


def test_a_remote_model_is_asked_without_one(builder, calls, monkeypatch):
    _remote(monkeypatch)
    builder._extract_batch("un lote", "tag")
    assert calls[0]["format"] is None


def test_reasoning_drops_it_on_a_local_model_too(builder, calls, monkeypatch):
    _local(monkeypatch)
    monkeypatch.setattr(config, "THINK_EB_EXTRACT", True)
    builder._extract_batch("un lote", "tag")
    assert calls[0]["format"] is None


# THE REPAIR --------------------------------------------------------------------------------------


def test_the_repair_of_a_remote_model_carries_no_grammar_either(builder, calls, monkeypatch):
    """A repair re-emits the same paragraphs, so its grammar would undo the drop."""
    _remote(monkeypatch)
    broken = iter(["no es json", REPLY])
    monkeypatch.setattr(
        inference,
        "generate",
        lambda **kw: (calls.append(kw), type("R", (), {"response": next(broken), "thinking": ""})())[1],
    )
    builder._extract_batch("un lote", "tag")
    assert len(calls) == 2
    assert calls[1]["format"] is None


def test_the_repair_keeps_its_grammar_on_a_local_model(builder, calls, monkeypatch):
    _local(monkeypatch)
    broken = iter(["no es json", REPLY])
    monkeypatch.setattr(
        inference,
        "generate",
        lambda **kw: (calls.append(kw), type("R", (), {"response": next(broken), "thinking": ""})())[1],
    )
    builder._extract_batch("un lote", "tag")
    assert len(calls) == 2
    assert calls[1]["format"] == builder._extraction_schema


# WHAT THE DROP MUST NOT COST ---------------------------------------------------------------------


def test_the_items_still_validate_without_a_grammar(builder, calls, monkeypatch):
    _remote(monkeypatch)
    items = builder._extract_batch("un lote", "tag")
    assert [item["enunciado"] for item in items] == ["¿Qué representan las siglas BNF?"]

import json

import pytest

import main
from system import config

TAGGED = '{"concepts": ["Bucles"], "primary_concept": "Bucles"}'


@pytest.fixture
def bank_path(tmp_path, monkeypatch):
    path = tmp_path / "instance" / "exemplars_bank.json"
    monkeypatch.setattr(config, "EXEMPLARS_BANK_PATH", path)
    return path


def test_annotating_persists_the_result(tagger, scripted_generate, bank_path):
    scripted_generate(*([TAGGED] * 4))
    bank = {"C001": {"statement": "Recorre una lista"}}

    annotated = main._annotate_bank(bank, tagger)

    assert bank_path.exists()
    assert json.loads(bank_path.read_text(encoding="utf-8")) == annotated


def test_an_already_annotated_bank_is_not_retagged(tagger, scripted_generate, bank_path):
    calls = scripted_generate()
    bank = {"C001": {"statement": "Recorre una lista", "concepts": ["Bucles"]}}

    annotated = main._annotate_bank(bank, tagger)

    assert annotated is bank
    assert calls == []
    assert not bank_path.exists()


def test_a_partially_annotated_bank_is_retagged(tagger, scripted_generate, bank_path):
    calls = scripted_generate(*([TAGGED] * 8))
    bank = {
        "C001": {"statement": "Recorre una lista", "concepts": ["Bucles"]},
        "C002": {"statement": "Declara una variable"},
    }

    main._annotate_bank(bank, tagger)

    assert len(calls) == 2
    assert bank_path.exists()


def test_target_concepts_are_ranked_by_frequency():
    bank = {
        "C001": {"concepts": ["Bucles", "Variables"]},
        "C002": {"concepts": ["Bucles"]},
        "C003": {"concepts": ["Bucles", "Variables"]},
        "C004": {"concepts": ["Condicionales"]},
    }

    assert main._pick_target_concepts(bank, k=2) == ["Bucles", "Variables"]


def test_target_concepts_tolerate_unannotated_items():
    assert main._pick_target_concepts({"C001": {}, "C002": {"concepts": None}}, k=3) == []


def test_json_has_key(tmp_path):
    path = tmp_path / "doc.json"
    path.write_text('{"entities": []}', encoding="utf-8")

    assert main._json_has_key(path, "entities")
    assert not main._json_has_key(path, "concepts_by_domains")
    assert not main._json_has_key(tmp_path / "no_existe.json", "entities")


def test_json_has_key_on_malformed_json(tmp_path):
    path = tmp_path / "roto.json"
    path.write_text("{no soy json", encoding="utf-8")

    assert not main._json_has_key(path, "entities")

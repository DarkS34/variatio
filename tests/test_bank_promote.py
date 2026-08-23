import json

import pytest

from server.db import mirror
from server.editors import bank_edit
from server.editors.bank_edit import BankError
from variant_generator.core.workspace import Workspace
from variant_generator.instance.exemplars_profile import ITEM_TYPE_KEY

PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio de programación",
            "description": "El alumno escribe código.",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "general_generation_rules": ["El enunciado especifica la entrada y la salida."],
            "fields": {
                "enunciado": {
                    "schema": {"type": "string"},
                    "description": "El texto del ejercicio.",
                },
            },
        },
    }
}

GRAPH = {
    "concepts_by_domains": {"Fundamentos": ["Bucles", "Listas", "Notación asintótica"]},
    "generic_non_taggable_concepts": ["Notación asintótica"],
    "taggability_reviewed": True,
    "relations": [],
}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror, "mirror_file", lambda ws, path: None)
    workspace = Workspace(tmp_path, "aula")
    workspace.instance_dir.mkdir(parents=True)
    _write(workspace.exemplars_profile_path, PROFILE)
    _write(workspace.kg_path, GRAPH)
    _write(workspace.exemplars_bank_path, {"C001": {"enunciado": "uno", "source": "tema1"}})
    return workspace


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _bank(ws):
    return json.loads(ws.exemplars_bank_path.read_text(encoding="utf-8"))


def test_a_promoted_variant_lands_tagged_and_marked(ws):
    result = bank_edit.add_item(
        ws,
        {"enunciado": "recorre la lista", "concepts": ["ignorado"]},
        "ejercicio",
        ["Bucles", "Notación asintótica", "No existe"],
    )

    item = result["item"]
    assert item["id"] == "G001"
    stored = _bank(ws)["G001"]
    assert stored["enunciado"] == "recorre la lista"
    assert stored[ITEM_TYPE_KEY] == "ejercicio"
    assert stored["source"] == bank_edit.PROMOTED_SOURCE
    assert stored["concepts"] == ["Bucles"]
    assert stored["primary_concept"] == "Bucles"
    assert stored["_tagging"]["method"] == "promoted"


def test_promoted_ids_count_beside_the_extractors(ws):
    bank_edit.add_item(ws, {"enunciado": "a"}, "ejercicio", ["Bucles"])
    result = bank_edit.add_item(ws, {"enunciado": "b"}, "ejercicio", ["Listas"])
    assert result["item"]["id"] == "G002"
    assert set(_bank(ws)) == {"C001", "G001", "G002"}


def test_an_item_that_breaks_the_schema_is_refused(ws):
    with pytest.raises(BankError):
        bank_edit.add_item(ws, {}, "ejercicio", ["Bucles"])
    assert set(_bank(ws)) == {"C001"}


def test_an_unknown_modality_is_refused(ws):
    with pytest.raises(BankError):
        bank_edit.add_item(ws, {"enunciado": "x"}, "inexistente", ["Bucles"])


def test_has_item_answers_without_raising(ws, tmp_path):
    assert bank_edit.has_item(ws, "C001") is True
    assert bank_edit.has_item(ws, "G001") is False
    empty = Workspace(tmp_path / "otro", "otro")
    assert bank_edit.has_item(empty, "C001") is False

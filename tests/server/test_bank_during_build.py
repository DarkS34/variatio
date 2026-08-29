"""What the bank screen reads, and refuses to write, while a build is making a new bank.

A re-extraction writes aside and puts what it made in place whole, so for as long as it
runs there are two banks on disk: the one the workspace still has and the one coming out.
The live panel polls this listing to show the second, and an edit saved against it would
put half a build in place of the artifact.
"""

import json

import pytest

from server.editors import bank_edit
from server.editors.bank_edit import BankError
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ITEM_TYPE_KEY

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

BANK = {
    "C001": {ITEM_TYPE_KEY: "ejercicio", "enunciado": "El de antes", "concepts": []},
}
BUILDING = {
    "C001": {ITEM_TYPE_KEY: "ejercicio", "enunciado": "El que está saliendo", "concepts": []},
}


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path, "aula")
    _write(workspace.exemplars_profile_path, PROFILE)
    _write(workspace.exemplars_bank_path, BANK)
    return workspace


def _statements(ws):
    result = bank_edit.listing(ws, order="id", page=1, page_size=50)
    return [item["enunciado"] for item in result["items"]]


def test_without_a_build_the_listing_reads_the_artifact(ws):
    assert _statements(ws) == ["El de antes"]


def test_while_a_build_runs_the_listing_reads_what_is_coming_out(ws):
    _write(ws.exemplars_bank_building_path, BUILDING)

    assert _statements(ws) == ["El que está saliendo"]


def test_an_edit_is_refused_while_a_build_is_writing(ws):
    _write(ws.exemplars_bank_building_path, BUILDING)

    with pytest.raises(BankError):
        bank_edit.delete_item(ws, "C001")

    assert json.loads(ws.exemplars_bank_path.read_text(encoding="utf-8")) == BANK

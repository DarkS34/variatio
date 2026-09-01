"""Filtering the bank by rung, which is what the screen asks now instead of sorting by it.

«Ordenar por dificultad» was replaced on 2026-09-01 (explicit user request) by a filter:
with three rungs an order only groups the list, where «enséñame los avanzados» is the
question somebody actually asks. The sort survives on the API and has its own file; this
one covers the filter, its counts and the refusal.
"""

import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.routers import bank as route
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ITEM_TYPE_KEY


def _type(primary: str, levels=("basico", "intermedio", "avanzado")) -> dict:
    return {
        "label": primary,
        "primary_field": primary,
        "embed_fields": [primary],
        "fields": {
            primary: {"schema": {"type": "string"}},
            "nivel_dificultad": {"schema": {"enum": list(levels)}, "decided_by": "user"},
        },
    }


PROFILE = {"item_types": {"escritura": _type("enunciado"), "test": _type("pregunta")}}

BANK = {
    "C001": {ITEM_TYPE_KEY: "escritura", "enunciado": "a", "nivel_dificultad": "avanzado"},
    "C002": {ITEM_TYPE_KEY: "test", "pregunta": "b", "nivel_dificultad": "basico"},
    "C003": {ITEM_TYPE_KEY: "escritura", "enunciado": "c", "nivel_dificultad": "avanzado"},
    "C004": {ITEM_TYPE_KEY: "test", "pregunta": "d", "nivel_dificultad": "basico"},
    "C005": {ITEM_TYPE_KEY: "escritura", "enunciado": "e"},
}


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path, "aula")
    workspace.instance_dir.mkdir(parents=True)
    workspace.exemplars_profile_path.write_text(json.dumps(PROFILE), encoding="utf-8")
    workspace.exemplars_bank_path.write_text(json.dumps(BANK), encoding="utf-8")
    return workspace


def _listing(ws, **kwargs):
    return route.listing(access=SimpleNamespace(ws=ws), page=1, page_size=50, **kwargs)


def test_the_filter_keeps_one_rung_across_modalities(ws):
    # The whole point of the shared ladder: «avanzado» is one value, so one filter reads
    # over a mixed list instead of over several interleaved scales.
    ids = [i["id"] for i in _listing(ws, difficulty="avanzado")["items"]]
    assert ids == ["C001", "C003"]


def test_an_item_with_no_rung_is_in_no_rung(ws):
    for rung in ("basico", "intermedio", "avanzado"):
        assert "C005" not in [i["id"] for i in _listing(ws, difficulty=rung)["items"]]
    assert "C005" in [i["id"] for i in _listing(ws)["items"]]


def test_the_counts_are_over_the_whole_bank_and_declared_not_gathered(ws):
    # `intermedio` is declared and empty, and it is still offered: the filter is about what
    # the profile says exists, not about what happens to have been written.
    assert _listing(ws)["difficulties"] == [
        {"value": "basico", "count": 2},
        {"value": "intermedio", "count": 0},
        {"value": "avanzado", "count": 2},
    ]


def test_the_counts_do_not_move_with_the_other_filters(ws):
    # They describe the bank, not the question: a count that shrank as you filtered would
    # be telling you what you already asked for.
    assert _listing(ws, item_type="test")["difficulties"] == _listing(ws)["difficulties"]


def test_it_combines_with_the_modality(ws):
    ids = [i["id"] for i in _listing(ws, difficulty="basico", item_type="test")["items"]]
    assert ids == ["C002", "C004"]


def test_a_rung_the_profile_does_not_declare_is_a_422_that_names_the_ones_that_exist(ws):
    with pytest.raises(HTTPException) as raised:
        _listing(ws, difficulty="imposible")
    assert raised.value.status_code == 422
    assert "imposible" in raised.value.detail
    assert "avanzado" in raised.value.detail


def test_a_profile_with_no_ladder_offers_nothing_to_filter_by(ws):
    profile = json.loads(json.dumps(PROFILE))
    for spec in profile["item_types"].values():
        del spec["fields"]["nivel_dificultad"]
    ws.exemplars_profile_path.write_text(json.dumps(profile), encoding="utf-8")
    assert _listing(ws)["difficulties"] == []


def test_a_hand_edited_profile_whose_modalities_disagree_offers_the_union(ws):
    # Normally one ladder. When somebody has edited one modality by hand, a rung that
    # exists in the bank still has to be selectable.
    profile = json.loads(json.dumps(PROFILE))
    profile["item_types"]["test"]["fields"]["nivel_dificultad"]["schema"]["enum"] = [
        "basico",
        "brutal",
    ]
    ws.exemplars_profile_path.write_text(json.dumps(profile), encoding="utf-8")
    assert [d["value"] for d in _listing(ws)["difficulties"]] == [
        "basico",
        "intermedio",
        "avanzado",
        "brutal",
    ]

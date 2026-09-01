"""Sorting the bank by difficulty, across modalities whose criteria differ.

The whole point of the shared ladder is that this order means something: two exercises of
different modalities sit on the same three rungs, so «easiest first» reads as one list
rather than as several interleaved scales. What is per-modality is the CRITERION, and the
criterion never reaches this sort.
"""

import json
from types import SimpleNamespace

import pytest

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
    "C003": {ITEM_TYPE_KEY: "escritura", "enunciado": "c", "nivel_dificultad": "intermedio"},
    "C004": {ITEM_TYPE_KEY: "test", "pregunta": "d", "nivel_dificultad": "avanzado"},
    "C005": {ITEM_TYPE_KEY: "escritura", "enunciado": "e"},
}


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path, "aula")
    workspace.instance_dir.mkdir(parents=True)
    workspace.exemplars_profile_path.write_text(json.dumps(PROFILE), encoding="utf-8")
    workspace.exemplars_bank_path.write_text(json.dumps(BANK), encoding="utf-8")
    return workspace


def _ids(ws, **kwargs) -> list[str]:
    result = route.listing(
        access=SimpleNamespace(ws=ws), order=kwargs.pop("order", "id"), page=1,
        page_size=50, **kwargs,
    )
    return [item["id"] for item in result["items"]]


def test_easiest_first_and_across_modalities(ws):
    assert _ids(ws, order="difficulty") == ["C002", "C003", "C001", "C004", "C005"]


def test_an_item_with_no_difficulty_lands_at_the_end(ws):
    # Not at the top: an item nobody classified is not the easiest one in the bank.
    assert _ids(ws, order="difficulty")[-1] == "C005"


def test_ties_keep_the_id_order_so_the_page_is_stable(ws):
    assert _ids(ws, order="difficulty")[2:4] == ["C001", "C004"]


def test_the_order_survives_a_modality_filter(ws):
    assert _ids(ws, order="difficulty", item_type="escritura") == ["C003", "C001", "C005"]


def test_the_listing_names_the_field_that_carries_it(ws):
    result = route.listing(access=SimpleNamespace(ws=ws), order="id", page=1, page_size=50)
    for summary in result["item_types"]:
        assert summary["difficulty_field"] == "nivel_dificultad"
        assert summary["difficulty_levels"] == ["basico", "intermedio", "avanzado"]


def test_a_bank_whose_profile_has_no_difficulty_still_sorts(ws):
    # Ordering by something nothing declares must degrade to the id order, not to a 500.
    profile = json.loads(json.dumps(PROFILE))
    for spec in profile["item_types"].values():
        del spec["fields"]["nivel_dificultad"]
    ws.exemplars_profile_path.write_text(json.dumps(profile), encoding="utf-8")
    assert _ids(ws, order="difficulty") == ["C001", "C002", "C003", "C004", "C005"]

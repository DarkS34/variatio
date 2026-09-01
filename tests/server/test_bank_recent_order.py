"""`order=recent` has no reader in the browser, and it is still an order this API serves.

The build's live feed — «Ejercicios que van saliendo» — was the only caller, and it was
removed on 2026-09-01 by explicit user request. The parameter stays for the same reason the
`concept` filter does: the bank listing is an API and not only a screen, and «newest first»
is a real question to ask of it. This file is what keeps it from being swept up as dead
code, so deleting the branch means deleting these tests on purpose rather than by accident.
"""

import json
from types import SimpleNamespace

import pytest

from server.routers import bank as route
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ITEM_TYPE_KEY

PROFILE = {
    "item_types": {
        "escritura": {
            "label": "Ejercicio",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "fields": {"enunciado": {"schema": {"type": "string"}}},
        }
    }
}

BANK = {
    f"C{n:03d}": {ITEM_TYPE_KEY: "escritura", "enunciado": f"ejercicio {n}"}
    for n in range(1, 6)
}


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path, "aula")
    workspace.instance_dir.mkdir(parents=True)
    workspace.exemplars_profile_path.write_text(json.dumps(PROFILE), encoding="utf-8")
    workspace.exemplars_bank_path.write_text(json.dumps(BANK), encoding="utf-8")
    return workspace


def _ids(ws, order: str) -> list[str]:
    result = route.listing(
        access=SimpleNamespace(ws=ws), order=order, page=1, page_size=50
    )
    return [item["id"] for item in result["items"]]


def test_recent_is_the_id_order_reversed(ws):
    # The ids are minted in extraction order, so the tail of that list IS the newest.
    assert _ids(ws, "recent") == ["C005", "C004", "C003", "C002", "C001"]
    assert _ids(ws, "id") == ["C001", "C002", "C003", "C004", "C005"]


def test_recent_pages_from_the_newest(ws):
    result = route.listing(
        access=SimpleNamespace(ws=ws), order="recent", page=1, page_size=2
    )
    assert [item["id"] for item in result["items"]] == ["C005", "C004"]
    assert result["total"] == 5

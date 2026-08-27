import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from server.editors import bank_edit
from server.routers import bank as route
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ITEM_TYPE_KEY

PROFILE = {
    "item_types": {
        "escritura_codigo": {
            "label": "Escritura de código",
            "description": "El alumno escribe el programa.",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "fields": {
                "enunciado": {
                    "schema": {"type": "string"},
                    "description": "El texto del ejercicio.",
                },
            },
        },
        "pregunta_test": {
            "label": "Pregunta tipo test",
            "description": "El alumno elige una opción.",
            "primary_field": "pregunta",
            "embed_fields": ["pregunta"],
            "fields": {
                "pregunta": {
                    "schema": {"type": "string"},
                    "description": "El texto de la pregunta.",
                },
            },
        },
    }
}

BANK = {
    "C001": {
        ITEM_TYPE_KEY: "escritura_codigo",
        "enunciado": "Recorre la lista",
        "source": "tema1",
        "concepts": ["Bucles"],
        "primary_concept": "Bucles",
    },
    "C002": {
        ITEM_TYPE_KEY: "escritura_codigo",
        "enunciado": "Invierte la lista",
        "source": "tema2",
        "concepts": [],
        "primary_concept": None,
    },
    "C003": {
        ITEM_TYPE_KEY: "pregunta_test",
        "pregunta": "¿Qué hace un bucle?",
        "source": "tema1",
        "concepts": ["Bucles"],
        "primary_concept": "Bucles",
    },
    "C004": {
        ITEM_TYPE_KEY: "pregunta_test",
        "pregunta": "¿Qué es una lista?",
        "source": "tema2",
        "concepts": ["Listas"],
        "primary_concept": "Listas",
    },
    "C005": {
        ITEM_TYPE_KEY: "pregunta_test",
        "pregunta": "¿Cuál se ejecuta primero?",
        "source": "tema3",
        "concepts": [],
        "primary_concept": None,
    },
}


@pytest.fixture
def ws(tmp_path):
    workspace = Workspace(tmp_path, "aula")
    workspace.instance_dir.mkdir(parents=True)
    _write(workspace.exemplars_profile_path, PROFILE)
    _write(workspace.exemplars_bank_path, BANK)
    return workspace


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _ids(result) -> list[str]:
    return [item["id"] for item in result["items"]]


def _listing(ws, **kwargs):
    return route.listing(
        access=SimpleNamespace(ws=ws),
        order=kwargs.pop("order", "id"),
        page=kwargs.pop("page", 1),
        page_size=kwargs.pop("page_size", 50),
        **kwargs,
    )


def test_without_a_modality_the_whole_bank_comes_back(ws):
    result = _listing(ws)
    assert _ids(result) == ["C001", "C002", "C003", "C004", "C005"]
    assert result["total"] == 5


def test_the_modality_filter_keeps_only_that_modality(ws):
    result = _listing(ws, item_type="pregunta_test")
    assert _ids(result) == ["C003", "C004", "C005"]
    assert result["total"] == 3


def test_the_modality_filter_intersects_the_search(ws):
    assert _ids(_listing(ws, q="lista")) == ["C001", "C002", "C004"]
    result = _listing(ws, item_type="escritura_codigo", q="lista")
    assert _ids(result) == ["C001", "C002"]
    assert result["total"] == 2


def test_the_modality_filter_intersects_the_source(ws):
    assert _ids(_listing(ws, source="tema1")) == ["C001", "C003"]
    assert _ids(_listing(ws, item_type="pregunta_test", source="tema1")) == ["C003"]


def test_the_modality_filter_intersects_the_untagged_ones(ws):
    assert _ids(_listing(ws, untagged=True)) == ["C002", "C005"]
    assert _ids(_listing(ws, item_type="escritura_codigo", untagged=True)) == ["C002"]


def test_the_options_and_their_counts_describe_the_bank_and_not_the_filter(ws):
    result = _listing(ws, item_type="escritura_codigo")
    assert [(t["key"], t["count"]) for t in result["item_types"]] == [
        ("escritura_codigo", 2),
        ("pregunta_test", 3),
    ]
    assert result["sources"] == ["tema1", "tema2", "tema3"]
    assert result["totals"] == {"items": 5, "tagged": 3, "untagged": 2}
    assert result["total"] == 2


def test_an_unknown_modality_is_a_readable_error(ws):
    with pytest.raises(HTTPException) as raised:
        _listing(ws, item_type="ejercicio_oral")
    assert raised.value.status_code == 422
    assert "ejercicio_oral" in raised.value.detail
    assert "escritura_codigo" in raised.value.detail


def test_the_filter_alone_would_have_answered_an_empty_page(ws):
    assert bank_edit.listing(ws, item_type="ejercicio_oral")["items"] == []


def test_the_concept_parameter_still_filters(ws):
    assert _ids(_listing(ws, concept="Bucles")) == ["C001", "C003"]
    assert _ids(_listing(ws, concept="Bucles", item_type="pregunta_test")) == ["C003"]

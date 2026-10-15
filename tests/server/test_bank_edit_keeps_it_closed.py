"""Editing an exercise of a closed bank keeps the bank closed, and the class's doors open.

Until 2026-10-14 every hand edit withdrew the bank's approval: a teacher correcting an erratum
in the middle of a course closed generating and the tutor to the whole class until they
pressed «Continuar» again. A closed bank is sealed again instead, as a retag is; a draft stays
a draft, and editing the types still reopens what comes after them.
"""

import json

import pytest

from server import approvals
from server.db import mirror
from server.editors import bank_edit, profile_edit
from variatio.core.workspace import Workspace

PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio de programación",
            "description": "El alumno escribe código.",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "general_generation_rules": ["El enunciado especifica la entrada y la salida."],
            "fields": {
                "enunciado": {"schema": {"type": "string"}, "description": "El texto."},
            },
        },
    }
}

GRAPH = {
    "concepts_by_domains": {"Fundamentos": ["Bucles", "Listas"]},
    "generic_non_taggable_concepts": [],
    "taggability_reviewed": True,
    "relations": [],
}


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setattr(mirror, "mirror_file", lambda ws, path: None)
    workspace = Workspace(tmp_path, "aula")
    workspace.artifacts_dir.mkdir(parents=True)
    _write(workspace.exemplars_profile_path, PROFILE)
    _write(workspace.kg_path, GRAPH)
    _write(
        workspace.exemplars_bank_path,
        {
            "C001": {"enunciado": "uno", "source": "tema1", "concepts": ["Bucles"]},
            "C002": {"enunciado": "dos", "source": "tema1", "concepts": ["Listas"]},
        },
    )
    return workspace


@pytest.fixture
def closed(ws):
    review = approvals.Approvals(ws)
    for artifact in approvals.ARTIFACTS:
        review.approve(artifact)
    assert review.generation_unlocked()
    return ws


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _status(ws) -> str:
    return approvals.Approvals(ws).state(approvals.EXEMPLARS_BANK)["status"]


@pytest.mark.parametrize(
    "edit",
    [
        lambda ws: bank_edit.patch_item(ws, "C001", {"enunciado": "uno, corregido"}),
        lambda ws: bank_edit.set_concepts(ws, "C001", ["Listas"], "Listas"),
        lambda ws: bank_edit.delete_item(ws, "C002"),
        lambda ws: bank_edit.add_item(ws, {"enunciado": "tres"}, "ejercicio", ["Bucles"]),
    ],
    ids=["patch", "concepts", "delete", "add"],
)
def test_an_edit_of_a_closed_bank_seals_it_again(closed, edit):
    before = approvals.Approvals(closed).state(approvals.EXEMPLARS_BANK)["hash"]
    edit(closed)

    state = approvals.Approvals(closed).state(approvals.EXEMPLARS_BANK)
    assert state["hash"] != before
    assert state["status"] == "approved"
    assert approvals.Approvals(closed).generation_unlocked()


def test_an_edit_of_a_draft_bank_leaves_it_a_draft(ws):
    review = approvals.Approvals(ws)
    review.approve(approvals.KNOWLEDGE_GRAPH)
    review.approve(approvals.EXEMPLARS_PROFILE)

    bank_edit.patch_item(ws, "C001", {"enunciado": "uno, corregido"})

    assert _status(ws) == "draft"
    assert not approvals.Approvals(ws).generation_unlocked()


def test_a_bank_closed_behind_types_reopened_is_not_sealed_by_an_edit(closed):
    approvals.Approvals(closed).reopen(approvals.EXEMPLARS_PROFILE)

    bank_edit.patch_item(closed, "C001", {"enunciado": "uno, corregido"})

    assert _status(closed) == "draft"


def test_editing_the_types_still_closes_the_doors(closed):
    profile_edit.save(closed, PROFILE)

    assert not approvals.Approvals(closed).generation_unlocked()

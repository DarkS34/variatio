"""Editing a concept without moving it between units leaves it where it was.

`_relocate` used to remove the name from its unit and append it, whatever the destination,
so every edit that did not change the unit put the concept last: marking one as not
serving as a label — a switch on its own row, pressed while reading down the list — sent
it to the bottom under the hand that pressed it. A rename did the same.

The three cases below are the whole contract: staying put keeps the index, a rename keeps
the index, and a real move still lands at the end of the destination.
"""

import pytest

from server.editors import kg_edit
from variatio.core.json_io import write_json
from variatio.core.workspace import Workspace

UNIT = "Unidad"
ORDER = ["Alfa", "Beta", "Gamma"]


@pytest.fixture
def ws(tmp_path):
    """A workspace whose curated graph holds one unit of three concepts, in order."""
    workspace = Workspace(root=tmp_path, slug="test")
    workspace.instance_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        workspace.kg_path,
        {
            "concepts_by_domains": {UNIT: list(ORDER), "Otra": []},
            "generic_non_taggable_concepts": [],
            "taggability_reviewed": True,
            "relations": {},
        },
    )
    return workspace


def units(workspace) -> dict:
    return kg_edit.raw(workspace)["concepts_by_domains"]


def test_marking_a_concept_not_taggable_leaves_it_in_place(ws):
    kg_edit.update_concept(ws, "Beta", taggable=False)
    assert units(ws)[UNIT] == ORDER
    assert kg_edit.raw(ws)["generic_non_taggable_concepts"] == ["Beta"]


def test_marking_it_taggable_again_leaves_it_in_place(ws):
    kg_edit.update_concept(ws, "Beta", taggable=False)
    kg_edit.update_concept(ws, "Beta", taggable=True)
    assert units(ws)[UNIT] == ORDER
    assert kg_edit.raw(ws)["generic_non_taggable_concepts"] == []


def test_a_rename_keeps_the_position(ws):
    kg_edit.update_concept(ws, "Beta", new_name="Beta prima")
    assert units(ws)[UNIT] == ["Alfa", "Beta prima", "Gamma"]


def test_moving_to_another_unit_still_appends_there(ws):
    kg_edit.update_concept(ws, "Beta", domain="Otra")
    assert units(ws)[UNIT] == ["Alfa", "Gamma"]
    assert units(ws)["Otra"] == ["Beta"]

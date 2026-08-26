import json
from pathlib import Path

import pytest

from variatio.variatio import assumed_known, forbidden

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "curriculum_sets.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))


def _by_name() -> list:
    return [pytest.param(case, id=case["name"]) for case in CASES]


@pytest.mark.parametrize("case", _by_name())
def test_assumed_known_matches_the_shared_table(case):
    assert assumed_known(case["closure"], case["curriculum"]) == case["assumed_known"]


@pytest.mark.parametrize("case", _by_name())
def test_forbidden_matches_the_shared_table(case):
    assert forbidden(case["closure"], case["curriculum"]) == case["forbidden"]


@pytest.mark.parametrize("case", _by_name())
def test_the_table_only_names_closure_members(case):
    closure = set(case["closure"])
    assert set(case["assumed_known"]) <= closure
    assert set(case["forbidden"]) <= closure


@pytest.mark.parametrize("case", _by_name())
def test_the_table_is_a_partition_whenever_a_curriculum_is_given(case):
    if not case["curriculum"]:
        return
    assert set(case["assumed_known"]).isdisjoint(case["forbidden"])
    assert set(case["assumed_known"]) | set(case["forbidden"]) == set(case["closure"])


def test_the_table_covers_every_shape():
    names = {case["name"] for case in CASES}
    assert {
        "null curriculum narrows nothing",
        "empty curriculum is a missing one",
        "full overlap",
        "no overlap",
        "partial overlap",
        "a covered concept outside the closure appears in neither list",
        "outputs keep closure order",
    } <= names


def test_the_python_side_keeps_closure_order():
    closure = ["Variable", "Función"]
    assert assumed_known(closure, None) == ["Variable", "Función"]
    assert forbidden(closure, None) == ["Variable", "Función"]


def test_the_two_operations_are_not_the_same():
    closure = ["Función", "Variable"]
    curriculum = ["Variable"]
    assert assumed_known(closure, curriculum) == ["Variable"]
    assert forbidden(closure, curriculum) == ["Función"]

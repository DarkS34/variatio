import json

from variatio.exemplars_bank import tagging as tagger_module
from variatio.exemplars_bank.tagging import ConceptTagger

NAMES = ["A", "B", "C", "D", "E", "F"]


def _parse(answer: dict) -> dict | None:
    return ConceptTagger._parse_and_validate(None, json.dumps(answer), NAMES)


def test_the_primary_joins_the_concepts_when_the_model_leaves_it_out():
    assert _parse({"primary_concept": "C", "concepts": ["A", "B"]}) == {
        "primary_concept": "C",
        "concepts": ["C", "A", "B"],
    }


def test_more_than_four_concepts_are_cut_to_four_keeping_the_primary():
    parsed = _parse({"primary_concept": "F", "concepts": NAMES})
    assert parsed["concepts"] == ["F", "A", "B", "C"]
    assert tagger_module.MAX_CONCEPTS == len(parsed["concepts"])

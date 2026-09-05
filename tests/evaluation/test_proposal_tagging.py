"""What the graph says each proposal is about, and what it should not have used.

The line under a revealed card is only worth reading if the set behind it is the one the
system arm was actually told to avoid, so what is pinned here is that identity: `off_limits`
is `variatio.runtime.generator.forbidden` over the dependent closure and nothing of its own — read
under the same rule `checks.run` reads it: any MENTION when a curriculum was given, only
the PRACTISED concept when none was (2026-09-04).
"""

import json

import pytest

from evaluation import FAILED, OK, ArmResult, Commission
from evaluation.run import _tag, off_limits
from variatio.core import progress
from variatio.instance.knowledge_graph import KnowledgeGraph

from ..conftest import CHAIN_GRAPH, PREREQUISITE


class _ItemType:
    """The one method the pass asks a modality for: the text the tagger reads."""

    def embed_text(self, item: dict, field_max_chars: int = 0) -> str:
        return str(item.get("enunciado") or "")


class _Tagger:
    """A tagger that answers from a table and records what it was asked."""

    def __init__(self, answers: dict[str, dict], fails: bool = False):
        self.answers = answers
        self.fails = fails
        self.seen: list[str] = []

    def tag(self, statement: str) -> dict:
        self.seen.append(statement)
        if self.fails:
            raise RuntimeError("el motor no responde")
        return self.answers.get(statement, {"concepts": [], "primary_concept": None})


class _Generator:
    prerequisite_relation = PREREQUISITE


class _Context:
    def __init__(self, graph: KnowledgeGraph, tagger: _Tagger):
        self.knowledge_graph = graph
        self.tagger = tagger
        self.generator = _Generator()


@pytest.fixture
def graph(tmp_path) -> KnowledgeGraph:
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return KnowledgeGraph(str(path))


def _result(arm: str, statement: str | None, checks: dict | None = None) -> ArmResult:
    return ArmResult(
        arm=arm,
        status=OK if statement else FAILED,
        item={"enunciado": statement} if statement else None,
        raw_response="",
        prompt="",
        model="m",
        provider="p",
        exemplar_ids=[],
        elapsed_ms=1,
        checks=checks,
    )


def test_out_of_bounds_is_the_whole_downstream_closure_with_no_curriculum(graph):
    commission = Commission(concepts=["Función"], item_type="ejercicio")
    assert off_limits(_Context(graph, _Tagger({})), commission) == [
        "Memoización",
        "Recursividad",
    ]


def test_the_curriculum_is_subtracted_from_it(graph):
    commission = Commission(
        concepts=["Función"],
        item_type="ejercicio",
        curriculum=["Variable", "Función", "Recursividad"],
    )
    assert off_limits(_Context(graph, _Tagger({})), commission) == ["Memoización"]


WITH_CURRICULUM = ["Variable", "Función"]


def test_every_proposal_with_an_item_is_tagged_and_its_trespasses_named(graph):
    tagger = _Tagger(
        {
            "a": {"concepts": ["Función", "Memoización"], "primary_concept": "Función"},
            "b": {"concepts": ["Función", "Variable"], "primary_concept": "Función"},
        }
    )
    results = {
        "naive": _result("naive", "a"),
        "rag": _result("rag", "b"),
        "system": _result("system", None),
    }
    _tag(
        _Context(graph, tagger),
        _ItemType(),
        Commission(concepts=["Función"], item_type="ejercicio", curriculum=WITH_CURRICULUM),
        results,
    )

    assert results["naive"].tagging == {
        "concepts": ["Función", "Memoización"],
        "primary": "Función",
        "rule": "mentions",
        "off_limits": ["Memoización"],
    }
    # A prerequisite is not a trespass: what is behind the target is what the item may lean on.
    assert results["rag"].tagging["off_limits"] == []
    # Nothing was produced, so there is nothing to read: an arm that failed is not tagged.
    assert results["system"].tagging is None


def test_a_concept_the_text_names_counts_even_when_the_tagger_did_not_tag_it(graph):
    """The lexical half of the union — `checks.forbidden_mentions`, the pipeline's own rule.

    Without it the line contradicts the system's own «menciona lo no impartido» flag on the
    same screen, and a proposal that names a later concept in passing reads as clean.
    """
    tagger = _Tagger(
        {"habla de Memoización": {"concepts": ["Función"], "primary_concept": "Función"}}
    )
    results = {
        "naive": _result("naive", "habla de Memoización"),
        "rag": _result("rag", None),
        "system": _result("system", None),
    }
    _tag(
        _Context(graph, tagger),
        _ItemType(),
        Commission(concepts=["Función"], item_type="ejercicio", curriculum=WITH_CURRICULUM),
        results,
    )

    assert results["naive"].tagging["concepts"] == ["Función"]
    assert results["naive"].tagging["off_limits"] == ["Memoización"]


def test_without_a_curriculum_only_what_is_practised_counts(graph):
    """Practicar ≠ usar, on the far side of the scaffolding (2026-09-04).

    Nobody said what the class has seen, so the closure is the graph's guess and a mention
    holds nothing against a proposal; what does is the tagger's PRIMARY concept lying after
    the target. Measured on the reference bank: the teacher's own exercises on «Condición
    lógica» use `if`, `else` and `while`, so the mention rule flagged exactly the exercises
    the course itself sets.
    """
    tagger = _Tagger(
        {
            # Names and is tagged with Memoización, but practises Función: clean.
            "usa Memoización": {
                "concepts": ["Función", "Memoización"],
                "primary_concept": "Función",
            },
            # Practises Recursividad, which comes after Función: that is the trespass.
            "b": {"concepts": ["Recursividad", "Función"], "primary_concept": "Recursividad"},
        }
    )
    results = {
        "naive": _result("naive", "usa Memoización"),
        "rag": _result("rag", "b"),
        "system": _result("system", None),
    }
    _tag(
        _Context(graph, tagger),
        _ItemType(),
        Commission(concepts=["Función"], item_type="ejercicio"),
        results,
    )

    assert results["naive"].tagging["rule"] == "practises"
    assert results["naive"].tagging["off_limits"] == []
    assert results["rag"].tagging["off_limits"] == ["Recursividad"]


def test_the_system_arm_reuses_the_annotation_its_own_checks_already_paid_for(graph):
    tagger = _Tagger({})
    checks = {"tagger": {"primary": "Función", "concepts": ["Función", "Recursividad"]}}
    results = {
        "naive": _result("naive", None),
        "rag": _result("rag", None),
        "system": _result("system", "a", checks=checks),
    }
    _tag(
        _Context(graph, tagger),
        _ItemType(),
        Commission(concepts=["Función"], item_type="ejercicio", curriculum=WITH_CURRICULUM),
        results,
    )

    assert tagger.seen == []
    assert results["system"].tagging == {
        "concepts": ["Función", "Recursividad"],
        "primary": "Función",
        "rule": "mentions",
        "off_limits": ["Recursividad"],
    }


def test_a_tagger_that_fails_leaves_that_proposal_unread_and_keeps_the_session(graph):
    results = {
        "naive": _result("naive", "a"),
        "rag": _result("rag", "b"),
        "system": _result("system", None),
    }
    _tag(
        _Context(graph, _Tagger({}, fails=True)),
        _ItemType(),
        Commission(concepts=["Función"], item_type="ejercicio"),
        results,
    )
    assert all(result.tagging is None for result in results.values())


def test_the_pass_is_cancellable(graph):
    class _Stopped:
        def emit(self, kind: str, payload: dict) -> None: ...

        def should_cancel(self) -> bool:
            return True

    results = {
        "naive": _result("naive", "a"),
        "rag": _result("rag", None),
        "system": _result("system", None),
    }
    with progress.emitting(_Stopped()), pytest.raises(progress.Cancelled):
        _tag(
            _Context(graph, _Tagger({})),
            _ItemType(),
            Commission(concepts=["Función"], item_type="ejercicio"),
            results,
        )

"""What a run resolved travels with every item it accepts, so the caller can keep it.

Over the three-hop chain `Variable ← Función ← Recursividad ← Memoización`, the only shape
where a one-hop reading and the transitive closure differ, targeting Recursividad: without a
curriculum the whole prerequisite closure is assumed and everything downstream is "viene
después"; with one, the first is INTERSECTED with it and the second has it SUBTRACTED.
"""

from types import SimpleNamespace

import pytest

from variatio import wording as wording_sets
from variatio.runtime import checks, generator as generator_module, screening
from variatio.runtime.generator import NEIGHBOUR, VariantGenerator

from ..conftest import ES

STATEMENT = "Escribe una función recursiva que calcule el factorial de un número entero."


class _Describer:
    def collect_relations(self, concept):
        return {}


class _Embedder:
    concept_descriptions = {
        "Variable": "Un nombre ligado a un valor.",
        "Función": "Un bloque de código con nombre.",
        "Recursividad": "Una función que se llama a sí misma.",
        "Memoización": "Guardar resultados ya calculados.",
    }
    describer = _Describer()

    def rank_exemplars(self, concepts, exemplar_ids):
        return list(exemplar_ids)


def _generator(graph, profile, context, bank: dict) -> VariantGenerator:
    generator = object.__new__(VariantGenerator)
    generator.knowledge_graph = graph
    generator.exemplars_bank = bank
    generator.embedder = _Embedder()
    generator.exemplars_profile = profile
    generator.prompts = ES
    generator._wording = wording_sets.beside(ES)
    generator.prerequisite_relation = "tiene como prerrequisito"
    generator.content_context = context
    generator.generator_model = "el-escritor"
    generator.repair_model = "el-reparador"
    generator.tagger = None
    generator.max_repair_attempts = 0
    generator.max_few_shot = 3
    generator.taggable_concepts = set(graph.taggable_concepts)
    return generator


@pytest.fixture
def answering(monkeypatch):
    """Answer every generating call with one valid item, and record the prompts it got."""
    prompts: list[str] = []

    def generate_stream(model, prompt, **kwargs):
        prompts.append(prompt)
        return SimpleNamespace(
            thinking="pensado",
            response=f'{{"enunciado": "{STATEMENT}", "nivel_dificultad": "basico"}}',
        )

    monkeypatch.setattr(generator_module.inference, "generate_stream", generate_stream)
    return prompts


def _bank() -> dict:
    return {
        "ex1": {
            "item_type": "ejercicio",
            "enunciado": "Suma recursiva de una lista",
            "concepts": ["Recursividad"],
            "primary_concept": "Recursividad",
            "_source": "tema3.pdf",
        },
        "ex2": {
            "item_type": "ejercicio",
            "enunciado": "Define una función que devuelva el doble",
            "concepts": ["Función"],
            "primary_concept": "Función",
        },
    }


def _run(generator, **kwargs):
    return generator.generate(
        concepts=["Recursividad"],
        item_type="ejercicio",
        check=False,
        ruling=screening.Ruling((), True),
        think="high",
        **kwargs,
    )


def test_without_a_curriculum_the_closures_are_whole(graph, profile, context, answering):
    [result] = _run(_generator(graph, profile, context, _bank()))

    provenance = result.provenance
    assert provenance["targets"] == ["Recursividad"]
    assert provenance["curriculum"] is None
    assert sorted(provenance["assumed_known"]) == ["Función", "Variable"]
    assert provenance["forbidden"] == ["Memoización"]
    assert provenance["closure_rule"] == checks.RULE_PRACTISES


def test_a_curriculum_intersects_one_closure_and_subtracts_from_the_other(
    graph, profile, context, answering
):
    curriculum = ["Función", "Recursividad", "Memoización"]
    [result] = _run(_generator(graph, profile, context, _bank()), curriculum=curriculum)

    provenance = result.provenance
    assert provenance["curriculum"] == curriculum
    # Variable is a prerequisite the course has not covered, so it is not assumed known...
    assert provenance["assumed_known"] == ["Función"]
    # ...and Memoización is downstream but covered, so it is no longer forbidden.
    assert provenance["forbidden"] == []
    assert provenance["closure_rule"] == checks.RULE_MENTIONS


def test_the_exemplars_shown_are_kept_by_id_origin_and_public_fields(
    graph, profile, context, answering
):
    [result] = _run(_generator(graph, profile, context, _bank()))

    few_shot = {entry["id"]: entry for entry in result.provenance["few_shot"]}
    assert few_shot["ex1"]["origin"] == "primary"
    assert few_shot["ex2"]["origin"] == NEIGHBOUR
    assert "_source" not in few_shot["ex1"]["item"]
    assert few_shot["ex1"]["item"]["enunciado"] == "Suma recursiva de una lista"


def test_the_writer_its_effort_the_ruling_and_the_reminder_are_kept(
    graph, profile, context, answering
):
    ruling = screening.Ruling(
        (screening.Request(text="una panadería", slot="ambito", owner=None, term=None),), True
    )
    [result] = _generator(graph, profile, context, _bank()).generate(
        concepts=["Recursividad"],
        item_type="ejercicio",
        check=False,
        ruling=ruling,
        think="high",
        model="el-otro",
        avoid=["un enunciado ya guardado"],
    )

    provenance = result.provenance
    assert provenance["model"] == "el-otro"
    assert provenance["effort"] == "high"
    assert provenance["item_type"] == "ejercicio"
    assert provenance["avoid"] == ["un enunciado ya guardado"]
    assert provenance["ruling"] == {
        "checked": True,
        "requests": [{"text": "una panadería", "slot": "ambito", "owner": None, "term": None}],
    }


def test_each_item_carries_the_prompt_it_was_written_from(graph, profile, context, answering):
    results = _run(_generator(graph, profile, context, _bank()), n=2)

    assert [r.prompt for r in results] == answering
    assert "Recursividad" in results[0].prompt
    # The second prompt also asks not to repeat the first statement.
    assert STATEMENT in results[1].prompt
    assert results[0].provenance == results[1].provenance
    assert results[0].provenance is not results[1].provenance

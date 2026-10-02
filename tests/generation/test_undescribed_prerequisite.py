"""A prerequisite with no description is described by its relations, not dropped and not fatal.

A bare name is not prior knowledge the model can reason about, so the prompt falls back to
what the graph says about it. That fallback used to raise `NameError` — a static method
reaching for `self` — so one missing description failed a whole generate job.
"""

from variatio import wording as wording_sets
from variatio.runtime.generator import VariantGenerator

from ..conftest import ES


class _Describer:
    def collect_relations(self, concept):
        return {"tiene como prerrequisito": ["Variable"], "se relaciona con": []}


class _Embedder:
    concept_descriptions = {"Variable": "Un nombre ligado a un valor."}
    describer = _Describer()


def _generator() -> VariantGenerator:
    generator = object.__new__(VariantGenerator)
    generator.embedder = _Embedder()
    generator._wording = wording_sets.beside(ES)
    return generator


def test_an_undescribed_prerequisite_is_described_by_its_relations():
    block = _generator()._format_prerequisites(["Función"])

    assert block == "- **Función**: Sin descripción; en el grafo tiene como prerrequisito Variable."


def test_a_described_prerequisite_keeps_its_description():
    block = _generator()._format_prerequisites(["Variable"])

    assert block == "- **Variable**: Un nombre ligado a un valor."


def test_a_concept_with_neither_is_left_as_its_name():
    generator = _generator()
    generator.embedder.describer = type("Bare", (), {"collect_relations": lambda self, c: {}})()

    assert generator._format_prerequisites(["Suelto"]) == "- **Suelto**"

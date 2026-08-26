import json

import pytest

from variant_generator import admissibility
from variant_generator.core import cerebras_budget
from variant_generator.instance.content_context import ContentContext
from variant_generator.instance.exemplars_profile import ExemplarsProfile
from variant_generator.instance.knowledge_graph import KnowledgeGraph

CHAIN_GRAPH = {
    "concepts_by_domains": {
        "Fundamentos": ["Variable", "Función"],
        "Avanzado": ["Recursividad", "Memoización", "Notación asintótica"],
    },
    "generic_non_taggable_concepts": ["Notación asintótica"],
    "relations": [
        {
            "details": {
                "key": "prerrequisito",
                "verbose": "tiene como prerrequisito",
                "directed": True,
                "acyclic": True,
                "use_in_embedding": True,
            },
            "relations_data": {
                "Función": ["Variable"],
                "Recursividad": ["Función"],
                "Memoización": ["Recursividad"],
            },
        }
    ],
}

PREREQUISITE = "tiene como prerrequisito"


# THE ONE AUTOUSE FIXTURE, and it exists to stop a test spending real money's worth of
# budget. `CerebrasEngine` records every call in a ledger at the project root, so the engine
# tests — which answer a simulated transport — charged six phantom requests to the
# installation's own Cerebras budget and the panel then reported them as spent.
@pytest.fixture(autouse=True)
def _isolated_cerebras_ledger(tmp_path):
    cerebras_budget.use(tmp_path / "cerebras_budget.json")
    yield
    cerebras_budget.use(None)


@pytest.fixture
def chain_graph_path(tmp_path):
    path = tmp_path / "knowledge_graph.json"
    path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    return path


PROFILE = {
    "item_types": {
        "ejercicio": {
            "label": "Ejercicio de programación",
            "description": "El alumno escribe código.",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "general_generation_rules": ["El enunciado especifica la entrada y la salida."],
            "fields": {
                "enunciado": {"schema": {"type": "string"}, "description": "El texto del ejercicio."},
                "nivel_dificultad": {
                    "schema": {"enum": ["basico", "intermedio", "avanzado"]},
                    "description": "Grado de exigencia. 'basico': una sola operación.",
                    "decided_by": "user",
                },
            },
        },
        "analisis": {
            "label": "Análisis de código",
            "description": "El alumno predice la salida.",
            "primary_field": "enunciado",
            "embed_fields": ["enunciado"],
            "general_generation_rules": ["El enunciado usa verbos de análisis."],
            "fields": {
                "enunciado": {"schema": {"type": "string"}, "description": "La pregunta."},
            },
        },
    }
}

CONTEXT = {
    "subject": "Programación en Python",
    "educational_level": "primer curso de grado",
    "language_of_instruction": "castellano",
}


@pytest.fixture
def profile(tmp_path):
    path = tmp_path / "exemplars_profile.json"
    path.write_text(json.dumps(PROFILE, ensure_ascii=False), encoding="utf-8")
    return ExemplarsProfile(path)


@pytest.fixture
def context():
    return ContentContext(dict(CONTEXT))


@pytest.fixture
def graph(chain_graph_path):
    return KnowledgeGraph(chain_graph_path)


@pytest.fixture
def owners_for(graph, profile, context):
    def build(targets=("Recursividad",), item_type="ejercicio"):
        return admissibility.owners(
            graph, profile.item_type(item_type), profile, context, list(targets)
        )

    return build

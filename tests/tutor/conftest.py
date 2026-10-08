"""A workspace's context the tutor can run against without a model or an index.

The graph is the suite's three-hop chain; the embedder scores by keyword so a test decides
which concept a message is about by what it writes; the engine answers from a script, one
callable per kind of call, so a test states what the model said and checks what the tutor
did with it.
"""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from ..conftest import CHAIN_GRAPH, CONTEXT, ES, PREREQUISITE, PROFILE
from variatio.core import inference
from variatio.core.workspace import Workspace
from variatio.loaders.content_context import ContentContext
from variatio.loaders.exemplars_profile import ExemplarsProfile
from variatio.loaders.knowledge_graph import KnowledgeGraph

CONCEPTS = [c for listed in CHAIN_GRAPH["concepts_by_domains"].values() for c in listed]

SOURCES = {
    "documents": ["apuntes.pdf"],
    "units": [
        {"name": "Fundamentos", "heading": "Tema 1 Fundamentos", "chunk": 1},
        {"name": "Avanzado", "heading": "Tema 2 Avanzado", "chunk": 2},
    ],
    "definitions": {"Recursividad": "Una función que se llama a sí misma."},
    "concepts": {
        "Recursividad": [
            {
                "document": "apuntes.pdf",
                "location": "Tema 2 Avanzado > Recursividad",
                "text": "Una función recursiva necesita un caso base y reduce el problema en cada llamada.",
            }
        ],
        "Función": [
            {
                "document": "apuntes.pdf",
                "location": "Tema 1 Fundamentos > Funciones",
                "text": "Una función recibe sus datos por parámetro y devuelve un valor.",
            }
        ],
    },
}

BANK = {
    "C001": {
        "item_type": "ejercicio",
        "enunciado": "Escribe una función recursiva que calcule el factorial de n.",
        "nivel_dificultad": "intermedio",
        "source": "Hoja 2",
        "concepts": ["Recursividad", "Función"],
        "primary_concept": "Recursividad",
    },
    "C002": {
        "item_type": "ejercicio",
        "enunciado": "Escribe una función recursiva que sume los números de 1 a n.",
        "nivel_dificultad": "basico",
        "source": "Hoja 1",
        "concepts": ["Recursividad"],
        "primary_concept": "Recursividad",
    },
}


def vector_for(text: str) -> np.ndarray:
    """Embed by keyword: one axis per concept, plus one the bank's first statement owns."""
    folded = text.lower()
    axes = [
        1.0 if name.lower()[:6] in folded else 0.0 for name in CONCEPTS
    ] + [1.0 if "factorial" in folded else 0.0, 0.1]
    vector = np.array(axes, dtype=np.float32)
    return vector / np.linalg.norm(vector)


class FakeEmbedder:
    """Scores concepts and bank items by the keyword axes above."""

    similarity_threshold = 0.4

    def __init__(self):
        self.concepts_index = {name: vector_for(name) for name in CONCEPTS}
        self.concept_descriptions = {name: f"Descripción de {name}." for name in CONCEPTS}
        self.exemplars_bank_index = {
            item_id: vector_for(item["enunciado"]) for item_id, item in BANK.items()
        }

    def embed_query(self, text):
        return vector_for(text)

    def embed_document(self, text):
        return vector_for(text)

    def concept_scores(self, vector):
        return {name: float(np.dot(vector, own)) for name, own in self.concepts_index.items()}


# The suite's profile, with the solution field a real exercise modality declares: the
# criteria builder reads the bank's solutions for the conventions they show.
TUTOR_PROFILE = json.loads(json.dumps(PROFILE))
TUTOR_PROFILE["item_types"]["ejercicio"]["fields"]["solucion"] = {
    "schema": {"type": ["string", "null"]},
    "description": "La solución del docente.",
}


@pytest.fixture
def tutor_context(tmp_path):
    graph_path = tmp_path / "knowledge_graph.json"
    graph_path.write_text(json.dumps(CHAIN_GRAPH, ensure_ascii=False), encoding="utf-8")
    profile_path = tmp_path / "exemplars_profile.json"
    profile_path.write_text(json.dumps(TUTOR_PROFILE, ensure_ascii=False), encoding="utf-8")
    return SimpleNamespace(
        knowledge_graph=KnowledgeGraph(graph_path),
        content_context=ContentContext(dict(CONTEXT)),
        exemplars_profile=ExemplarsProfile(profile_path),
        exemplars_bank=json.loads(json.dumps(BANK)),
        embedder=FakeEmbedder(),
        generator=SimpleNamespace(prerequisite_relation=PREREQUISITE),
        workspace=Workspace(tmp_path / "ws", slug="ws"),
        prompts=ES,
        language="es",
    )


class ScriptedEngine:
    """Answers each call from a script keyed by what kind of call it is.

    `classify` answers a call whose grammar names the kinds, `reply` one made under the
    method, `other` anything else; each is a list consumed in order, the last one repeating.
    """

    def __init__(self, **script):
        self.script = {key: list(value) for key, value in script.items()}
        self.calls: list[dict] = []

    def __call__(self, *, model, prompt, think=None, system=None, format=None, **kwargs):
        if system:
            kind = "reply"
        elif isinstance(format, dict) and "kind" in (format.get("properties") or {}):
            kind = "classify"
        elif "Clasifica el último mensaje" in prompt:
            kind = "classify"
        else:
            kind = "other"
        self.calls.append({"kind": kind, "prompt": prompt, "system": system, "format": format})
        answers = self.script.get(kind) or ['{"kind": "theory"}']
        answer = answers.pop(0) if len(answers) > 1 else answers[0]
        if isinstance(answer, inference.GenerationResponse):
            return answer
        return inference.GenerationResponse(response=answer)


@pytest.fixture
def engine(monkeypatch):
    """Install a scripted engine and a guardrail that lets everything through."""
    from variatio.runtime import screening

    holder = {}

    def install(**script):
        scripted = ScriptedEngine(**script)
        holder["engine"] = scripted
        monkeypatch.setattr(inference, "generate", scripted)
        monkeypatch.setattr(inference, "remote_models", lambda: frozenset())
        monkeypatch.setattr(
            screening.guardrail,
            "check",
            lambda text, criteria=None, wording=None: screening.Verdict(blocked_by=None, checked=True),
        )
        return scripted

    return install

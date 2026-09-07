import json
import os

import pytest

from variatio import prompts
from variatio.runtime import screening
from variatio.core import cerebras_budget
from variatio.instance.content_context import ContentContext
from variatio.instance.exemplars_profile import ExemplarsProfile
from variatio.instance.knowledge_graph import KnowledgeGraph

# The Spanish set, which is what every measurement in this suite was taken against.
# A test that is ABOUT the two languages resolves its own with `prompts.of`.
ES = prompts.of("es")

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


# THREE AUTOUSE FIXTURES, and all three are here for the same reason: the suite runs inside
# the installation itself — its `.env`, its `workspaces/` — so whatever resolves a default
# resolves PRODUCTION.
#
# The first stops a test spending real money's worth of budget. `CerebrasEngine` records
# every call in a ledger at the project root, so the engine tests — which answer a simulated
# transport — charged six phantom requests to the installation's own Cerebras budget and the
# panel then reported them as spent.
@pytest.fixture(autouse=True)
def _isolated_cerebras_ledger(tmp_path):
    cerebras_budget.use(tmp_path / "cerebras_budget.json")
    yield
    cerebras_budget.use(None)


# The second stops a test reading Cerebras' catalogue over the network. Routing asks the
# catalogue — every model the API lists is served remotely — so a hybrid engine built by any
# test would call `/models` with the installation's own key, and the lane tests would then
# measure the real catalogue instead of the routing list they set up. The two tests of
# `known_models` itself restore the real method on their own instance.
@pytest.fixture(autouse=True)
def _no_cerebras_catalogue(monkeypatch):
    from variatio.core import cerebras

    monkeypatch.setattr(cerebras.CerebrasEngine, "known_models", lambda self: frozenset())


# The third stops a test writing into the installation's own instances. Every slug a test
# invents resolves under `paths.WORKSPACES_DIR`: a `Job` carrying an invented workspace has
# the bus mkdir `workspaces/<slug>/instance/.runs/` and append its event log there.
# `paths.LOGS_DIR` travels with it for the same reason — a job also opens
# `logs/<slug>/jobs.log`.
#
# Redirected rather than cleaned up afterwards: deleting directories under `workspaces/` is
# the one operation this project already treats as unforgiving. Everything reads the module
# attribute at call time, so patching it is enough; the `corpus` tests are unaffected, since
# they open a workspace by relative path to measure the instance itself.
#
# SESSION-scoped, unlike the other two, and that is the whole reason it works: a host that
# publishes from a worker thread outlives a per-test redirect, so the tail of a run lands
# outside the tree the fixture had moved. The environment variable travels beside the
# attribute so a subprocess reads the same root.
@pytest.fixture(autouse=True, scope="session")
def _isolated_workspaces(tmp_path_factory):
    from variatio.core import paths

    root = tmp_path_factory.mktemp("workspaces")
    logs = tmp_path_factory.mktemp("logs")
    previous, previous_env = paths.WORKSPACES_DIR, os.environ.get("WORKSPACES_DIR")
    previous_logs, previous_logs_env = paths.LOGS_DIR, os.environ.get("VARIATIO_LOGS_DIR")
    paths.WORKSPACES_DIR = root
    paths.LOGS_DIR = logs
    os.environ["WORKSPACES_DIR"] = str(root)
    os.environ["VARIATIO_LOGS_DIR"] = str(logs)
    yield
    paths.WORKSPACES_DIR = previous
    paths.LOGS_DIR = previous_logs
    for name, value in (("WORKSPACES_DIR", previous_env), ("VARIATIO_LOGS_DIR", previous_logs_env)):
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


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
        return screening.owners(
            graph, profile.item_type(item_type), profile, context, list(targets)
        )

    return build

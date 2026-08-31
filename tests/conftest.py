import json
import os

import pytest

from variatio import admissibility, prompts
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
# the installation itself — its `.env`, its database, its `workspaces/` — so whatever
# resolves a default resolves PRODUCTION.
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


# The second stops a test writing to the production database. `session.database_url()` reads
# `DATABASE_URL`, `.env` supplies a real one, and nothing under `tests/` overrode it — so a
# test reaching `session_scope()` without meaning to opened a transaction against the live
# Postgres. One did, on 2026-08-28, and left an orphan row in `workspaces`.
#
# A throwaway SQLite file rather than a refusal: a test that genuinely wants a database gets
# a working empty one, and a test that never meant to touch it fails on the missing schema
# instead of quietly succeeding against real data. Tests that build their own engine are
# unaffected, and the import is inside the function so a runtime-only checkout without the
# `server` extra can still collect this file.
@pytest.fixture(autouse=True)
def _isolated_database(tmp_path, monkeypatch):
    from server.db import session

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    session.reset()
    yield
    session.reset()


# The third stops a test writing into the installation's own instances. `paths.WORKSPACES_DIR`
# is the checkout's `workspaces/`, and every slug a test invents resolves under it: a `Job`
# carrying `workspace="aula"` had the bus mkdir `workspaces/aula/instance/.runs/` and append
# its event log there, so a full run left two invented instances sitting beside the real ones.
# `paths.LOGS_DIR` travels with it for exactly the same reason: since 2026-08-31 a job also
# opens `logs/<slug>/jobs.log`, and an invented slug would leave a directory of its own there.
#
# Redirected rather than cleaned up afterwards: deleting directories under `workspaces/` is
# the one operation this project already treats as unforgiving, and a suite that never
# reaches the real tree needs no such pass. Everything reads the module attribute at call
# time, so patching it is enough. The `corpus` tests are unaffected — they open
# `workspaces/default/` by relative path, deliberately measuring the shipped instance.
#
# SESSION-scoped, unlike the other two, and that is the whole reason it works: a `JobRunner`
# publishes from a worker thread, and with a per-test redirect the last events of a job
# outlived the fixture that had moved the tree — six files still landed in the real
# `workspaces/` on a full run. The environment variable travels beside the attribute so a
# subprocess reads the same root.
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
        return admissibility.owners(
            graph, profile.item_type(item_type), profile, context, list(targets)
        )

    return build

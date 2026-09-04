"""The concepts a course has actually covered, per workspace.

Host state rather than an artifact (`instance/.curriculum.json`, gitignored), because two
courses over one graph disagree about it. It is validated against the graph on every read,
not on write alone, so a rename or a deletion surfaces as a named casualty instead of a
silent shrink.
"""

import json
from datetime import datetime, timezone

from variatio.core.workspace import Workspace
from variatio.instance import locale
from variatio.instance.knowledge_graph import KnowledgeGraph

from . import storage


def _read(ws: Workspace) -> dict:
    """Read the stored list, treating a missing or corrupt file as an empty one."""
    if not ws.curriculum_path.exists():
        return {"concepts": [], "updated_at": None}
    try:
        with ws.curriculum_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"concepts": [], "updated_at": None}
    stored = data.get("concepts")
    return {
        "concepts": stored if isinstance(stored, list) else [],
        "updated_at": data.get("updated_at"),
    }


def load(ws: Workspace, graph: KnowledgeGraph) -> dict:
    """Partition the stored list into concepts the graph still holds and `dropped` ones.

    An empty list is not short-circuited: emptying a curriculum is a save, so it keeps its
    timestamp.
    """
    data = _read(ws)
    existing = set(graph.all_concepts)
    kept = sorted({c for c in data["concepts"] if c in existing})
    dropped = sorted({c for c in data["concepts"] if c not in existing})
    return {"concepts": kept, "updated_at": data["updated_at"], "dropped": dropped}


def save(ws: Workspace, concepts: list[str], graph: KnowledgeGraph) -> dict:
    """Store the concepts the graph knows about and hand back the reloaded state."""
    existing = set(graph.all_concepts)
    kept = sorted({c for c in concepts if c in existing})
    storage.write_json(
        ws.curriculum_path,
        {"concepts": kept, "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    return load(ws, graph)


def closure(concepts: list[str], graph: KnowledgeGraph, relation: str | None) -> list[str]:
    """Grow a selection with everything it depends on.

    On the FILE it is an opt-in of the write path, materialised at save time: applied to
    what is read back, the file would stop meaning what it says. On a COMMISSION it is the
    reading itself (`resolve`): a coverage that names «if» and not «Condición lógica» is not
    a coverage, and the generator's `assumed_known` intersects with exactly this list.
    """
    if not relation:
        return sorted(set(concepts))
    return sorted(set(concepts) | set(graph.prerequisite_closure(concepts, relation)))


def resolve(ws: Workspace, graph: KnowledgeGraph, param: list[str] | None) -> list[str] | None:
    """Choose between a commission's own curriculum and the workspace's, closed downwards.

    Absent and `[]` are different requests and only absent falls back: an empty list is how
    a single commission says «sin restricción». A non-empty list is closed under the
    prerequisite relation (2026-09-04): what the class has covered includes what that rests
    on, which is what the selector marks on screen and what the row must record as having
    run. The file's own list was closed when it was saved with the option, so closing it
    again changes nothing.
    """
    if param is not None:
        return closure(param, graph, locale.prerequisite_relation(ws)) if param else param
    stored = load(ws, graph)["concepts"]
    return closure(stored, graph, locale.prerequisite_relation(ws)) if stored else None

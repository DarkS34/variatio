import json
from datetime import datetime, timezone

from variant_generator.knowledge_graph import KnowledgeGraph
from variant_generator.workspace import Workspace

from . import storage

EMPTY = {"concepts": [], "updated_at": None, "dropped": []}


def _read(ws: Workspace) -> dict:
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
    data = _read(ws)
    if not data["concepts"]:
        return dict(EMPTY)
    existing = set(graph.all_concepts)
    kept = sorted({c for c in data["concepts"] if c in existing})
    dropped = sorted({c for c in data["concepts"] if c not in existing})
    return {"concepts": kept, "updated_at": data["updated_at"], "dropped": dropped}


def save(ws: Workspace, concepts: list[str], graph: KnowledgeGraph) -> dict:
    existing = set(graph.all_concepts)
    kept = sorted({c for c in concepts if c in existing})
    storage.write_json(
        ws.curriculum_path,
        {"concepts": kept, "updated_at": datetime.now(timezone.utc).isoformat()},
    )
    return load(ws, graph)


def closure(concepts: list[str], graph: KnowledgeGraph, relation: str) -> list[str]:
    return sorted(set(concepts) | set(graph.prerequisite_closure(concepts, relation)))


def resolve(ws: Workspace, graph: KnowledgeGraph, param: list[str] | None) -> list[str] | None:
    if param is not None:
        return param
    return load(ws, graph)["concepts"] or None

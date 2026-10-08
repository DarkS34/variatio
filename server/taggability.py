"""Whether the taggability review has anything new to judge, per workspace.

The review decides which concepts of the graph work as labels, judged against the exemplars
profile and the subject's context. Since 2026-10-08 it heads every collection of the bank
(`jobs/chain.py`), so collecting a bank twice over the same profile and syllabus would pay a
model pass per unit for the same verdict and, worse, undo whatever a teacher switched by hand
in between. This module keeps a fingerprint of what the last review read and says when it
still holds.

The fingerprint reads the profile's bytes, the graph's units and concepts in their order, and
the context's bytes. NOT the non-taggable list, which is the review's own output and what a
teacher corrects by hand, and not the bank, which is what the collection is about to rebuild.

The record is a cache (`Workspace.taggability_review_path`): losing it costs nothing, because
a graph that says it was reviewed is taken at its word and the record is written again.
"""

import hashlib
import json
from datetime import datetime

from variatio import entrypoints
from variatio.core import json_io
from variatio.core.workspace import Workspace

from . import storage


def up_to_date(ws: Workspace) -> bool:
    """Say whether the graph's labels were decided against what the workspace holds now.

    A graph a build just wrote says `taggability_reviewed: false` and is never up to date.
    A reviewed graph with no record is one reviewed before the record existed: its word is
    taken and the record starts from here, so the next change of the profile is noticed.
    """
    graph = _graph(ws)
    if graph is None or not graph.get("taggability_reviewed"):
        return False
    if entrypoints.exemplars_profile_path(ws) is None:
        return False
    current = fingerprint(ws)
    stored = record(ws)
    if stored is None:
        write_record(
            ws,
            current,
            list(graph.get("generic_non_taggable_concepts") or []),
            _count(graph),
        )
        return True
    return stored.get("fingerprint") == current


def fingerprint(ws: Workspace) -> str:
    """Digest what a review reads: the profile, the graph's units and concepts, the context."""
    graph = _graph(ws)
    return _digest(
        {
            "profile": storage.sha256_of(entrypoints.exemplars_profile_path(ws)),
            "graph": _digest(graph.get("concepts_by_domains")) if graph else None,
            "context": storage.sha256_of(entrypoints.content_context_path(ws)),
        }
    )


def record(ws: Workspace) -> dict | None:
    """Return what the last review read, or nothing when no review left a record."""
    path = ws.taggability_review_path
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_record(ws: Workspace, digest: str, non_taggable: list[str], concepts: int) -> None:
    """Write down the fingerprint a review judged against, with what it decided."""
    json_io.write_json(
        ws.taggability_review_path,
        {
            "fingerprint": digest,
            "at": datetime.now().isoformat(timespec="seconds"),
            "non_taggable": sorted(non_taggable),
            "concepts": concepts,
        },
    )


def _graph(ws: Workspace) -> dict | None:
    """Read the graph that wins, curated over draft, or nothing."""
    path = entrypoints.knowledge_graph_path(ws)
    if path is None:
        return None
    try:
        data = storage.read_json(path)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _count(graph: dict) -> int:
    """Count the graph's concepts across its units."""
    return sum(len(names) for names in (graph.get("concepts_by_domains") or {}).values())


def _digest(value) -> str:
    """Hash a JSON value as it stands, its order included: a unit moved is a change."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

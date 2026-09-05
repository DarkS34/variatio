"""Deciding which concepts of the graph are any use as a label for this instance.

Its own stage rather than a handler's assembly: the review is a model pass over the graph
and the profile, so the CLI and the API have to reach it through the same door as every
other phase. What it does NOT do is write — the non-taggable list is patched into the
graph by `server/editors/kg_edit`, which owns the history, the database mirror and the
approval it revokes.
"""

import json

from loguru import logger

from .. import prompts as prompts_pkg
from ..core import progress
from ..core.workspace import Workspace
from ..instance import locale
from ..instance.exemplars_profile import ExemplarsProfile
from ..instance.knowledge_graph import KnowledgeGraph
from ..runtime.taggability import BUILD_PHASES as TAGGABILITY_PHASES
from ..runtime.taggability import review
from . import _artifacts


def review_taggability(ws: Workspace) -> dict:
    """Judge every concept as a label and report the verdict with the size of the graph.

    Needs a built profile: a concept is useless as a label only relative to the shapes of
    item this instance sets, so the graph alone cannot answer it. The bank is optional and
    only feeds the sample statements each domain is judged beside. The count travels with
    the names because the caller persists them elsewhere and would have to re-read the
    graph to say how many concepts were weighed.
    """
    kg_path = _artifacts.knowledge_graph_path(ws)
    if kg_path is None:
        raise _artifacts.MissingArtifactError(_artifacts.KNOWLEDGE_GRAPH)

    profile_path = _artifacts.exemplars_profile_path(ws)
    if profile_path is None:
        raise _artifacts.MissingArtifactError(_artifacts.EXEMPLARS_PROFILE)

    knowledge_graph = KnowledgeGraph(kg_path)
    exemplars_profile = ExemplarsProfile(profile_path)

    with progress.overall(TAGGABILITY_PHASES):
        progress.phase("taggable")
        non_taggable = review(
            knowledge_graph,
            exemplars_profile,
            prompts_pkg.of(locale.prompt_language(ws)),
            _bank(ws),
            _artifacts.load_content_context(ws),
        )

    concepts = len(knowledge_graph.all_concepts)
    logger.success(f"{len(non_taggable)} of {concepts} concept(s) are no use as labels")
    return {"non_taggable": non_taggable, "concepts": concepts}


def _bank(ws: Workspace) -> dict:
    """The exemplars bank, or nothing: its statements are evidence and never a condition."""
    if not ws.exemplars_bank_path.is_file():
        return {}
    try:
        with open(ws.exemplars_bank_path, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError) as exc:
        logger.warning(f"Unreadable exemplars bank; judging without samples: {exc}")
        return {}

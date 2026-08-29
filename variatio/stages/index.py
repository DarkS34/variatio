from loguru import logger

from ..core.workspace import Workspace
from ..instance import locale
from .. import prompts as prompts_pkg
from ..embedder import ConceptDescriber, load_descriptions, load_sources, save_descriptions
from ..instance.knowledge_graph import KnowledgeGraph
from . import _artifacts


# No profile here, and that is the point of moving the context out of it. Describing a
# concept needs the graph and what subject this is; it never needed the anatomy of an
# exercise. Loading the profile for its `content_context` alone is what made
# `review.UPSTREAM[KNOWLEDGE_GRAPH] == ()` false in practice, and it failed exactly in the
# state a new workspace starts in: a graph built, nothing else yet.
def _describer(ws: Workspace) -> ConceptDescriber:
    kg_path = _artifacts.knowledge_graph_path(ws)
    if kg_path is None:
        raise _artifacts.MissingArtifactError(_artifacts.KNOWLEDGE_GRAPH)

    return ConceptDescriber(
        KnowledgeGraph(kg_path),
        _artifacts.load_content_context(ws),
        prompts_pkg.of(locale.prompt_language(ws)),
        path=ws.concept_descriptions_path,
        sources_path=ws.concept_sources_path,
    )


def describe_concepts(
    ws: Workspace,
    concepts: list[str] | None = None,
    overwrite: bool = False,
) -> dict[str, str]:
    """Write the prose that concept retrieval matches against.

    Its own step on purpose: these descriptions govern every tag the embedder
    proposes, so they get reviewed before anything is indexed against them.
    """
    describer = _describer(ws)
    descriptions = describer.ensure(concepts=concepts, overwrite=overwrite)
    logger.success(f"{len(descriptions)} concept description(s) available")
    return descriptions


def restamp_descriptions(ws: Workspace, dry_run: bool = False) -> tuple[int, int]:
    changed, total = _describer(ws).restamp(dry_run=dry_run)
    if dry_run:
        logger.info(
            f"{changed} of {total} description(s) would be rewritten against the current graph"
        )
    elif changed:
        logger.success(
            f"{changed} of {total} description(s) re-stamped against the current graph; "
            "no text was rewritten"
        )
    else:
        logger.info(f"{total} description(s) were already stamped against the current graph")
    return changed, total


# Writing descriptions requires the graph and the profile, because they have to be
# composed; READING them requires neither, and routing it through `_describer` tied the
# graph screen to the exemplars profile — an artifact the graph does not have as an
# upstream (`review.UPSTREAM`). The symptom was that, with the graph already built,
# `GET /api/kg` answered 404 saying the profile was missing, and the interface read that
# as the workspace having no graph.
def load_concept_descriptions(ws: Workspace) -> dict[str, str]:
    return load_descriptions(ws.concept_descriptions_path)


def save_concept_descriptions(descriptions: dict[str, str], ws: Workspace) -> None:
    save_descriptions(ws.concept_descriptions_path, descriptions)


# The corpus anchoring, as the graph build left it. Read for the same reason as the
# descriptions and under the same rule: only the file, no graph and no profile.
def load_concept_sources(ws: Workspace) -> dict:
    return load_sources(ws.concept_sources_path)

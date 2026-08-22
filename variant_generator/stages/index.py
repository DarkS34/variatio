from loguru import logger

from ..core.workspace import Workspace
from ..embedder import ConceptDescriber, load_descriptions, load_sources, save_descriptions
from ..instance.knowledge_graph import KnowledgeGraph
from . import _artifacts


# No profile here, and that is the point of moving the context out of it. Describing a
# concept needs the graph and what subject this is; it never needed the anatomy of an
# exercise. Loading the profile for its `content_context` alone is what made
# `review.UPSTREAM[KNOWLEDGE_GRAPH] == ()` false in practice, and it failed exactly in the
# state a new workspace starts in: a graph built, nothing else yet.
def _describer(ws: Workspace | None = None) -> ConceptDescriber:
    ws = _artifacts.resolve(ws)
    kg_path = _artifacts.knowledge_graph_path(ws)
    if kg_path is None:
        raise _artifacts.MissingArtifactError(_artifacts.KNOWLEDGE_GRAPH)

    return ConceptDescriber(
        KnowledgeGraph(kg_path),
        _artifacts.load_content_context(ws),
        path=ws.concept_descriptions_path,
        sources_path=ws.concept_sources_path,
    )


def describe_concepts(
    concepts: list[str] | None = None,
    overwrite: bool = False,
    ws: Workspace | None = None,
) -> dict[str, str]:
    """Write the prose that concept retrieval matches against.

    Its own step on purpose: these descriptions govern every tag the embedder
    proposes, so they get reviewed before anything is indexed against them.
    """
    describer = _describer(ws)
    descriptions = describer.ensure(concepts=concepts, overwrite=overwrite)
    logger.success(f"{len(descriptions)} descripción(es) de concepto disponibles")
    return descriptions


# Writing descriptions requires the graph and the profile, because they have to be
# composed; READING them requires neither, and routing it through `_describer` tied the
# graph screen to the exemplars profile — an artifact the graph does not have as an
# upstream (`review.UPSTREAM`). The symptom was that, with the graph already built,
# `GET /api/kg` answered 404 saying the profile was missing, and the interface read that
# as the workspace having no graph.
def load_concept_descriptions(ws: Workspace | None = None) -> dict[str, str]:
    return load_descriptions(_artifacts.resolve(ws).concept_descriptions_path)


def save_concept_descriptions(
    descriptions: dict[str, str], ws: Workspace | None = None
) -> None:
    save_descriptions(_artifacts.resolve(ws).concept_descriptions_path, descriptions)


# The corpus anchoring, as the graph build left it. Read for the same reason as the
# descriptions and under the same rule: only the file, no graph and no profile.
def load_concept_sources(ws: Workspace | None = None) -> dict:
    return load_sources(_artifacts.resolve(ws).concept_sources_path)

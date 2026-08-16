from loguru import logger

from ..exemplars_profile import ExemplarsProfile
from ..embedder import ConceptDescriber
from ..knowledge_graph import KnowledgeGraph
from ..workspace import Workspace
from . import _artifacts


def _describer(ws: Workspace | None = None) -> ConceptDescriber:
    ws = _artifacts.resolve(ws)
    profile_path = _artifacts.exemplars_profile_path(ws)
    if profile_path is None:
        raise _artifacts.MissingArtifactError(_artifacts.EXEMPLARS_PROFILE)
    kg_path = _artifacts.knowledge_graph_path(ws)
    if kg_path is None:
        raise _artifacts.MissingArtifactError(_artifacts.KNOWLEDGE_GRAPH)

    profile = ExemplarsProfile(profile_path)
    return ConceptDescriber(
        KnowledgeGraph(kg_path), profile.content_context, path=ws.concept_descriptions_path
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
    logger.success(f"{len(descriptions)} concept description(s) available")
    return descriptions


def load_concept_descriptions(ws: Workspace | None = None) -> dict[str, str]:
    return _describer(ws).load()


def save_concept_descriptions(
    descriptions: dict[str, str], ws: Workspace | None = None
) -> None:
    _describer(ws).save(descriptions)

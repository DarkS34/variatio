from loguru import logger

from ..exemplars_profile import ExemplarsProfile
from ..embedder import ConceptDescriber
from ..knowledge_graph import KnowledgeGraph
from . import _artifacts


def _describer() -> ConceptDescriber:
    profile_path = _artifacts.exemplars_profile_path()
    if profile_path is None:
        raise _artifacts.MissingArtifactError(_artifacts.EXEMPLARS_PROFILE)
    kg_path = _artifacts.knowledge_graph_path()
    if kg_path is None:
        raise _artifacts.MissingArtifactError(_artifacts.KNOWLEDGE_GRAPH)

    profile = ExemplarsProfile(profile_path)
    return ConceptDescriber(KnowledgeGraph(kg_path), profile.content_context)


def describe_concepts(
    concepts: list[str] | None = None, overwrite: bool = False
) -> dict[str, str]:
    """Write the prose that concept retrieval matches against.

    Its own step on purpose: these descriptions govern every tag the embedder
    proposes, so they get reviewed before anything is indexed against them.
    """
    describer = _describer()
    descriptions = describer.ensure(concepts=concepts, overwrite=overwrite)
    logger.success(f"{len(descriptions)} concept description(s) available")
    return descriptions


def load_concept_descriptions() -> dict[str, str]:
    return _describer().load()


def save_concept_descriptions(descriptions: dict[str, str]) -> None:
    _describer().save(descriptions)

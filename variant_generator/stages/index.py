from loguru import logger

from ..exemplars_profile import ExemplarsProfile
from ..embedder import ConceptDescriber, load_descriptions, load_sources, save_descriptions
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
        KnowledgeGraph(kg_path),
        profile.content_context,
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


# Escribir descripciones exige el grafo y el perfil, porque hay que redactarlas; LEERLAS
# no exige ninguno de los dos, y hacerlo pasar por `_describer` ataba la pantalla del grafo
# al perfil de ejemplares — un artefacto que el grafo no tiene como upstream (`review.UPSTREAM`).
# El síntoma era que, con el grafo ya construido, `GET /api/kg` devolvía 404 diciendo que
# faltaba el perfil, y la interfaz lo leía como que no había grafo en el workspace.
def load_concept_descriptions(ws: Workspace | None = None) -> dict[str, str]:
    return load_descriptions(_artifacts.resolve(ws).concept_descriptions_path)


def save_concept_descriptions(
    descriptions: dict[str, str], ws: Workspace | None = None
) -> None:
    save_descriptions(_artifacts.resolve(ws).concept_descriptions_path, descriptions)


# El anclaje al corpus, tal cual lo dejó la construcción del grafo. Se lee por el mismo
# motivo que las descripciones y con la misma regla: solo el fichero, sin grafo ni perfil.
def load_concept_sources(ws: Workspace | None = None) -> dict:
    return load_sources(_artifacts.resolve(ws).concept_sources_path)

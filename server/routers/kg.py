from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from variatio import config

from .. import auth, curriculum, kg_view
from ..editors import kg_edit
from ..editors.kg_edit import KGError
from .pipeline import pipeline_payload

router = APIRouter(prefix="/api/kg", tags=["kg"], dependencies=[auth.VIEW])


# Concept and domain names are free Spanish text; keeping them in the body instead of
# the path sidesteps every encoding question about slashes, accents and spaces.
class DomainBody(BaseModel):
    name: str
    new_name: str | None = None
    move_to: str | None = None
    after: str | None = None


class DomainOrderBody(BaseModel):
    order: list[str]


class ConceptBody(BaseModel):
    name: str
    new_name: str | None = None
    domain: str | None = None
    taggable: bool | None = None


class EdgeBody(BaseModel):
    relation: str
    source: str
    target: str


class DescriptionBody(BaseModel):
    concept: str
    description: str


class GraphBody(BaseModel):
    graph: dict


class CurriculumBody(BaseModel):
    concepts: list[str]
    close_prerequisites: bool = False


def _handle(access: auth.Access, action):
    try:
        return {**action(), "pipeline": pipeline_payload(access)}
    except KGError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("")
def read(access: auth.Access = auth.VIEW) -> dict:
    try:
        return kg_edit.summary(access.ws)
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/graph")
def graph(access: auth.Access = auth.VIEW) -> dict:
    try:
        graph_raw = kg_edit.raw(access.ws)
        return kg_view.build(graph_raw, kg_edit.load_graph(access.ws, graph_raw))
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/raw")
def read_raw(access: auth.Access = auth.VIEW) -> dict:
    try:
        return {"graph": kg_edit.raw(access.ws)}
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/raw", dependencies=[auth.EDIT])
def replace(body: GraphBody, access: auth.Access = auth.VIEW) -> dict:
    return _handle(access, lambda: kg_edit.replace(access.ws, body.graph))


@router.get("/neighbours")
def neighbours(concept: str, access: auth.Access = auth.VIEW) -> dict:
    try:
        return {"concept": concept, "relations": kg_edit.neighbours(access.ws, concept)}
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


# DESCRIPTIONS --------------------------------------------------------------------------------


@router.get("/descriptions")
def read_descriptions(access: auth.Access = auth.VIEW) -> dict:
    try:
        return kg_edit.descriptions(access.ws)
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/descriptions", dependencies=[auth.EDIT])
def write_description(body: DescriptionBody, access: auth.Access = auth.VIEW) -> dict:
    try:
        return kg_edit.set_description(access.ws, body.concept, body.description)
    except KGError as exc:
        raise HTTPException(422, str(exc)) from exc


# DOMAINS -------------------------------------------------------------------------------------


@router.post("/domains", dependencies=[auth.EDIT])
def add_domain(body: DomainBody, access: auth.Access = auth.VIEW) -> dict:
    return _handle(access, lambda: kg_edit.add_domain(access.ws, body.name, body.after))


@router.patch("/domains", dependencies=[auth.EDIT])
def patch_domain(body: DomainBody, access: auth.Access = auth.VIEW) -> dict:
    if not body.new_name:
        raise HTTPException(422, "Falta 'new_name'")
    return _handle(access, lambda: kg_edit.rename_domain(access.ws, body.name, body.new_name))


@router.post("/domains/delete", dependencies=[auth.EDIT])
def delete_domain(body: DomainBody, access: auth.Access = auth.VIEW) -> dict:
    return _handle(access, lambda: kg_edit.delete_domain(access.ws, body.name, body.move_to))


@router.put("/domains/order", dependencies=[auth.EDIT])
def reorder_domains(body: DomainOrderBody, access: auth.Access = auth.VIEW) -> dict:
    return _handle(access, lambda: kg_edit.reorder_domains(access.ws, body.order))


# CONCEPTS ------------------------------------------------------------------------------------


@router.post("/concepts", dependencies=[auth.EDIT])
def add_concept(body: ConceptBody, access: auth.Access = auth.VIEW) -> dict:
    if not body.domain:
        raise HTTPException(422, "Falta el dominio del concepto")
    return _handle(
        access,
        lambda: kg_edit.add_concept(
            access.ws,
            body.name,
            body.domain,
            taggable=True if body.taggable is None else body.taggable,
        ),
    )


@router.patch("/concepts", dependencies=[auth.EDIT])
def patch_concept(body: ConceptBody, access: auth.Access = auth.VIEW) -> dict:
    return _handle(
        access,
        lambda: kg_edit.update_concept(
            access.ws,
            body.name,
            new_name=body.new_name,
            domain=body.domain,
            taggable=body.taggable,
        ),
    )


@router.post("/concepts/delete", dependencies=[auth.EDIT])
def delete_concept(body: ConceptBody, access: auth.Access = auth.VIEW) -> dict:
    return _handle(access, lambda: kg_edit.delete_concept(access.ws, body.name))


# RELATIONS -----------------------------------------------------------------------------------


@router.post("/relations/edges", dependencies=[auth.EDIT])
def add_edge(body: EdgeBody, access: auth.Access = auth.VIEW) -> dict:
    return _handle(
        access, lambda: kg_edit.add_edge(access.ws, body.relation, body.source, body.target)
    )


@router.post("/relations/edges/delete", dependencies=[auth.EDIT])
def remove_edge(body: EdgeBody, access: auth.Access = auth.VIEW) -> dict:
    return _handle(
        access, lambda: kg_edit.remove_edge(access.ws, body.relation, body.source, body.target)
    )


# CURRICULUM ----------------------------------------------------------------------------------


@router.get("/curriculum")
def read_curriculum(access: auth.Access = auth.VIEW) -> dict:
    graph = kg_edit.load_graph(access.ws)
    return curriculum.load(access.ws, graph)


@router.put("/curriculum", dependencies=[auth.EDIT])
def write_curriculum(body: CurriculumBody, access: auth.Access = auth.VIEW) -> dict:
    graph = kg_edit.load_graph(access.ws)
    concepts = body.concepts
    if body.close_prerequisites:
        concepts = curriculum.closure(concepts, graph, config.KG_PREREQUISITE_RELATION)
    return curriculum.save(access.ws, concepts, graph)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import kg_view
from ..editors import kg_edit
from ..editors.kg_edit import KGError
from .pipeline import get_pipeline

router = APIRouter(prefix="/api/kg", tags=["kg"])


# Concept and domain names are free Spanish text; keeping them in the body instead of
# the path sidesteps every encoding question about slashes, accents and spaces.
class DomainBody(BaseModel):
    name: str
    new_name: str | None = None
    move_to: str | None = None


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


def _handle(action):
    try:
        return {**action(), "pipeline": get_pipeline()}
    except KGError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("")
def read() -> dict:
    try:
        return kg_edit.summary()
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/graph")
def graph() -> dict:
    try:
        graph_raw = kg_edit.raw()
        return kg_view.build(graph_raw, kg_edit.load_graph(graph_raw))
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/raw")
def read_raw() -> dict:
    try:
        return {"graph": kg_edit.raw()}
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/raw")
def replace(body: GraphBody) -> dict:
    return _handle(lambda: kg_edit.replace(body.graph))


@router.get("/neighbours")
def neighbours(concept: str) -> dict:
    try:
        return {"concept": concept, "relations": kg_edit.neighbours(concept)}
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


# DESCRIPTIONS --------------------------------------------------------------------------------


@router.get("/descriptions")
def read_descriptions() -> dict:
    try:
        return kg_edit.descriptions()
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/descriptions")
def write_description(body: DescriptionBody) -> dict:
    try:
        return kg_edit.set_description(body.concept, body.description)
    except KGError as exc:
        raise HTTPException(422, str(exc)) from exc


# DOMAINS -------------------------------------------------------------------------------------


@router.post("/domains")
def add_domain(body: DomainBody) -> dict:
    return _handle(lambda: kg_edit.add_domain(body.name))


@router.patch("/domains")
def patch_domain(body: DomainBody) -> dict:
    if not body.new_name:
        raise HTTPException(422, "Falta 'new_name'")
    return _handle(lambda: kg_edit.rename_domain(body.name, body.new_name))


@router.post("/domains/delete")
def delete_domain(body: DomainBody) -> dict:
    return _handle(lambda: kg_edit.delete_domain(body.name, body.move_to))


# CONCEPTS ------------------------------------------------------------------------------------


@router.post("/concepts")
def add_concept(body: ConceptBody) -> dict:
    if not body.domain:
        raise HTTPException(422, "Falta el dominio del concepto")
    return _handle(
        lambda: kg_edit.add_concept(
            body.name, body.domain, taggable=True if body.taggable is None else body.taggable
        )
    )


@router.patch("/concepts")
def patch_concept(body: ConceptBody) -> dict:
    return _handle(
        lambda: kg_edit.update_concept(
            body.name, new_name=body.new_name, domain=body.domain, taggable=body.taggable
        )
    )


@router.post("/concepts/delete")
def delete_concept(body: ConceptBody) -> dict:
    return _handle(lambda: kg_edit.delete_concept(body.name))


# RELATIONS -----------------------------------------------------------------------------------


@router.post("/relations/edges")
def add_edge(body: EdgeBody) -> dict:
    return _handle(lambda: kg_edit.add_edge(body.relation, body.source, body.target))


@router.post("/relations/edges/delete")
def remove_edge(body: EdgeBody) -> dict:
    return _handle(lambda: kg_edit.remove_edge(body.relation, body.source, body.target))

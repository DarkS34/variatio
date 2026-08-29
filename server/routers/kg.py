"""The knowledge graph: its concepts, its domains, its relations and the curriculum.

Declares `auth.VIEW` for the whole router; every write adds `auth.EDIT`. Concept and
domain names are free text in the instance's own language, so they travel in the body
and never in the path — that sidesteps every encoding question about slashes, accents
and spaces at once.

The curriculum is host state rather than an artifact, and `close_prerequisites` is an
opt-in on the WRITE path only: materialising the closure at save time is what keeps the
stored list meaning exactly what it says when it is read back.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from variatio.instance import locale

from .. import auth, curriculum, kg_view
from ..editors import kg_edit
from ..editors.kg_edit import KGError
from .pipeline import pipeline_payload

router = APIRouter(prefix="/api/kg", tags=["kg"], dependencies=[auth.VIEW])


class DomainBody(BaseModel):
    """One domain, and whatever is being done to it: renamed, moved into, or placed."""

    name: str
    new_name: str | None = None
    move_to: str | None = None
    after: str | None = None


class DomainOrderBody(BaseModel):
    """The domains in teaching order, as the syllabus is to be read."""

    order: list[str]


class ConceptBody(BaseModel):
    """One concept, and whatever is being done to it."""

    name: str
    new_name: str | None = None
    domain: str | None = None
    taggable: bool | None = None


class EdgeBody(BaseModel):
    """One triple: the relation and its two endpoints."""

    relation: str
    source: str
    target: str


class DescriptionBody(BaseModel):
    """A concept's description, as a person rewrote it."""

    concept: str
    description: str


class GraphBody(BaseModel):
    """A whole graph document, replacing the one on disk."""

    graph: dict


class CurriculumBody(BaseModel):
    """The concepts a course has covered, and whether to close them upwards."""

    concepts: list[str]
    close_prerequisites: bool = False


def _handle(access: auth.Access, action):
    """Run one graph edit and answer it with the chain's new state.

    A `KGError` is the editor refusing an edit, never a missing artifact, so it is 422.
    """
    try:
        return {**action(), "pipeline": pipeline_payload(access)}
    except KGError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("")
def read(access: auth.Access = auth.VIEW) -> dict:
    """Answer the graph as the screens read it: domains, concepts and counts."""
    try:
        return kg_edit.summary(access.ws)
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/graph")
def graph(access: auth.Access = auth.VIEW) -> dict:
    """Answer the positional payload the canvas draws, with its relation vocabulary."""
    try:
        graph_raw = kg_edit.raw(access.ws)
        return kg_view.build(
            graph_raw,
            kg_edit.load_graph(access.ws, graph_raw),
            locale.relation_schema(access.ws),
        )
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/raw")
def read_raw(access: auth.Access = auth.VIEW) -> dict:
    """Answer the graph document verbatim, as it sits on disk."""
    try:
        return {"graph": kg_edit.raw(access.ws)}
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/raw", dependencies=[auth.EDIT])
def replace(body: GraphBody, access: auth.Access = auth.VIEW) -> dict:
    """Replace the whole graph document."""
    return _handle(access, lambda: kg_edit.replace(access.ws, body.graph))


@router.get("/neighbours")
def neighbours(concept: str, access: auth.Access = auth.VIEW) -> dict:
    """Answer one concept's relations, grouped by relation type."""
    try:
        return {"concept": concept, "relations": kg_edit.neighbours(access.ws, concept)}
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


# DESCRIPTIONS --------------------------------------------------------------------------------


@router.get("/descriptions")
def read_descriptions(access: auth.Access = auth.VIEW) -> dict:
    """Answer the cached concept descriptions and what is still missing."""
    try:
        return kg_edit.descriptions(access.ws)
    except KGError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.put("/descriptions", dependencies=[auth.EDIT])
def write_description(body: DescriptionBody, access: auth.Access = auth.VIEW) -> dict:
    """Overwrite one concept's description by hand."""
    try:
        return kg_edit.set_description(access.ws, body.concept, body.description)
    except KGError as exc:
        raise HTTPException(422, str(exc)) from exc


# DOMAINS -------------------------------------------------------------------------------------


@router.post("/domains", dependencies=[auth.EDIT])
def add_domain(body: DomainBody, access: auth.Access = auth.VIEW) -> dict:
    """Add a domain, optionally after a named one."""
    return _handle(access, lambda: kg_edit.add_domain(access.ws, body.name, body.after))


@router.patch("/domains", dependencies=[auth.EDIT])
def patch_domain(body: DomainBody, access: auth.Access = auth.VIEW) -> dict:
    """Rename a domain."""
    if not body.new_name:
        raise HTTPException(422, "Falta 'new_name'")
    return _handle(access, lambda: kg_edit.rename_domain(access.ws, body.name, body.new_name))


@router.post("/domains/delete", dependencies=[auth.EDIT])
def delete_domain(body: DomainBody, access: auth.Access = auth.VIEW) -> dict:
    """Delete a domain, moving its concepts into another or dropping them."""
    return _handle(access, lambda: kg_edit.delete_domain(access.ws, body.name, body.move_to))


@router.put("/domains/order", dependencies=[auth.EDIT])
def reorder_domains(body: DomainOrderBody, access: auth.Access = auth.VIEW) -> dict:
    """Set the order the syllabus is read in."""
    return _handle(access, lambda: kg_edit.reorder_domains(access.ws, body.order))


# CONCEPTS ------------------------------------------------------------------------------------


@router.post("/concepts", dependencies=[auth.EDIT])
def add_concept(body: ConceptBody, access: auth.Access = auth.VIEW) -> dict:
    """Add a concept to a domain, taggable unless said otherwise."""
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
    """Rename a concept, move it, or set whether it may be used as a label."""
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
    """Delete a concept and every triple it appears in."""
    return _handle(access, lambda: kg_edit.delete_concept(access.ws, body.name))


# RELATIONS -----------------------------------------------------------------------------------


@router.post("/relations/edges", dependencies=[auth.EDIT])
def add_edge(body: EdgeBody, access: auth.Access = auth.VIEW) -> dict:
    """Add one triple to the graph."""
    return _handle(
        access, lambda: kg_edit.add_edge(access.ws, body.relation, body.source, body.target)
    )


@router.post("/relations/edges/delete", dependencies=[auth.EDIT])
def remove_edge(body: EdgeBody, access: auth.Access = auth.VIEW) -> dict:
    """Remove one triple from the graph."""
    return _handle(
        access, lambda: kg_edit.remove_edge(access.ws, body.relation, body.source, body.target)
    )


# CURRICULUM ----------------------------------------------------------------------------------


@router.get("/curriculum")
def read_curriculum(access: auth.Access = auth.VIEW) -> dict:
    """Answer what the course has covered, partitioned against the current graph."""
    graph = kg_edit.load_graph(access.ws)
    return curriculum.load(access.ws, graph)


@router.put("/curriculum", dependencies=[auth.EDIT])
def write_curriculum(body: CurriculumBody, access: auth.Access = auth.VIEW) -> dict:
    """Save what the course has covered, closing prerequisites when asked."""
    graph = kg_edit.load_graph(access.ws)
    concepts = body.concepts
    if body.close_prerequisites:
        concepts = curriculum.closure(
            concepts, graph, locale.prerequisite_relation(access.ws)
        )
    return curriculum.save(access.ws, concepts, graph)

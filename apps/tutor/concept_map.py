"""The concept map: one concept of the graph with what surrounds it, shown under a reply.

Code draws it and never the model: a map a model writes can hold a relation the graph does
not, and a diagram that is wrong looks exactly like one that is right. Every node and every
edge here is read off the graph, so the map costs no call and cannot invent.

WHEN a map is shown matters as much as what is on it. A map under every reply is noise the
student learns to scroll past, so a conversation gets one at the two moments the graph has
something to say that the prose does not:

- the OPENING map, the first time the conversation stands on a concept: where it sits, what
  it takes as known and what it leads to. One per move of the focus, even when the focus
  holds two concepts — the second is usually on the first one's map already;
- the REVIEW map, when a reply sends the student back to something earlier — one sentence
  of it names a prerequisite and tells them to go over it again. The same map, with that
  prerequisite marked as the thing to go and read. Once per prerequisite, and never right
  after another map: two maps in adjacent replies are one map too many.

The map is one hop wide and capped, because a diagram is read at a glance or not at all;
what does not fit is counted, not drawn. Within a cap, the concepts closest to the focus by
their descriptions are the ones kept. A concept with nothing before it and nothing after it
has no map, whatever else the graph ties it to: a map says where a concept sits in the order
things are learnt, and the first live conversation opened on «Factorial» with three dotted
«se relaciona con» edges that placed it nowhere.

It returns data, not a drawing: names, relations and directions. The client writes the
diagram, in the reader's interface language and the application's own colours.
"""

from dataclasses import dataclass

import numpy as np

from . import ATTEMPT, EXERCISE, THEORY

# The kinds of reply that work on a concept. A greeting has no concept, and a student asking
# for the solution is asking for something a map does not answer.
MAPPED_KINDS = (THEORY, EXERCISE, ATTEMPT)

# What a glance takes in: measured on the demo subject, where most concepts have one or two
# prerequisites and none to three dependents, but one has twelve dependents and eight
# related concepts — drawn whole, its map was a fan nobody could read.
MAX_BEFORE = 4
MAX_AFTER = 3
MAX_LINKS = 3

# How many replies must separate a review map from the map before it.
REVIEW_GAP = 2

OUT, IN, BOTH = "out", "in", "both"


@dataclass(frozen=True)
class Link:
    """A concept tied to the focus by a relation other than the prerequisite one."""

    name: str
    relation: str
    direction: str


@dataclass(frozen=True)
class ConceptMap:
    """One concept with its neighbours in the graph, as a map shows them."""

    concept: str
    unit: str
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    links: tuple[Link, ...] = ()
    hidden: tuple[int, int, int] = (0, 0, 0)
    review: str | None = None

    def record(self) -> dict:
        """Return the map as a saved turn keeps it and the client draws it."""
        return {
            "concept": self.concept,
            "unit": self.unit,
            "before": list(self.before),
            "after": list(self.after),
            "links": [
                {"name": link.name, "relation": link.relation, "direction": link.direction}
                for link in self.links
            ],
            "hidden": dict(zip(("before", "after", "links"), self.hidden)),
            "review": self.review,
        }


def opening(kind: str, focus: list[str], mapped: list[str], context) -> ConceptMap | None:
    """Return the map of the first focus concept the conversation has no map of, if any.

    A concept the graph places in no order has no map, and the next one of the focus is tried.
    """
    if kind not in MAPPED_KINDS:
        return None
    for name in focus:
        if name not in mapped:
            found = build(name, context)
            if found is not None:
                return found
    return None


def review(
    kind: str, sent_back: tuple[str, str] | None, state: dict, context
) -> ConceptMap | None:
    """Return the map that marks the prerequisite a reply sent the student back to, if due.

    `sent_back` is the focus concept and its prerequisite, as `Card.sent_back` read them off
    the reply.
    """
    if kind not in MAPPED_KINDS or sent_back is None:
        return None
    concept, prerequisite = sent_back
    if review_key(concept, prerequisite) in (state.get("mapped") or []):
        return None
    if int(state.get("since_map", REVIEW_GAP)) < REVIEW_GAP:
        return None
    return build(concept, context, review=prerequisite)


def review_key(concept: str, prerequisite: str) -> str:
    """Return how a conversation's state remembers a review map it has shown."""
    return f"{concept} < {prerequisite}"


def build(name: str, context, review: str | None = None) -> ConceptMap | None:
    """Read one concept's map off the graph, or None when the graph places it in no order."""
    graph = context.knowledge_graph
    if name not in graph.concept_domain:
        return None
    prerequisite = context.generator.prerequisite_relation
    index = context.embedder.concepts_index

    before: list[str] = []
    after: list[str] = []
    if prerequisite and graph.has_relation(prerequisite):
        before = _ranked(graph.neighbors(name, prerequisite, "out"), name, index)
        after = _ranked(graph.neighbors(name, prerequisite, "in"), name, index)
    if not (before or after):
        return None
    if review in before:
        before.remove(review)
        before.insert(0, review)
    else:
        review = None
    taken = {name, *before}
    after = [other for other in after if other not in taken]
    taken.update(after)

    tied: dict[str, Link] = {}
    for relation in graph.graphs:
        if relation == prerequisite:
            continue
        for other, direction in _neighbours(graph, name, relation):
            if other not in taken and other not in tied:
                tied[other] = Link(other, relation, direction)
    links = [tied[other] for other in _ranked(list(tied), name, index)]

    return ConceptMap(
        concept=name,
        unit=graph.concept_domain[name],
        before=tuple(before[:MAX_BEFORE]),
        after=tuple(after[:MAX_AFTER]),
        links=tuple(links[:MAX_LINKS]),
        hidden=(
            max(0, len(before) - MAX_BEFORE),
            max(0, len(after) - MAX_AFTER),
            max(0, len(links) - MAX_LINKS),
        ),
        review=review,
    )


def _neighbours(graph, name: str, relation: str) -> list[tuple[str, str]]:
    """Return a concept's neighbours along one relation, each with the edge's direction."""
    if not graph[relation].is_directed():
        return [(other, BOTH) for other in graph.neighbors(name, relation)]
    return [(other, OUT) for other in graph.neighbors(name, relation, "out")] + [
        (other, IN) for other in graph.neighbors(name, relation, "in")
    ]


def _ranked(names: list[str], concept: str, index: dict) -> list[str]:
    """Order concepts by how close their descriptions are to the focus's, closest first.

    A concept the index does not hold keeps the graph's order, after the ones it does.
    """
    own = index.get(concept)
    if own is None:
        return list(names)
    known = [other for other in names if other in index]
    known.sort(key=lambda other: -float(np.dot(own, index[other])))
    return known + [other for other in names if other not in index]

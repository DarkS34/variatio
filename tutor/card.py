"""The card: what code writes from the artifacts for one exact moment of a conversation.

This is the tutor's whole advantage over a chatbot with instructions, so every entry has a job
and the job is one of the method's rules:

- the subject's context says what is being taught (the role and its scope);
- each focus concept carries its unit, its definition from the notes and the passages the
  graph anchored to it — what the reply leans on, and the places shown under it;
- its direct prerequisites, each with where the notes explain it — what the reply takes as
  known, and the place shown to a student the reply sends back to one;
- its direct dependents — what comes later and must not be introduced, which the checks then
  enforce on the reply;
- its closest concepts of the same unit — something to contrast it with when the student
  confuses two;
- the passages of the notes the message itself is closest to — the reference when the
  question is about no concept, or about a detail of one;
- the criteria of the subject and of the focus's unit, and the terms it never suggests;
- the bank exercise the message IS, when it is one, and a simpler one of the same concept to
  step down to when the student is stuck.

What a kind of message does not need stays off its card: a greeting carries no notes, and a
fixed answer has no card at all.

The card also says when a concept map will be shown under the reply (`map_of`), so the reply
can lean on it instead of describing in prose what the student is about to see drawn.
"""

import re
from dataclasses import dataclass, field

import numpy as np

from variatio.core.lexicon import fold, mentions

from . import ATTEMPT, EXERCISE, SOCIAL, SOLUTION, THEORY
from . import config as tutor_config
from .criteria import Criteria, Criterion
from .passages import PassageIndex, text_key

# The anchored passages are the graph's, cut to a paragraph or two; the bank statement a
# card offers is clipped the same way, since the card has a budget and the student reads
# the whole exercise on the bank's own screen.
_ANCHOR_CHARS = 900
_STATEMENT_CHARS = 700
_NEIGHBOURS = 2

# How many places a reply that names none of the card's shows under it.
_SHOWN = 2

# A part of a heading path shorter than this («Introducción», «Ejemplos») names too many
# sections to say which one a reply meant.
_PART_MIN_CHARS = 8


@dataclass(frozen=True)
class Quote:
    """A piece of the notes a card carries, with where it is."""

    document: str
    location: str
    text: str
    id: str = ""


@dataclass(frozen=True)
class Prerequisite:
    """A concept the focus needs, and where the notes explain it when that is known."""

    name: str
    location: str | None = None
    document: str | None = None


@dataclass(frozen=True)
class FocusConcept:
    """One concept the conversation is about, with everything the graph knows around it."""

    name: str
    unit: str
    definition: str = ""
    anchors: tuple[Quote, ...] = ()
    prerequisites: tuple[Prerequisite, ...] = ()
    neighbours: tuple[str, ...] = ()
    later: tuple[str, ...] = ()


@dataclass(frozen=True)
class BankExercise:
    """An exercise of the bank a card names: the one the message is, or one to step down to."""

    id: str
    source: str
    concepts: tuple[str, ...] = ()
    statement: str = ""


@dataclass(frozen=True)
class Card:
    """Everything one reply is written with besides the method and the conversation."""

    kind: str
    subject: str = ""
    focus: tuple[FocusConcept, ...] = ()
    passages: tuple[Quote, ...] = ()
    criteria: tuple[Criterion, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    exercise: BankExercise | None = None
    step_down: BankExercise | None = None
    map_of: str = ""
    chosen: str = ""
    extra: dict = field(default_factory=dict)

    def quotes(self) -> list[Quote]:
        """Return every piece of the notes the card carries, anchors first."""
        return [quote for concept in self.focus for quote in concept.anchors] + list(self.passages)

    def references(self, reply: str = "", sent_back: tuple[str, str] | None = None) -> list[dict]:
        """Return the places of the notes a reply shows under it, drawn from the card alone.

        They are the ONLY place a student reads where something is: the card quotes the notes
        without their headings and the method forbids a reply to name one, so the reply says
        «en los apuntes» and the exact section is here, one click from the reader. Drawn from
        the card, so a place the model invented cannot reach the screen; but CHOSEN by the
        reply, since the card carries more places than any reply leans on. The places whose
        own section title the reply's words contain come first — a section is usually titled
        after what it explains; failing that, those of whose path it contains any part;
        failing both, the card's first `_SHOWN`. A prerequisite's place is shown only under
        the reply that sends the student back to it (`sent_back`), and leads. A place with no
        section is dropped when its document has one that has.
        """
        places = _distinct(
            {"document": quote.document, "location": quote.location} for quote in self.quotes()
        )
        if not reply:
            return places
        said = f" {_plain(reply)} "
        chosen = places[:_SHOWN]
        for named in (_last_part, _any_part):
            found = [place for place in places if named(place["location"], said)]
            if found:
                chosen = found
                break
        review = [
            {"document": p.document, "location": p.location}
            for concept in self.focus
            for p in concept.prerequisites
            if sent_back and p.name == sent_back[1] and p.document and p.location
        ][:1]
        return _distinct(review + chosen)

    def sent_back(self, reply: str, review: str, wording=None) -> tuple[str, str] | None:
        """Return the focus concept and the prerequisite of it a reply sends the student to.

        Both signs are asked for in ONE sentence, because either alone is everyday prose: the
        sentence names the prerequisite AND tells the student to go over it again (`review`,
        the prompt set's `REVIEW_PATTERN`). «Una función que se llama a sí misma» names a
        prerequisite of recursion and sends nobody anywhere; «si te falta qué es una función,
        repásalo en los apuntes» does.
        """
        own = {concept.name for concept in self.focus}
        sentences = [
            sentence
            for sentence in re.split(r"(?<=[.!?…])\s+|\n+", reply)
            if re.search(review, fold(sentence))
        ]
        for concept in self.focus:
            for earlier in concept.prerequisites:
                if earlier.name in own:
                    continue
                if any(mentions(sentence, earlier.name, wording) for sentence in sentences):
                    return concept.name, earlier.name
        return None

    def later(self) -> list[str]:
        """Return what the focus's dependents are, the concepts a reply must not introduce.

        A concept of the focus is never one of them, even when it depends on the other: a
        focus of «Recursividad» and «Subproblema» made every reply that said «subproblema»
        fail as one that introduced a later concept.
        """
        own = {concept.name for concept in self.focus}
        return list(
            dict.fromkeys(name for concept in self.focus for name in concept.later if name not in own)
        )

    def record(self) -> dict:
        """Return what a saved turn keeps of its card: names, places and ids, never the texts."""
        return {
            "concepts": [concept.name for concept in self.focus],
            "units": list(dict.fromkeys(concept.unit for concept in self.focus if concept.unit)),
            "prerequisites": [p.name for concept in self.focus for p in concept.prerequisites],
            "later": self.later(),
            "passages": [
                {"id": quote.id, "document": quote.document, "location": quote.location}
                for quote in self.passages
            ],
            "criteria": len(self.criteria),
            "forbidden_terms": list(self.forbidden_terms),
            "exercise": self.exercise.id if self.exercise else None,
            "step_down": self.step_down.id if self.step_down else None,
            "map_of": self.map_of or None,
            "chosen": self.chosen or None,
            **self.extra,
        }


def assemble(
    kind: str,
    *,
    context,
    sources: dict,
    criteria: Criteria,
    index: PassageIndex,
    vector: np.ndarray,
    focus: list[str],
    exercise_id: str | None = None,
    map_of: str = "",
    chosen: str = "",
) -> Card:
    """Write the card one reply of this kind is answered with.

    `map_of` is the concept whose map will be shown under the reply, when one will; `chosen`
    the concept the student picked for this message, when they picked one.
    """
    concepts = () if kind == SOCIAL else tuple(_focus_concept(n, context, sources) for n in focus)
    anchored = {text_key(q.text) for concept in concepts for q in concept.anchors}

    passages: tuple[Quote, ...] = ()
    if kind in (THEORY, EXERCISE, ATTEMPT, SOLUTION):
        passages = tuple(
            Quote(document=p.document, location=p.location, text=p.text, id=p.id)
            for p, _score in index.search(
                vector,
                tutor_config.PASSAGES_TOP_K,
                tutor_config.PASSAGE_THRESHOLD,
                exclude=anchored,
            )
        )

    applied: list[Criterion] = []
    if kind != SOCIAL:
        unit = concepts[0].unit if concepts else None
        applied = criteria.for_focus(unit, list(focus), tutor_config.CRITERIA_MAX_CHARS)

    exercise = _bank_exercise(exercise_id, context) if exercise_id else None
    step_down = None
    if kind in (EXERCISE, ATTEMPT) and focus:
        step_down = _step_down(focus[0], exercise_id, context)

    return Card(
        kind=kind,
        subject=context.content_context.prompt_block(),
        focus=concepts,
        passages=passages,
        criteria=tuple(applied),
        forbidden_terms=tuple(criteria.terms()) if kind != SOCIAL else (),
        exercise=exercise,
        step_down=step_down,
        map_of=map_of,
        chosen=chosen,
    )


def _focus_concept(name: str, context, sources: dict) -> FocusConcept:
    """Gather what the graph, its anchoring and the index know around one focus concept."""
    graph = context.knowledge_graph
    relation = context.generator.prerequisite_relation
    anchored = (sources.get("concepts") or {}).get(name) or []
    definitions = sources.get("definitions") or {}

    prerequisites: list[str] = []
    later: list[str] = []
    if relation and graph.has_relation(relation):
        prerequisites = graph.neighbors(name, relation, "out")
        later = graph.neighbors(name, relation, "in")

    return FocusConcept(
        name=name,
        unit=graph.concept_domain.get(name, ""),
        definition=str(definitions.get(name) or context.embedder.concept_descriptions.get(name) or ""),
        anchors=tuple(
            Quote(
                document=str(entry.get("document") or ""),
                location=str(entry.get("location") or ""),
                text=str(entry.get("text") or "")[:_ANCHOR_CHARS],
            )
            for entry in anchored[: tutor_config.ANCHORS_PER_CONCEPT]
            if isinstance(entry, dict) and entry.get("text")
        ),
        prerequisites=tuple(
            Prerequisite(prerequisite, *_first_place(prerequisite, sources))
            for prerequisite in prerequisites
        ),
        neighbours=tuple(_neighbours(name, context, set(prerequisites) | set(later))),
        later=tuple(later),
    )


def _first_place(name: str, sources: dict) -> tuple[str | None, str | None]:
    """Return where the notes first explain a concept — section, then document — or Nones."""
    for entry in (sources.get("concepts") or {}).get(name) or []:
        if isinstance(entry, dict) and entry.get("location"):
            return str(entry["location"]), str(entry.get("document") or "") or None
    return None, None


def _neighbours(name: str, context, excluded: set[str]) -> list[str]:
    """Return the concepts of the same unit closest to this one by their descriptions.

    Compared on the DESCRIPTION vectors and not the merged ones: what a student confuses is
    what the notes say two concepts are, not which exercises they share. A concept's own
    prerequisites and dependents are left out — they are on the card already, as such.
    """
    graph = context.knowledge_graph
    index = context.embedder.concepts_index
    own = index.get(name)
    if own is None:
        return []
    peers = [
        other
        for other in graph.concepts_by_domains.get(graph.concept_domain.get(name, ""), [])
        if other != name
        and other not in excluded
        and other not in graph.generic_non_taggable_concepts
        and other in index
    ]
    peers.sort(key=lambda other: -float(np.dot(own, index[other])))
    return peers[:_NEIGHBOURS]


def _bank_exercise(item_id: str, context) -> BankExercise | None:
    """Return a bank item as a card names it, or None when the bank no longer has it."""
    item = context.exemplars_bank.get(item_id)
    if not isinstance(item, dict):
        return None
    return BankExercise(
        id=item_id,
        source=str(item.get("source") or item_id),
        concepts=tuple(item.get("concepts") or ()),
        statement=_statement(item, context),
    )


def _step_down(concept: str, current: str | None, context) -> BankExercise | None:
    """Return the easiest bank exercise practising `concept` below the current one, if any.

    "Below" is the modality's own ladder (`ItemType.difficulty_rank`); with no current
    exercise, the easiest one of the concept is offered, and an unranked one comes last.
    """
    profile = context.exemplars_profile
    ceiling = None
    if current and isinstance(context.exemplars_bank.get(current), dict):
        ceiling = _rank(context.exemplars_bank[current], profile)

    candidates = []
    for item_id, item in context.exemplars_bank.items():
        if item_id == current or not isinstance(item, dict) or item.get("primary_concept") != concept:
            continue
        rank = _rank(item, profile)
        if ceiling is not None and rank >= ceiling:
            continue
        candidates.append((rank, item_id))
    if not candidates:
        return None
    return _bank_exercise(min(candidates)[1], context)


def _rank(item: dict, profile) -> int:
    """Return an item's place on its modality's difficulty ladder, unrankable ones last."""
    try:
        return profile.item_type(profile.type_key_of(item)).difficulty_rank(item)
    except (KeyError, ValueError):
        return 10**6


def _statement(item: dict, context) -> str:
    """Return a bank item's statement, clipped to what a card can carry."""
    profile = context.exemplars_profile
    try:
        text = profile.item_type(profile.type_key_of(item)).primary_text(item)
    except (KeyError, ValueError):
        return ""
    return text.strip()[:_STATEMENT_CHARS]


def _distinct(places) -> list[dict]:
    """Return places once each, without the bare document of one that has a located place."""
    found: list[dict] = []
    for place in places:
        if place not in found:
            found.append(place)
    located = {place["document"] for place in found if place["location"]}
    return [place for place in found if place["location"] or place["document"] not in located]


def _last_part(location: str, said: str) -> bool:
    """Say whether a reply names the section a heading path ends in."""
    parts = _parts(location)
    return bool(parts) and f" {parts[-1]} " in said


def _any_part(location: str, said: str) -> bool:
    """Say whether a reply names any section of a heading path."""
    return any(f" {part} " in said for part in _parts(location))


def _parts(location: str) -> list[str]:
    """Return the sections of a heading path as a reply would name them, short ones left out."""
    parts = [_plain(part) for part in location.split(" > ")]
    return [part for part in parts if len(part) >= _PART_MIN_CHARS]


def _plain(text: str) -> str:
    """Return text folded, with every run of punctuation read as one space."""
    return " ".join(re.sub(r"[^\w]+", " ", fold(text)).split())

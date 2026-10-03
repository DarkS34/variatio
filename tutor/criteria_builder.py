"""Drafting the subject's teaching criteria from the artifacts the chain already built.

One call per unit of the syllabus, and the unit is where the evidence comes from: its own
paragraphs of the notes — the ones that order, forbid or warn first — the passages the graph
anchored to its concepts, and a few of the bank's solutions to those concepts, where the
conventions a teacher never writes down show. The model cites all of it by id, and code keeps
only what it cited: a criterion with no citation is dropped, exactly as a concept with no
anchoring is left unanchored — no anchoring beats a false one.

The criteria meant for the whole subject come out of every unit at once and say the same
thing in different words, so one last call groups them and the first of each group stays.
A merge that fails keeps them all: the teacher curating the draft is the last word anyway.

Returns data and writes nothing; the job that runs it cleans it with `criteria.normalize`
and writes the draft.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

from variatio.core import progress
from variatio.core.lexicon import fold

from . import calls
from . import config as tutor_config
from . import prompts as tutor_prompts_pkg
from .criteria import MUST, STRENGTHS
from .passages import Passage

_SOLUTION_CHARS = 1200
_STATEMENT_CHARS = 500
# Terms a unit's notes rule out are a handful when there are any; the cap only keeps a
# grammar from running on.
_TERMS_PER_UNIT = 8
# A term is a statement, a keyword or a function as code writes it: `break`, `global`,
# `exit()`. Measured on the demo subject, the model filled the list with practices
# («Uso de variables globales para la comunicación…»), which no check can find in a reply.
_TERM_MAX_WORDS = 3


@dataclass(frozen=True)
class _Evidence:
    """One citable piece handed to the model: its id, where it is, and its text."""

    id: str
    place: dict
    text: str


def build_criteria(context, sources: dict, passages: list[Passage]) -> dict:
    """Draft the criteria of every unit of the syllabus, each one checked against its citations.

    `context` is the workspace's `RuntimeContext`; `sources` its anchoring
    (`concept_sources.json`) and `passages` its notes cut by `passages.cut_corpus`.
    """
    tutor_prompts = tutor_prompts_pkg.of(context.language)
    graph = context.knowledge_graph
    model = tutor_config.CRITERIA_MODEL
    think = tutor_config.THINK_CRITERIA
    per_unit = tutor_config.CRITERIA_PER_UNIT
    cap = None if think else tutor_config.CRITERIA_MAX_TOKENS
    pattern = re.compile(tutor_prompts.NORMATIVE_PATTERN)
    units = [unit for unit in graph.domains if graph.concepts_by_domains.get(unit)]
    logger.info(
        f"[tutor] Redactando los criterios de {len(units)} unidad(es) con '{model}'"
        + (f", razonando a «{think}»" if think else "")
    )

    by_unit: dict[str, list[dict]] = {}
    subject_wide: list[dict] = []
    forbidden: list[dict] = []
    dropped = 0
    with progress.step("tutor_criteria", "Drafting the subject's criteria", len(units) + 1) as handle:
        for index, unit in enumerate(units, 1):
            progress.checkpoint()
            handle.start(index, detail=unit)
            concepts = list(graph.concepts_by_domains[unit])
            evidence = _notes(unit, concepts, sources, passages, pattern)
            evidence += _solutions(concepts, context, tutor_prompts.BANK_SOURCE)
            answer = calls.ask_object(
                tutor_prompts.criteria_unit_prompt(
                    context.content_context.prompt_block(),
                    unit,
                    concepts,
                    [(e.id, _place_text(e.place), e.text) for e in evidence if e.id.startswith("P")],
                    [(e.id, _place_text(e.place), e.text) for e in evidence if e.id.startswith("S")],
                    per_unit,
                ),
                _unit_schema(concepts, [e.id for e in evidence], per_unit),
                model=model,
                think=think,
                phase="tutor_criteria",
                tutor_prompts=tutor_prompts,
                prompts=context.prompts,
                max_output_tokens=cap,
            )
            local, wide, terms, lost = _verify(answer or {}, evidence, concepts)
            by_unit[unit] = local
            subject_wide += wide
            forbidden += terms
            dropped += lost
            handle.tick(detail=unit)
        general = _merge(subject_wide, tutor_prompts, model, context.prompts, cap)
        handle.tick()

    if dropped:
        logger.info(f"[tutor] {dropped} criterio(s) sin cita válida descartado(s)")
    logger.success(
        f"[tutor] Criterios redactados: {len(general)} general(es), "
        f"{sum(len(listed) for listed in by_unit.values())} de unidad, {len(forbidden)} término(s) vetado(s)"
    )
    return {
        "general": general,
        "units": by_unit,
        "forbidden_terms": forbidden,
        "administrative_reply": tutor_prompts.DEFAULT_ADMINISTRATIVE_REPLY,
        "built": {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "model": model,
            "effort": think,
            "units": len(units),
            "dropped": dropped,
        },
    }


def _notes(
    unit: str, concepts: list[str], sources: dict, passages: list[Passage], pattern: re.Pattern
) -> list[_Evidence]:
    """Return a unit's paragraphs of the notes, the normative ones first, within the budget.

    Two roads into the unit, because either can be empty: the passages the cut placed under
    its heading, and the passages the graph anchored to its concepts — a graph whose domains
    were named without the corpus's own units has only the second.
    """
    pieces: list[tuple[dict, str]] = []
    for passage in passages:
        if passage.unit == unit:
            place = {"document": passage.document, "location": passage.location}
            pieces += [(place, p.strip()) for p in re.split(r"\n\s*\n", passage.text) if p.strip()]
    anchored = sources.get("concepts") if isinstance(sources.get("concepts"), dict) else {}
    for concept in concepts:
        for entry in anchored.get(concept) or []:
            if isinstance(entry, dict) and str(entry.get("text") or "").strip():
                place = {
                    "document": str(entry.get("document") or ""),
                    "location": str(entry.get("location") or ""),
                }
                pieces.append((place, str(entry["text"]).strip()))

    seen: set[str] = set()
    distinct = []
    for place, text in pieces:
        key = fold(text)[:200]
        if key not in seen:
            seen.add(key)
            distinct.append((place, text))

    ordered = [p for p in distinct if pattern.search(fold(p[1]))]
    ordered += [p for p in distinct if not pattern.search(fold(p[1]))]
    budget = tutor_config.CRITERIA_EVIDENCE_CHARS
    chosen: list[_Evidence] = []
    for place, text in ordered:
        if len(text) > budget:
            continue
        budget -= len(text)
        chosen.append(_Evidence(id=f"P{len(chosen) + 1}", place=place, text=text))
    return chosen


def _solutions(concepts: list[str], context, bank_label: str) -> list[_Evidence]:
    """Return up to the configured number of the bank's solutions to a unit's concepts.

    One per primary concept before a second of any, so six solutions are six concepts and
    not six variations of the first. An item whose only text is its statement shows no
    convention and is skipped.
    """
    wanted = set(concepts)
    profile = context.exemplars_profile
    rounds: dict[str, list[tuple[str, str, str]]] = {}
    for item_id, item in context.exemplars_bank.items():
        if not isinstance(item, dict):
            continue
        primary = item.get("primary_concept")
        if primary not in wanted and not wanted.intersection(item.get("concepts") or []):
            continue
        rendered = _render_item(item, profile)
        if rendered is not None:
            rounds.setdefault(str(primary), []).append((item_id, str(item.get("source") or ""), rendered))

    picked: list[tuple[str, str, str]] = []
    limit = tutor_config.CRITERIA_SOLUTIONS
    while len(picked) < limit and any(rounds.values()):
        for queue in rounds.values():
            if queue and len(picked) < limit:
                picked.append(queue.pop(0))
    return [
        _Evidence(
            id=f"S{index}",
            place={"document": bank_label, "location": f"{source} · {item_id}" if source else item_id},
            text=text,
        )
        for index, (item_id, source, text) in enumerate(picked, 1)
    ]


def _render_item(item: dict, profile) -> str | None:
    """Render a bank item's statement and its other written fields, or None without them."""
    try:
        item_type = profile.item_type(profile.type_key_of(item))
    except (KeyError, ValueError):
        return None
    skipped = {item_type.primary_field, item_type.difficulty_field}
    others = [
        f"{name}: {value.strip()[:_SOLUTION_CHARS]}"
        for name, value in item.items()
        if name in item_type.field_specs
        and name not in skipped
        and isinstance(value, str)
        and value.strip()
    ]
    if not others:
        return None
    statement = item_type.primary_text(item).strip()[:_STATEMENT_CHARS]
    return "\n".join([f"{item_type.primary_field}: {statement}", *others])


def _unit_schema(concepts: list[str], evidence_ids: list[str], per_unit: int) -> dict:
    """Return the grammar of one unit's answer: every name and id drawn from what it was given."""

    def one_of(values: list[str]) -> dict:
        """Return a string limited to `values`, or any string when there are none to offer."""
        return {"type": "string", "enum": values} if values else {"type": "string"}

    return {
        "type": "object",
        "properties": {
            "criteria": {
                "type": "array",
                "maxItems": per_unit,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "strength": {"type": "string", "enum": list(STRENGTHS)},
                        "scope": {"type": "string", "enum": ["unit", "subject"]},
                        "concepts": {"type": "array", "items": one_of(concepts)},
                        "evidence": {"type": "array", "items": one_of(evidence_ids)},
                    },
                    "required": ["text", "strength", "scope", "concepts", "evidence"],
                },
            },
            "forbidden": {
                "type": "array",
                "maxItems": _TERMS_PER_UNIT,
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "reason": {"type": "string"},
                        "evidence": {"type": "array", "items": one_of(evidence_ids)},
                    },
                    "required": ["term", "reason", "evidence"],
                },
            },
        },
        "required": ["criteria", "forbidden"],
    }


def _verify(
    answer: dict, evidence: list[_Evidence], concepts: list[str]
) -> tuple[list[dict], list[dict], list[dict], int]:
    """Keep what the answer cited from what it was given; return unit, subject, terms, dropped."""
    places = {e.id: e.place for e in evidence}
    known = set(concepts)
    unit_wide: list[dict] = []
    subject_wide: list[dict] = []
    terms: list[dict] = []
    dropped = 0

    for entry in answer.get("criteria") or []:
        if not isinstance(entry, dict):
            continue
        cited = _cited(entry, places)
        text = str(entry.get("text") or "").strip()
        if not text or not cited:
            dropped += 1
            continue
        criterion = {
            "text": text,
            "strength": entry.get("strength") if entry.get("strength") in STRENGTHS else "should",
            "concepts": [c for c in dict.fromkeys(entry.get("concepts") or []) if c in known],
            "sources": cited,
        }
        (subject_wide if entry.get("scope") == "subject" else unit_wide).append(criterion)

    for entry in answer.get("forbidden") or []:
        if not isinstance(entry, dict):
            continue
        cited = _cited(entry, places)
        term = str(entry.get("term") or "").strip()
        if term and cited and len(term.split()) <= _TERM_MAX_WORDS:
            terms.append({"term": term, "reason": str(entry.get("reason") or "").strip(), "sources": cited})
        else:
            dropped += 1
    return unit_wide, subject_wide, terms, dropped


def _cited(entry: dict, places: dict[str, dict]) -> list[dict]:
    """Return the places an entry cites among those it was given, each once."""
    found: list[dict] = []
    for evidence_id in entry.get("evidence") or []:
        place = places.get(evidence_id)
        if place is not None and place not in found:
            found.append(place)
    return found


def _merge(criteria: list[dict], tutor_prompts, model: str, prompts, cap: int | None) -> list[dict]:
    """Collapse the subject-wide criteria that say the same thing, keeping each group's first."""
    if len(criteria) < 2:
        return criteria
    progress.checkpoint()
    answer = calls.ask_object(
        tutor_prompts.criteria_merge_prompt([c["text"] for c in criteria]),
        {
            "type": "object",
            "properties": {
                "groups": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}}
            },
            "required": ["groups"],
        },
        model=model,
        think=False,
        phase="tutor_criteria",
        tutor_prompts=tutor_prompts,
        prompts=prompts,
        max_output_tokens=cap,
    )
    groups = _groups(answer, len(criteria))
    return [_combine([criteria[i] for i in group]) for group in groups]


def _groups(answer: dict | None, count: int) -> list[list[int]]:
    """Return the answer's groups as 0-based indices, every index exactly once.

    An index the answer repeats stays in its first group, one it forgets forms a group of
    its own, and an index out of range is ignored: what comes back is always a partition.
    """
    used: set[int] = set()
    groups: list[list[int]] = []
    for group in (answer or {}).get("groups") or []:
        members = []
        for number in group if isinstance(group, list) else []:
            if isinstance(number, int) and 1 <= number <= count and number - 1 not in used:
                used.add(number - 1)
                members.append(number - 1)
        if members:
            groups.append(members)
    groups += [[index] for index in range(count) if index not in used]
    return sorted(groups, key=lambda members: members[0])


def _combine(group: list[dict]) -> dict:
    """Merge one group into its first criterion, with the firmest strength and every source."""
    first = dict(group[0])
    first["strength"] = MUST if any(c["strength"] == MUST for c in group) else first["strength"]
    first["concepts"] = list(dict.fromkeys(name for c in group for name in c["concepts"]))
    first["sources"] = []
    for criterion in group:
        for place in criterion["sources"]:
            if place not in first["sources"]:
                first["sources"].append(place)
    return first


def _place_text(place: dict) -> str:
    """Render a place for the prompt: its location, else its document."""
    return place.get("location") or place.get("document") or ""

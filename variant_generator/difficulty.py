"""How much each concept demands: the structural half, the blend with the model's judgement
and the invariant that makes the number defensible.

Pure on purpose: neither `inference` nor `Workspace` is imported here, exactly as in
`builders/knowledge_graph_builder/blocks.py`, so everything in it can be checked with a dict
and no GPU. What is imported is `networkx`, because the signal that really orders a subject
is a walk over the prerequisite DAG.

It works on DATA and not on a loaded graph — the list of concepts and the
`[source, key, target]` triples — because its first caller is curation, which has not written
any artifact that could be loaded yet.
"""

import json
from collections import Counter
from pathlib import Path

import networkx as nx
from loguru import logger

from . import config
from .json_io import write_json

EMPTY: dict = {"concepts": {}}


# PERSISTENCE -------------------------------------------------------------------------------


# It is read the way the descriptions and the corpus anchoring are read: ONLY THE FILE. A
# workspace whose graph arrived by import does not have it, and that is not an error — it
# generates uncalibrated, which is how it generated before this existed. The rule that would
# break if the graph or the profile were loaded here is written in `review.UPSTREAM`: the
# graph has no upstreams.
def load_difficulty(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return dict(EMPTY)
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return dict(EMPTY)
    concepts = data.get("concepts")
    return {"concepts": concepts if isinstance(concepts, dict) else {}}


def save_difficulty(path: str | Path, data: dict) -> None:
    write_json(path, data)


def tier_of(concept: str, data: dict) -> int | None:
    entry = (data.get("concepts") or {}).get(concept) or {}
    tier = entry.get("tier")
    return tier if isinstance(tier, int) else None


def threshold_of(concept: str, data: dict) -> str:
    entry = (data.get("concepts") or {}).get(concept) or {}
    return str(entry.get("threshold") or "").strip()


# THE PREREQUISITE DAG ----------------------------------------------------------------------


def prerequisite_pairs(relations: list[list], prerequisite_key: str | None) -> list[tuple[str, str]]:
    if not prerequisite_key:
        return []
    return [
        (source, target)
        for source, key, target in relations
        if key == prerequisite_key and source != target
    ]


# `A → B` means «B is a prerequisite of A», which is the direction the schema declares the
# relation in and the one `ContentGenerator._prerequisites` reads as `direction="out"`.
#
# Cycles are broken here rather than treated as impossible: the draft comes out without them
# because `curation.break_cycles` removes them, but the curated graph is hand-edited and one
# edge put the wrong way round must not leave the whole subject without a difficulty.
def _dag(concepts: list[str], pairs: list[tuple[str, str]]) -> nx.DiGraph:
    universe = set(concepts)
    graph = nx.DiGraph()
    graph.add_nodes_from(concepts)
    graph.add_edges_from((s, t) for s, t in pairs if s in universe and t in universe)

    removed = 0
    while not nx.is_directed_acyclic_graph(graph):
        graph.remove_edge(*nx.find_cycle(graph)[-1][:2])
        removed += 1
    # `debug` and not `warning` because whoever owns the cycle already reports it:
    # `curation.break_cycles` when building and `KnowledgeGraph._report_cycles` when loading.
    # Here it is broken only to keep computing, and this runs twice per calibration.
    if removed:
        logger.debug(f"Prerrequisitos con {removed} ciclo(s); se ignoran esas aristas al calibrar")
    return graph


def prerequisite_depth(concepts: list[str], pairs: list[tuple[str, str]]) -> dict[str, int]:
    """How many chained prerequisites sit below each concept."""
    graph = _dag(concepts, pairs)
    depth = dict.fromkeys(graph.nodes, 0)
    # `topological_sort` yields first the ones that depend on nobody; reversed, a concept's
    # prerequisites are already computed by the time it is reached.
    for node in reversed(list(nx.topological_sort(graph))):
        below = [depth[s] for s in graph.successors(node)]
        depth[node] = 1 + max(below) if below else 0
    return depth


# THE STRUCTURAL HALF -----------------------------------------------------------------------


def _ratio(value: float, top: float) -> float:
    return 0.0 if top <= 0 else value / top


def _rescale(raw: dict[str, float]) -> dict[str, float]:
    if not raw:
        return {}
    low, high = min(raw.values()), max(raw.values())
    # A graph without a single declared prerequisite says nothing about anything's difficulty,
    # and answering 0 would pretend it did. Neutral, and let the model decide.
    if high - low < 1e-9:
        logger.warning("La estructura del grafo no separa dificultades; señal estructural neutra")
        return {c: 0.5 for c in raw}
    return {c: (value - low) / (high - low) for c, value in raw.items()}


def structural_scores(concepts: list[str], relations: list[list], schema) -> dict[str, float]:
    """The difficulty read off the graph, in [0,1], without asking any model."""
    prerequisite = schema.prerequisite
    pairs = prerequisite_pairs(relations, prerequisite)
    depth = prerequisite_depth(concepts, pairs)

    needs = Counter(source for source, _ in pairs)
    enables = Counter(target for _, target in pairs)
    # Every specific key except the prerequisite: «es un tipo de» and «es parte de». The
    # fallback one is left out by construction, which is the point.
    hierarchy = {k for k in schema.specific_keys() if k != prerequisite}
    specificity = Counter(source for source, key, _ in relations if key in hierarchy)

    tops = (
        max(depth.values(), default=0),
        max(needs.values(), default=0),
        max(enables.values(), default=0),
        max(specificity.values(), default=0),
    )
    raw = {
        concept: (
            config.DIFFICULTY_DEPTH_WEIGHT * _ratio(depth.get(concept, 0), tops[0])
            + config.DIFFICULTY_NEEDS_WEIGHT * _ratio(needs[concept], tops[1])
            + config.DIFFICULTY_SPECIFICITY_WEIGHT * _ratio(specificity[concept], tops[3])
            - config.DIFFICULTY_ENABLES_WEIGHT * _ratio(enables[concept], tops[2])
        )
        for concept in concepts
    }
    return _rescale(raw)


# BLEND, INVARIANT AND TIERS ------------------------------------------------------------------


def _judged_score(level: object) -> float | None:
    try:
        value = int(level)
    except (TypeError, ValueError):
        return None
    levels = config.DIFFICULTY_LEVELS
    value = min(max(value, 1), levels)
    return 0.0 if levels < 2 else (value - 1) / (levels - 1)


def blend(
    concepts: list[str],
    structural: dict[str, float],
    judgements: dict[str, object],
    llm_weight: float | None = None,
) -> dict[str, float]:
    alpha = config.DIFFICULTY_LLM_WEIGHT if llm_weight is None else llm_weight
    scores = {}
    for concept in concepts:
        base = structural.get(concept, 0.5)
        judged = _judged_score(judgements.get(concept))
        # A concept the model did not judge — because it is not taggable, or because it was
        # skipped — keeps the structure alone instead of half an invented number.
        scores[concept] = base if judged is None else alpha * judged + (1 - alpha) * base
    return scores


# THE INVARIANT. If A has B as a prerequisite, A cannot demand less than B: mastering A means
# mastering B. The blend can violate it — the model judges concept by concept and the
# structure penalises the backbone ones — and this is what turns an arguable score into a
# number with a checkable property.
def enforce_monotonicity(
    scores: dict[str, float], concepts: list[str], pairs: list[tuple[str, str]]
) -> tuple[dict[str, float], int]:
    graph = _dag(concepts, pairs)
    fixed = dict(scores)
    raised = 0
    for node in reversed(list(nx.topological_sort(graph))):
        below = [fixed[s] for s in graph.successors(node) if s in fixed]
        if below and node in fixed and fixed[node] < max(below):
            fixed[node] = max(below)
            raised += 1
    return fixed, raised


def tier_for(score: float) -> int:
    return 1 + sum(1 for bound in config.DIFFICULTY_TIER_BOUNDARIES if score >= bound)


def calibrate(
    concepts: list[str],
    relations: list[list],
    schema,
    judgements: dict[str, object] | None = None,
    thresholds: dict[str, str] | None = None,
) -> dict:
    """The two signals, blended, with the invariant applied and split into tiers."""
    judgements = judgements or {}
    thresholds = thresholds or {}

    structural = structural_scores(concepts, relations, schema)
    pairs = prerequisite_pairs(relations, schema.prerequisite)
    scores, raised = enforce_monotonicity(
        blend(concepts, structural, judgements), concepts, pairs
    )
    if raised:
        logger.info(
            f"{raised} concepto(s) subidos de nivel para no exigir menos que sus prerrequisitos"
        )

    entries = {}
    for concept in sorted(concepts):
        entry = {
            "tier": tier_for(scores[concept]),
            "score": round(scores[concept], 4),
            "structural": round(structural.get(concept, 0.5), 4),
        }
        judged = judgements.get(concept)
        if _judged_score(judged) is not None:
            entry["judged"] = int(judged)
        threshold = str(thresholds.get(concept) or "").strip()
        if threshold:
            entry["threshold"] = threshold
        entries[concept] = entry

    spread = Counter(entry["tier"] for entry in entries.values())
    logger.success(
        f"Dificultad calibrada: {len(entries)} concepto(s) — "
        + ", ".join(f"nivel {t}: {spread.get(t, 0)}" for t in range(1, config.DIFFICULTY_LEVELS + 1))
    )
    return {"concepts": entries}


# THE EXISTING BANK ---------------------------------------------------------------------------


# An item demands whatever the hardest of the concepts it makes the student practise demands:
# averaging it down with the easy ones would claim that a recursion exercise with loops in it
# is half easy.
def item_tier(concepts: list[str], data: dict) -> int | None:
    tiers = [t for t in (tier_of(c, data) for c in concepts or []) if t is not None]
    return max(tiers) if tiers else None


# The other half of the question: which tier is DERIVED for the exercises that already exist.
# It reports, it does not overwrite — which is why `field` is optional and named by the caller:
# the name of the difficulty field belongs to the instance's profile (`nivel_dificultad` here),
# and this library cannot know it without tying itself to one profile.
#
# It is also the measurement that says whether any of the above is worth anything: the tiers
# written by hand in the teaching material are free ground truth to check the weights against.
def bank_report(bank: dict, data: dict, field: str | None = None) -> dict:
    derived: dict[str, int] = {}
    untagged: list[str] = []
    for item_id, item in (bank or {}).items():
        tier = item_tier(item.get("concepts") or [], data)
        if tier is None:
            untagged.append(item_id)
        else:
            derived[item_id] = tier

    report = {
        "items": len(bank or {}),
        "derived": derived,
        "without_difficulty": sorted(untagged),
        "spread": dict(Counter(derived.values())),
    }
    if field is None:
        return report

    stored = {
        item_id: item.get(field)
        for item_id, item in (bank or {}).items()
        if item.get(field) is not None
    }
    report["stored"] = stored
    report["agreement"] = {
        item_id: {"stored": stored[item_id], "derived": derived[item_id]}
        for item_id in sorted(set(stored) & set(derived))
    }
    return report

"""Phase 2 — a deduplicated, denoised graph. Nothing reaches disk here.

Two unrelated questions are asked separately and each of them in bites, rather than as one
call over the whole node universe: which names are the same concept — only inside groups
that name similarity already flagged as suspicious — and which nodes are not concepts at
all, in batches. Blocking first and escalating only what is ambiguous is the rule the rest
of the pipeline follows.
"""

import re
import unicodedata
from collections import defaultdict

import numpy as np
from loguru import logger

from ... import config
from ...core import inference, progress
from ...runtime.embedder import embed_normalized
from . import blocks, parsing
from .schemas import DROP_SCHEMA, MERGE_SCHEMA

MIN_SINGULARIZE_LENGTH = 3


def run(staging: dict, *, schema, max_attempts: int, prompts) -> dict:
    """Merge the names that are one concept, drop what is not one, and remap the graph."""
    progress.phase("clean")
    nodes = node_universe(staging)
    logger.info(f"Cleaning the raw graph: {len(nodes)} node(s) in the universe")

    det_map, representatives = deterministic_merge(nodes)
    logger.info(f"Mechanical merge: {len(nodes)} → {len(representatives)} node(s)")
    progress.advance(0.1, f"{len(nodes)} → {len(representatives)} node(s) after the mechanical merge")

    definitions = staging.get("definitions") or {}
    llm_map = propose_merges(
        representatives,
        staging["relations"],
        det_map,
        definitions,
        max_attempts=max_attempts,
            prompts=prompts,
    )
    canonicals = sorted({llm_map.get(n, n) for n in representatives})
    logger.info(f"Semantic merge: {len(representatives)} → {len(canonicals)} node(s)")
    progress.advance(0.6, f"{len(canonicals)} node(s) after the semantic merge")

    surviving = {n: llm_map.get(det_map.get(n, n), det_map.get(n, n)) for n in nodes}
    drop = propose_drops(
        canonicals, staging["relations"], surviving, definitions, max_attempts=max_attempts,
            prompts=prompts,
    )
    progress.advance(0.95, f"{len(drop)} descarte(s)")

    node_map = compose_node_map(nodes, det_map, llm_map, drop)
    cleaned = apply_node_map(staging, node_map)
    logger.success(
        f"Graph cleaned: {len(staging['entities'])}→{len(cleaned['entities'])} concept(s), "
        f"{len(staging['relations'])}→{len(cleaned['relations'])} relation(s)"
    )
    progress.advance(1.0)
    return cleaned


def node_universe(graph: dict) -> list[str]:
    """Every entity plus every relation endpoint, so nothing stays dangling and unjudged."""
    nodes = set(graph["entities"])
    for source, _, target in graph["relations"]:
        nodes.add(source)
        nodes.add(target)
    return sorted(nodes)


def deterministic_merge(nodes: list[str]) -> tuple[dict, list[str]]:
    """Merge the mechanical variants of a name; the survivor is the short capitalised form."""
    groups = defaultdict(list)
    for n in nodes:
        groups[norm_key(n)].append(n)
    variant_to_canon = {}
    representatives = []
    for members in groups.values():
        canon = min(members, key=lambda x: (x[:1].islower(), len(x)))
        representatives.append(canon)
        for m in members:
            variant_to_canon[m] = canon
    return variant_to_canon, sorted(representatives)


def norm_key(name: str) -> str:
    """The key two names must share to be merged mechanically.

    Conservative: casing, accents, an optional configurable qualifier and a trailing plural
    suffix. Parentheses are NOT stripped, to keep `O(n)` and `O(log n)` apart, and only the
    LAST word is singularised, so `Listas anidadas` and `Lista anidadas` do not merge.
    """
    s = name.lower().strip()
    if config.KG_BUILDER_MERGE_QUALIFIER_PATTERN:
        s = re.sub(config.KG_BUILDER_MERGE_QUALIFIER_PATTERN, "", s)
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s).strip()
    for suffix in config.KG_BUILDER_PLURAL_SUFFIXES:
        if len(s) > MIN_SINGULARIZE_LENGTH and s.endswith(suffix):
            return s[: -len(suffix)]
    return s


# MERGE ---------------------------------------------------------------------------------------


def propose_merges(
    nodes: list[str],
    relations: list[list],
    det_map: dict,
    definitions: dict[str, str] | None = None,
    *,
    max_attempts: int,
    prompts,
) -> dict:
    """Ask which of the suspicious groups are one concept; returns alias → canonical."""
    groups = merge_candidates(nodes)
    if not groups:
        logger.info("No merge candidates; the mechanical merge stands")
        return {}

    per_call = config.KG_BUILDER_MERGE_GROUPS_PER_CALL
    batches = [groups[i : i + per_call] for i in range(0, len(groups), per_call)]
    logger.info(
        f"{len(groups)} candidate merge group(s) over "
        f"{sum(len(g) for g in groups)} name(s), in {len(batches)} call(s)"
    )

    valid = set(nodes)
    alias_map: dict[str, str] = {}
    with progress.step(
        "kg_merge", "Deciding which names are the same concept", len(batches)
    ) as reporter:
        for idx, batch in enumerate(batches, 1):
            progress.checkpoint()
            reporter.start(idx, detail=f"{len(batch)} grupo(s)")
            progress.advance(
                0.1 + 0.4 * (idx - 1) / len(batches), f"grupos {idx}/{len(batches)}"
            )
            prompt = prompts.merge_candidate_groups_prompt(
                blocks.groups_block(batch, relations, det_map, definitions)
            )
            response = inference.generate(
                model=config.KG_CLEAN_MERGE_MODEL,
                prompt=prompt,
                think=config.THINK_KG_CLEAN_MERGE,
                temperature=inference.judgement_temperature(config.THINK_KG_CLEAN_MERGE),
            ).response
            raw = parsing.parse_object(
                response, f"[merge {idx}/{len(batches)}] ", MERGE_SCHEMA, max_attempts, prompts
            )
            if raw is None:
                continue
            alias_map.update(merge_alias_map(raw.get("merges", []), valid))

    return resolve_chains(alias_map)


def merge_candidates(nodes: list[str]) -> list[list[str]]:
    """Group the names similar enough to be worth asking about.

    A suspicion cheap enough to compute for the whole inventory, which is what lets the model
    be asked about five names instead of six hundred. It embeds NAMES, which retrieval
    deliberately never does — here they are the shortlist and not the answer.
    """
    if len(nodes) < 2:
        return []
    vectors = embed_normalized(
        nodes, "the node names", model=config.EMBEDDING_LLM
    )
    if vectors is None:
        return []

    similarity = vectors @ vectors.T
    np.fill_diagonal(similarity, 0.0)
    groups = components(
        list(range(len(nodes))), similarity, config.KG_BUILDER_MERGE_SIMILARITY
    )
    return [sorted(nodes[i] for i in members) for members in groups if len(members) > 1]


def components(index: list[int], similarity, threshold: float) -> list[list[int]]:
    """The connected components at `threshold`, re-cut stricter when one grows past the cap.

    Components chain (A~B, B~C keeps C even when A and C are unrelated), so an oversized
    group is split again rather than handed over as one unanswerable question.
    """
    parent = {i: i for i in index}

    def find(x: int) -> int:
        """The representative of `x`, path-compressed on the way."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for position, a in enumerate(index):
        for b in index[position + 1 :]:
            if similarity[a, b] >= threshold:
                parent[find(a)] = find(b)

    grouped = defaultdict(list)
    for i in index:
        grouped[find(i)].append(i)

    out = []
    for members in grouped.values():
        if len(members) <= config.KG_BUILDER_MAX_MERGE_GROUP or threshold >= 0.95:
            out.append(members)
        else:
            out.extend(components(members, similarity, threshold + 0.05))
    return out


def merge_alias_map(merges: list, valid: set) -> dict:
    """Read the proposed merges as alias → canonical, forcing every canonical to exist."""
    alias_map = {}
    for merge in merges or []:
        if not isinstance(merge, dict):
            continue
        canonical = merge.get("canonical")
        aliases = [a for a in (merge.get("aliases") or []) if isinstance(a, str)]
        if not isinstance(canonical, str):
            continue
        target = (
            canonical if canonical in valid else next((a for a in aliases if a in valid), None)
        )
        if target is None:
            continue
        for name in (canonical, *aliases):
            if name in valid and name != target:
                alias_map[name] = target
    return alias_map


def resolve_chains(alias_map: dict) -> dict:
    """Point every alias at a final name.

    A group judged in one call can still come back as A→B and B→C, and nothing may end up
    pointing at a name that is itself an alias.
    """
    resolved = {}
    for name in alias_map:
        target = alias_map[name]
        seen = {name}
        while target in alias_map and target not in seen:
            seen.add(target)
            target = alias_map[target]
        if target != name:
            resolved[name] = target
    return resolved


# DROP ----------------------------------------------------------------------------------------


def propose_drops(
    nodes: list[str],
    relations: list[list],
    node_map: dict,
    definitions: dict[str, str] | None = None,
    *,
    max_attempts: int,
    prompts,
) -> set:
    """Ask the model, in batches, which nodes do not name a concept at all."""
    size = config.KG_BUILDER_CLEAN_BATCH_SIZE
    batches = [nodes[i : i + size] for i in range(0, len(nodes), size)]
    drop: set[str] = set()

    with progress.step(
        "kg_drop", "Dropping what does not name a concept", len(batches)
    ) as reporter:
        for idx, batch in enumerate(batches, 1):
            progress.checkpoint()
            reporter.start(idx, detail=f"{len(batch)} nodo(s)")
            progress.advance(
                0.6 + 0.35 * (idx - 1) / len(batches), f"lote {idx}/{len(batches)}"
            )
            prompt = prompts.filter_graph_nodes_prompt(
                blocks.nodes_block(batch, relations, node_map, definitions=definitions)
            )
            # Reasoning stays on, and it is measured: over the same 180 already-clean nodes,
            # turning it off is 6.8x faster and goes from 1 drop to 20. The deliberation is
            # what keeps this pass timid, and a concept dropped here is gone for good.
            response = inference.generate(
                model=config.KG_CLEAN_DROP_MODEL,
                prompt=prompt,
                think=config.THINK_KG_CLEAN_DROP,
                temperature=inference.judgement_temperature(config.THINK_KG_CLEAN_DROP),
            ).response
            raw = parsing.parse_object(
                response, f"[drop {idx}/{len(batches)}] ", DROP_SCHEMA, max_attempts, prompts
            )
            if raw is None:
                continue

            verdicts = raw.get("drop") or {}
            if isinstance(verdicts, list):
                verdicts = {n: "" for n in verdicts if isinstance(n, str)}
            if not isinstance(verdicts, dict):
                continue
            valid = set(batch)
            for name, reason in verdicts.items():
                if name in valid:
                    drop.add(name)
                    logger.debug(f"[{name}] dropped: {reason}")

    logger.info(f"Drops: {len(drop)} of {len(nodes)} node(s)")
    return drop


def compose_node_map(nodes: list[str], det_map: dict, llm_map: dict, drop: set) -> dict:
    """Fold mechanical merge, semantic merge and drops into one node → canonical map.

    A node whose canonical was dropped maps to `None`.
    """
    node_map = {}
    for n in nodes:
        representative = det_map.get(n, n)
        canonical = llm_map.get(representative, representative)
        node_map[n] = None if canonical in drop else canonical
    return node_map


def apply_node_map(graph: dict, node_map: dict) -> dict:
    """Rewrite the whole staging graph under the canonical names."""
    entities = sorted({c for c in node_map.values() if c})
    ents = set(entities)
    relations = remap_relations(graph["relations"], node_map, ents)
    positions = merge_positions(graph.get("positions") or {}, node_map, ents)
    return {
        "entities": entities,
        "edges": sorted({r[1] for r in relations}),
        "relations": sorted(list(r) for r in relations),
        "documents": graph.get("documents") or [],
        "origins": merge_origins(graph.get("origins") or {}, node_map, ents),
        "passages": merge_passages(graph.get("passages") or {}, node_map, ents),
        "positions": positions,
        "occurrences": merge_occurrences(graph.get("occurrences") or {}, node_map, ents),
        "outline": graph.get("outline") or [],
        "definitions": merge_definitions(
            graph.get("definitions") or {}, graph.get("positions") or {}, node_map, ents
        ),
    }


def remap_relations(relations: list[list], node_map: dict, surviving: set) -> set[tuple]:
    """The relations under their canonical names, keeping only those whose endpoints survive."""
    out = set()
    for source, relation, target in relations:
        canon_source, canon_target = node_map.get(source), node_map.get(target)
        if canon_source in surviving and canon_target in surviving:
            out.add((canon_source, relation, canon_target))
    return out


def merge_positions(positions: dict, node_map: dict, surviving: set) -> dict:
    """Where each surviving concept was introduced: the minimum over its aliases."""
    merged: dict[str, int] = {}
    for name, position in positions.items():
        canonical = node_map.get(name)
        if canonical in surviving:
            merged[canonical] = min(position, merged.get(canonical, position))
    return {name: merged[name] for name in sorted(merged)}


def merge_origins(origins: dict, node_map: dict, surviving: set) -> dict:
    """The documents each surviving concept was seen in, united over its aliases."""
    merged: dict[str, set[int]] = defaultdict(set)
    for name, sources in (origins or {}).items():
        canonical = node_map.get(name)
        if canonical in surviving:
            merged[canonical].update(sources)
    return {name: sorted(merged[name]) for name in sorted(merged)}


def merge_passages(passages: dict, node_map: dict, surviving: set) -> dict:
    """The corpus evidence of every alias, carried onto the survivor and capped again.

    The passage that justified "Listas anidadas" still justifies "Listas", and throwing it
    away would leave the survivor with nothing to show; five aliases bring five lists, which
    is why the cap is applied here too.
    """
    merged: dict[str, list[dict]] = defaultdict(list)
    for name, entries in passages.items():
        canonical = node_map.get(name)
        if canonical not in surviving:
            continue
        for entry in entries:
            kept = merged[canonical]
            if len(kept) >= config.KG_MAX_SOURCE_PASSAGES:
                break
            if any(other["text"] == entry["text"] for other in kept):
                continue
            kept.append(entry)
    return {name: merged[name] for name in sorted(merged)}


def merge_occurrences(occurrences: dict, node_map: dict, surviving: set) -> dict:
    """Every chunk a surviving concept was seen in, united over its aliases."""
    merged: dict[str, set[int]] = defaultdict(set)
    for name, chunks in occurrences.items():
        canonical = node_map.get(name)
        if canonical in surviving:
            merged[canonical].update(chunks)
    return {name: sorted(merged[name]) for name in sorted(merged)}


def merge_definitions(
    definitions: dict, positions: dict, node_map: dict, surviving: set
) -> dict:
    """One definition per surviving concept: the one written at its earliest introduction."""
    best: dict[str, tuple[int, str]] = {}
    for name, definition in definitions.items():
        canonical = node_map.get(name)
        if canonical not in surviving or not definition:
            continue
        candidate = (positions.get(name, 0), definition)
        if canonical not in best or candidate < best[canonical]:
            best[canonical] = candidate
    return {name: best[name][1] for name in sorted(best)}

"""Phase 2 — a deduplicated, denoised graph. Nothing reaches disk here.

It used to be ONE model call over the whole node universe, asked to emit a complete
partition in which every one of several hundred nodes appears exactly once — and it had to
answer two unrelated questions at the same time: which names are the same concept, and
which nodes are not concepts at all. The merges it missed are still visible downstream, so
the two questions are now asked separately, and each of them in bites: merges only inside
groups that name-similarity already flagged as suspicious, drops in batches of nodes.
Blocking first and escalating only what is ambiguous is the rule the rest of the pipeline
follows.
"""

import re
import unicodedata
from collections import defaultdict

import numpy as np
from loguru import logger

from ... import config
from ...core import inference, progress
from ...embedder import embed_normalized
from ...prompts import filter_graph_nodes_prompt, merge_candidate_groups_prompt
from . import blocks, parsing
from .schemas import DROP_SCHEMA, MERGE_SCHEMA

MIN_SINGULARIZE_LENGTH = 3


def run(staging: dict, *, schema, max_attempts: int) -> dict:
    progress.phase("clean")
    nodes = node_universe(staging)
    logger.info(f"Limpiando el grafo en bruto: {len(nodes)} nodo(s) en el universo")

    det_map, representatives = deterministic_merge(nodes)
    logger.info(f"Fusión mecánica: {len(nodes)} → {len(representatives)} nodo(s)")
    progress.advance(0.1, f"{len(nodes)} → {len(representatives)} nodo(s) por fusión mecánica")

    definitions = staging.get("definitions") or {}
    llm_map = propose_merges(
        representatives,
        staging["relations"],
        det_map,
        definitions,
        max_attempts=max_attempts,
    )
    canonicals = sorted({llm_map.get(n, n) for n in representatives})
    logger.info(f"Fusión semántica: {len(representatives)} → {len(canonicals)} nodo(s)")
    progress.advance(0.6, f"{len(canonicals)} nodo(s) tras la fusión semántica")

    surviving = {n: llm_map.get(det_map.get(n, n), det_map.get(n, n)) for n in nodes}
    drop = propose_drops(
        canonicals, staging["relations"], surviving, definitions, max_attempts=max_attempts
    )
    progress.advance(0.95, f"{len(drop)} descarte(s)")

    node_map = compose_node_map(nodes, det_map, llm_map, drop)
    cleaned = apply_node_map(staging, node_map)
    logger.success(
        f"Grafo limpio: {len(staging['entities'])}→{len(cleaned['entities'])} concepto(s), "
        f"{len(staging['relations'])}→{len(cleaned['relations'])} relación(es)"
    )
    progress.advance(1.0)
    return cleaned


# The node universe is entities plus every relation endpoint, so phrases that
# only ever appear inside relations also get judged and can't stay dangling.
def node_universe(graph: dict) -> list[str]:
    nodes = set(graph["entities"])
    for source, _, target in graph["relations"]:
        nodes.add(source)
        nodes.add(target)
    return sorted(nodes)


# Conservative key: casing, accents, an optional configurable qualifier and a
# trailing plural suffix. No parenthesis stripping, to keep e.g. O(n) vs O(log n) apart,
# and only the LAST word is singularised, so `Listas anidadas` and `Lista anidadas`
# do not merge.
def norm_key(name: str) -> str:
    s = name.lower().strip()
    if config.KG_BUILDER_MERGE_QUALIFIER_PATTERN:
        s = re.sub(config.KG_BUILDER_MERGE_QUALIFIER_PATTERN, "", s)
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s).strip()
    for suffix in config.KG_BUILDER_PLURAL_SUFFIXES:
        if len(s) > MIN_SINGULARIZE_LENGTH and s.endswith(suffix):
            return s[: -len(suffix)]
    return s


# Merge only mechanical variants deterministically; the survivor is a
# capitalized, short form when available.
def deterministic_merge(nodes: list[str]) -> tuple[dict, list[str]]:
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


# MERGE ---------------------------------------------------------------------------------------


def propose_merges(
    nodes: list[str],
    relations: list[list],
    det_map: dict,
    definitions: dict[str, str] | None = None,
    *,
    max_attempts: int,
) -> dict:
    groups = merge_candidates(nodes)
    if not groups:
        logger.info("Sin candidatos a fusión; se queda la fusión mecánica")
        return {}

    per_call = config.KG_BUILDER_MERGE_GROUPS_PER_CALL
    batches = [groups[i : i + per_call] for i in range(0, len(groups), per_call)]
    logger.info(
        f"{len(groups)} grupo(s) candidatos a fusión sobre "
        f"{sum(len(g) for g in groups)} nombre(s), en {len(batches)} llamada(s)"
    )

    valid = set(nodes)
    alias_map: dict[str, str] = {}
    with progress.step(
        "kg_merge", "Decidiendo qué nombres son el mismo concepto", len(batches)
    ) as reporter:
        for idx, batch in enumerate(batches, 1):
            progress.checkpoint()
            reporter.tick(idx, detail=f"{len(batch)} grupo(s)")
            progress.advance(
                0.1 + 0.4 * (idx - 1) / len(batches), f"grupos {idx}/{len(batches)}"
            )
            prompt = merge_candidate_groups_prompt(
                blocks.groups_block(batch, relations, det_map, definitions)
            )
            response = inference.generate(
                model=config.KG_CLEAN_MERGE_MODEL,
                prompt=prompt,
                think=True,
                temperature=config.TEMPERATURE_REASONING,
            ).response
            raw = parsing.parse_object(
                response, f"[merge {idx}/{len(batches)}] ", MERGE_SCHEMA, max_attempts
            )
            if raw is None:
                continue
            alias_map.update(merge_alias_map(raw.get("merges", []), valid))

    return resolve_chains(alias_map)


# Candidate groups come from the names' own embeddings: a suspicion cheap enough to
# compute for the whole inventory, which is what lets the model be asked about five
# names instead of six hundred. Note this embeds NAMES, which retrieval deliberately
# never does — here they are not the answer, only the shortlist the model then judges.
def merge_candidates(nodes: list[str]) -> list[list[str]]:
    if len(nodes) < 2:
        return []
    vectors = embed_normalized(
        nodes, "los nombres de los nodos", model=config.EMBEDDING_LLM
    )
    if vectors is None:
        return []

    similarity = vectors @ vectors.T
    np.fill_diagonal(similarity, 0.0)
    groups = components(
        list(range(len(nodes))), similarity, config.KG_BUILDER_MERGE_SIMILARITY
    )
    return [sorted(nodes[i] for i in members) for members in groups if len(members) > 1]


# Connected components chain (A~B, B~C keeps C even when A and C are unrelated), so a
# component that grows past the cap is re-cut at a stricter threshold instead of being
# handed over as one unanswerable group.
def components(index: list[int], similarity, threshold: float) -> list[list[int]]:
    parent = {i: i for i in index}

    def find(x: int) -> int:
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


# Force every canonical to be an existing node (drops invented names).
def merge_alias_map(merges: list, valid: set) -> dict:
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


# A group judged in one call can still come back as A→B and B→C; nothing may end up
# pointing at a name that is itself an alias.
def resolve_chains(alias_map: dict) -> dict:
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
) -> set:
    size = config.KG_BUILDER_CLEAN_BATCH_SIZE
    batches = [nodes[i : i + size] for i in range(0, len(nodes), size)]
    drop: set[str] = set()

    with progress.step(
        "kg_drop", "Descartando lo que no nombra un concepto", len(batches)
    ) as reporter:
        for idx, batch in enumerate(batches, 1):
            progress.checkpoint()
            reporter.tick(idx, detail=f"{len(batch)} nodo(s)")
            progress.advance(
                0.6 + 0.35 * (idx - 1) / len(batches), f"lote {idx}/{len(batches)}"
            )
            prompt = filter_graph_nodes_prompt(
                blocks.nodes_block(batch, relations, node_map, definitions=definitions)
            )
            # Reasoning stays ON, and this is measured, not assumed: it looks like a
            # lexical verdict that could be read off the name, and turning it off is 6.8x
            # faster — but over the same 180 already-clean nodes it went from 1 drop to
            # 20, taking `Cohesión`, `El método de la Burbuja`, `Else` and `Error de
            # compilación` with it. The deliberation is what keeps this pass timid, and a
            # concept dropped here is gone from the graph for good.
            response = inference.generate(
                model=config.KG_CLEAN_DROP_MODEL,
                prompt=prompt,
                think=True,
                temperature=config.TEMPERATURE_REASONING,
            ).response
            raw = parsing.parse_object(
                response, f"[drop {idx}/{len(batches)}] ", DROP_SCHEMA, max_attempts
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
                    logger.debug(f"[{name}] descartado: {reason}")

    logger.info(f"Descartes: {len(drop)} de {len(nodes)} nodo(s)")
    return drop


# Compose deterministic merge -> semantic merge -> drops into one node->canonical map;
# a node whose canonical was dropped maps to None.
def compose_node_map(nodes: list[str], det_map: dict, llm_map: dict, drop: set) -> dict:
    node_map = {}
    for n in nodes:
        representative = det_map.get(n, n)
        canonical = llm_map.get(representative, representative)
        node_map[n] = None if canonical in drop else canonical
    return node_map


def apply_node_map(graph: dict, node_map: dict) -> dict:
    entities = sorted({c for c in node_map.values() if c})
    ents = set(entities)
    relations = set()
    for source, relation, target in graph["relations"]:
        canon_source, canon_target = node_map.get(source), node_map.get(target)
        # Keep a relation only when both remapped endpoints survive as entities.
        if canon_source in ents and canon_target in ents:
            relations.add((canon_source, relation, canon_target))
    origins = defaultdict(set)
    for name, sources in (graph.get("origins") or {}).items():
        canonical = node_map.get(name)
        if canonical in ents:
            origins[canonical].update(sources)
    positions = merge_positions(graph.get("positions") or {}, node_map, ents)
    return {
        "entities": entities,
        "edges": sorted({r[1] for r in relations}),
        "relations": sorted(list(r) for r in relations),
        "documents": graph.get("documents") or [],
        "origins": {name: sorted(origins[name]) for name in sorted(origins)},
        "passages": merge_passages(graph.get("passages") or {}, node_map, ents),
        "positions": positions,
        "definitions": merge_definitions(
            graph.get("definitions") or {}, graph.get("positions") or {}, node_map, ents
        ),
    }


# A merged concept was introduced where its EARLIEST alias was: the position is the
# minimum over the aliases, and the definition is the one written at that introduction.
def merge_positions(positions: dict, node_map: dict, surviving: set) -> dict:
    merged: dict[str, int] = {}
    for name, position in positions.items():
        canonical = node_map.get(name)
        if canonical in surviving:
            merged[canonical] = min(position, merged.get(canonical, position))
    return {name: merged[name] for name in sorted(merged)}


def merge_definitions(
    definitions: dict, positions: dict, node_map: dict, surviving: set
) -> dict:
    best: dict[str, tuple[int, str]] = {}
    for name, definition in definitions.items():
        canonical = node_map.get(name)
        if canonical not in surviving or not definition:
            continue
        candidate = (positions.get(name, 0), definition)
        if canonical not in best or candidate < best[canonical]:
            best[canonical] = candidate
    return {name: best[name][1] for name in sorted(best)}


# Merging two names merges their evidence: the passage that justified «Listas anidadas»
# still justifies «Listas», and throwing it away would leave the survivor with nothing to
# show. The cap is applied again here, because five aliases bring five lists.
def merge_passages(passages: dict, node_map: dict, surviving: set) -> dict:
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

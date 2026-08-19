"""Phase 3 — domains, the syllabus order, taggability, and the one file a build writes.

The result is still a DRAFT. The final curation into `instance/knowledge_graph.json`
(draining the unclassified bucket, fixing dubious directions) is manual.
"""

from collections import defaultdict
from pathlib import Path

import networkx as nx
from loguru import logger

from ... import config, inference, progress
from ...prompts import (
    assign_leftover_concepts_prompt,
    curate_graph_domains_prompt,
    link_cross_domain_relations_prompt,
    link_domain_relations_prompt,
    review_taggable_concepts_prompt,
)
from ...json_io import write_json
from . import blocks, parsing
from .schemas import DOMAINS_SCHEMA, LINK_SCHEMA, TAGGABLE_SCHEMA


def run(
    cleaned: dict,
    output_path: str | Path,
    sources_path: str | Path,
    *,
    schema,
    max_attempts: int,
) -> dict:
    concepts = cleaned["entities"]
    relations = cleaned["relations"]
    logger.info(f"Curando {len(concepts)} concepto(s) y {len(relations)} relación(es)")

    progress.phase("domains", f"clasificando {len(concepts)} concepto(s)")
    with progress.step("kg_domains", "Agrupando los conceptos en dominios"):
        progress.checkpoint()
        concepts_by_domains = curate_domains(
            concepts,
            relations,
            cleaned.get("documents") or [],
            cleaned.get("origins") or {},
            max_attempts=max_attempts,
        )
        logger.info(f"Dominios: {len(concepts_by_domains)}")
    progress.advance(1.0, f"{len(concepts_by_domains)} dominio(s)")

    relations = link_relations(
        concepts_by_domains, relations, schema=schema, max_attempts=max_attempts
    )

    progress.phase("curate")
    with progress.step("kg_curate", "Tipando las relaciones y rompiendo ciclos"):
        universe = {c for cs in concepts_by_domains.values() for c in cs}
        typed = break_cycles(build_typed_relations(relations, universe, schema))
        logger.info(
            f"Relaciones: {len(typed)} grupo(s) tipados sobre {len(universe)} concepto(s)"
        )
    progress.advance(1.0)

    curated = {
        "concepts_by_domains": concepts_by_domains,
        "generic_non_taggable_concepts": [],
        "relations": typed,
    }
    write_json(output_path, curated)
    write_sources(sources_path, cleaned, universe)
    logger.success(
        f"Borrador curado en {Path(output_path).name}: {len(universe)} concepto(s), "
        f"{len(typed)} grupo(s) de relación; falta revisar la etiquetabilidad"
    )
    return curated


# ANCLAJE AL CORPUS -----------------------------------------------------------------------


# El segundo — y último — fichero que escribe una construcción del grafo, y no es una etapa
# intermedia de las que se quitaron: es el anclaje de cada concepto al corpus, en `cache/`,
# junto a las descripciones que lo leen. Va aparte del artefacto a propósito. El grafo
# curado se edita a mano y son cientos de KB de citas; y esto se regenera con una
# construcción, igual que el markdown de al lado, así que no es dato del usuario.
#
# `documents` guarda la lista entera del corpus porque de ahí sale una decisión del prompt:
# nombrar el documento de cada pasaje solo tiene sentido cuando hay más de uno.
def write_sources(path: str | Path, cleaned: dict, universe: set) -> None:
    passages = cleaned.get("passages") or {}
    documents = [d.get("name", "") for d in (cleaned.get("documents") or [])]
    anchored = {c: passages[c] for c in sorted(universe) if passages.get(c)}
    write_json(path, {"documents": documents, "concepts": anchored})

    orphans = len(universe) - len(anchored)
    if orphans:
        logger.warning(f"{orphans} concepto(s) sin pasaje del corpus que los respalde")
    logger.info(
        f"Anclaje al corpus: {len(anchored)} de {len(universe)} concepto(s) con cita "
        f"en {Path(path).name}"
    )


# DOMAINS ---------------------------------------------------------------------------------


def curate_domains(
    concepts: list[str],
    relations: list[list],
    documents: list[dict],
    origins: dict[str, list[int]],
    *,
    max_attempts: int,
) -> dict:
    prompt = curate_graph_domains_prompt(
        blocks.nodes_block(concepts, relations, {}, origins),
        blocks.documents_block(documents),
    )
    # NOT `think=True`, and this is the one call where that is load-bearing. Asked to
    # partition the whole inventory, a reasoning model turns the reasoning channel into the
    # answer: measured over 203 concepts with `qwen3.8:27b-q4_K_M` at `low`, it enumerated
    # «24. Colecciones → Domain 5 ✓» for 36 929 characters, hit its stop token at concept 60
    # and returned `response == ""` — with no JSON anywhere in the deliberation to salvage,
    # and `done_reason: "stop"`, so nothing upstream could tell it apart from a real answer.
    # Every concept would have landed in `Sin clasificar`, which is silent: the graph builds,
    # it is just worthless, because neither the per-domain linking nor the taggability pass
    # can reason about that bucket.
    #
    # Off, with the grammar, the same call takes 56 s instead of 400 and places 202 of the
    # 203. It is also what `assign_round` below has always done, for the same reason: this is
    # a partition, not a judgement, and a partition is exactly what a grammar can pin down.
    response = inference.generate(
        model=config.KG_DOMAINS_MODEL, prompt=prompt, think=False, format=DOMAINS_SCHEMA
    ).response
    raw = parsing.parse_object(response, "[domains] ", DOMAINS_SCHEMA, max_attempts) or {}
    by_domain = reconcile_domains(concepts, raw.get("domains", {}) or {})
    return place_leftovers(by_domain, relations, max_attempts=max_attempts)


def reconcile_domains(concepts: list[str], domains_raw: dict) -> dict:
    valid = set(concepts)
    placed: set[str] = set()
    by_domain: dict[str, list[str]] = {}
    for domain, members in domains_raw.items():
        if not isinstance(members, list):
            continue
        kept = sorted({c for c in members if c in valid and c not in placed})
        if kept:
            placed.update(kept)
            by_domain[domain] = kept
    leftover = sorted(c for c in concepts if c not in placed)
    if leftover:
        by_domain.setdefault(config.KG_BUILDER_UNCLASSIFIED_DOMAIN, []).extend(leftover)
    return by_domain


# A concept parked in the unclassified bucket is not a concept the model judged hard to
# place — it is one it never reached. It keeps its relations, so it still works as
# scaffolding, but it gets no domain-level review: neither the per-domain linking nor
# the taggability pass can reason about a bucket that shares no theme. Asking again,
# with only the leftovers and the domains already fixed, is a much smaller question.
def place_leftovers(by_domain: dict, relations: list[list], *, max_attempts: int) -> dict:
    unclassified = config.KG_BUILDER_UNCLASSIFIED_DOMAIN
    leftovers = by_domain.get(unclassified)
    if not leftovers:
        return by_domain

    placed = {d: list(m) for d, m in by_domain.items() if d != unclassified}
    if not placed:
        return by_domain

    logger.info(f"Colocando {len(leftovers)} concepto(s) sueltos en {len(placed)} dominio(s)")
    remaining = list(leftovers)
    # Small batches and repeated rounds, because the failure being repaired here is
    # "forgot to answer", not "could not decide": at 60 names a call the model placed 24
    # of 84, and the ones it skipped are not the hard ones — asked again, in a shorter
    # list, most of them get placed. Rounds stop as soon as one adds nothing, so a
    # genuinely unplaceable concept costs one extra call and not three.
    for _ in range(config.KG_BUILDER_DOMAIN_ROUNDS):
        before = len(remaining)
        remaining = assign_round(remaining, placed, relations, max_attempts=max_attempts)
        if not remaining or len(remaining) == before:
            break

    for domain in placed:
        placed[domain] = sorted(set(placed[domain]))
    if remaining:
        placed[unclassified] = sorted(remaining)
    logger.info(
        f"Sueltos: {len(leftovers) - len(remaining)} colocados, "
        f"{len(remaining)} sin clasificar"
    )
    return placed


def assign_round(
    pending: list[str], placed: dict, relations: list[list], *, max_attempts: int
) -> list[str]:
    size = config.KG_BUILDER_DOMAIN_BATCH_SIZE
    batches = [pending[i : i + size] for i in range(0, len(pending), size)]
    unplaced = set(pending)

    for idx, batch in enumerate(batches, 1):
        progress.checkpoint()
        progress.advance(
            0.5 + 0.45 * (idx - 1) / len(batches), f"sin dominio: {len(unplaced)} concepto(s)"
        )
        prompt = assign_leftover_concepts_prompt(
            blocks.domains_block(placed), blocks.nodes_block(batch, relations, {})
        )
        response = inference.generate(
            model=config.KG_DOMAINS_LEFTOVERS_MODEL,
            prompt=prompt,
            think=False,
            format=DOMAINS_SCHEMA,
        ).response
        raw = (
            parsing.parse_object(
                response,
                f"[domains · leftovers {idx}/{len(batches)}] ",
                DOMAINS_SCHEMA,
                max_attempts,
            )
            or {}
        )
        for domain, members in (raw.get("domains") or {}).items():
            if domain not in placed or not isinstance(members, list):
                continue
            for concept in members:
                if concept in unplaced:
                    placed[domain].append(concept)
                    unplaced.discard(concept)

    return [c for c in pending if c in unplaced]


# LINKING -------------------------------------------------------------------------------------


# One question over the whole inventory produced 10 prerequisite edges for 199 concepts:
# ordering a syllabus is not something a model does in one turn over a flat list. Asked
# per domain — a dozen concepts at a time, with the relations already known as evidence —
# and then once for what crosses domains, it is a question that can actually be answered.
def link_relations(
    concepts_by_domains: dict, relations: list[list], *, schema, max_attempts: int
) -> list[list]:
    domains = list(concepts_by_domains)
    if not domains:
        return relations

    progress.phase("link", f"{len(domains)} dominio(s)")
    known = {tuple(r) for r in relations}
    before = len(known)
    total = len(domains) + 1

    with progress.step(
        "kg_link", "Enlazando conceptos y ordenando el temario", total
    ) as reporter:
        for idx, domain in enumerate(domains, 1):
            progress.checkpoint()
            members = concepts_by_domains[domain]
            reporter.tick(idx, detail=f"{domain} · {len(members)} concepto(s)")
            progress.advance((idx - 1) / total, f"{domain} ({idx}/{len(domains)})")
            known.update(
                tuple(r)
                for r in link_domain(
                    domain, members, relations, schema=schema, max_attempts=max_attempts
                )
            )

        progress.checkpoint()
        reporter.tick(total, detail="relaciones entre dominios")
        progress.advance((total - 1) / total, "relaciones entre dominios")
        known.update(
            tuple(r)
            for r in link_cross_domain(
                concepts_by_domains, schema=schema, max_attempts=max_attempts
            )
        )

    logger.info(f"El enlazado añadió {len(known) - before} relación(es)")
    progress.advance(1.0, f"{len(known) - before} relación(es) nuevas")
    return sorted(list(r) for r in known)


def link_domain(
    domain: str, members: list[str], relations: list[list], *, schema, max_attempts: int
) -> list[list]:
    if len(members) < 2:
        return []
    prompt = link_domain_relations_prompt(
        domain, blocks.nodes_block(members, relations, {}), schema
    )
    response = inference.generate(
        model=config.KG_LINK_DOMAIN_MODEL, prompt=prompt, think=True
    ).response
    raw = parsing.parse_object(response, f"[link · {domain}] ", LINK_SCHEMA, max_attempts)
    if raw is None:
        return []
    return parsing.valid_relations(raw.get("relations", []), schema, allowed=set(members))


def link_cross_domain(concepts_by_domains: dict, *, schema, max_attempts: int) -> list[list]:
    if len(concepts_by_domains) < 2:
        return []
    prompt = link_cross_domain_relations_prompt(
        blocks.domains_block(concepts_by_domains), schema
    )
    response = inference.generate(
        model=config.KG_LINK_CROSS_DOMAIN_MODEL, prompt=prompt, think=True
    ).response
    raw = parsing.parse_object(response, "[link · global] ", LINK_SCHEMA, max_attempts)
    if raw is None:
        return []

    domain_of = {c: d for d, members in concepts_by_domains.items() for c in members}
    proposed = parsing.valid_relations(
        raw.get("relations", []), schema, allowed=set(domain_of)
    )
    crossing = [r for r in proposed if domain_of[r[0]] != domain_of[r[2]]]
    if len(crossing) < len(proposed):
        logger.debug(
            f"Entre dominios: descartadas {len(proposed) - len(crossing)} relación(es) "
            "que no cruzaban ningún dominio"
        )
    return crossing


# TAGGABILITY ---------------------------------------------------------------------------------


# Domain assignment and taggability are two different judgements, and asking for both
# in the same call gave the second one whatever attention was left after partitioning
# a few hundred concepts: the draft came back with a handful of non-taggables and a
# long tail of terms ("Codificación", "Diseño", "Ejecución") that label everything and
# therefore identify nothing. One call per domain, judging only that, is the fix.
def review_taggability(
    concepts_by_domains: dict, relations: list[list], *, max_attempts: int
) -> list[str]:
    domains = list(concepts_by_domains)
    if not domains:
        return []

    progress.phase("taggable")
    non_taggable: set[str] = set()
    with progress.step(
        "kg_taggability", "Revisando qué conceptos sirven como etiqueta", len(domains)
    ) as reporter:
        for idx, domain in enumerate(domains, 1):
            progress.checkpoint()
            members = concepts_by_domains[domain]
            reporter.tick(idx, detail=f"{domain} · {len(members)} concepto(s)")
            progress.advance((idx - 1) / len(domains), f"{domain} ({idx}/{len(domains)})")
            non_taggable.update(
                judge_domain(domain, members, domains, relations, max_attempts=max_attempts)
            )

    logger.info(
        f"Etiquetabilidad: {len(non_taggable)} concepto(s) excluidos "
        f"en {len(domains)} dominio(s)"
    )
    progress.advance(1.0, f"{len(non_taggable)} concepto(s) no etiquetables")
    return sorted(non_taggable)


def judge_domain(
    domain: str,
    members: list[str],
    domains: list[str],
    relations: list[list],
    *,
    max_attempts: int,
) -> list[str]:
    prompt = review_taggable_concepts_prompt(
        domain,
        blocks.concepts_block(domains),
        blocks.nodes_block(members, relations, {}),
    )
    response = inference.generate(
        model=config.KG_TAGGABLE_MODEL, prompt=prompt, think=True
    ).response
    raw = (
        parsing.parse_object(
            response, f"[taggable · {domain}] ", TAGGABLE_SCHEMA, max_attempts
        )
        or {}
    )
    verdicts = raw.get("non_taggable") or {}
    if isinstance(verdicts, list):
        verdicts = {c: "" for c in verdicts if isinstance(c, str)}
    if not isinstance(verdicts, dict):
        return []

    valid = set(members)
    excluded = []
    for concept, reason in verdicts.items():
        if concept in valid:
            excluded.append(concept)
            logger.debug(f"[{domain}] «{concept}» no sirve como etiqueta: {reason}")
    return excluded


# TYPING AND CYCLES ---------------------------------------------------------------------------


def build_typed_relations(relations: list[list], universe: set, schema) -> list[dict]:
    buckets = {relation.key: defaultdict(list) for relation in schema}
    for source, key, target in relations:
        if source not in universe or target not in universe:
            continue
        if key not in schema:
            key = schema.fallback
            if key is None:
                continue
        if target not in buckets[key][source]:
            buckets[key][source].append(target)

    typed = []
    for relation in schema:
        data = buckets[relation.key]
        if not data:
            continue
        relations_data = {source: sorted(data[source]) for source in sorted(data)}
        typed.append({"details": relation.details(), "relations_data": relations_data})
    return typed


# Removes the DFS back edge of every cycle in `directed`+`acyclic` relations, to guarantee
# the loader's cycle check passes. It leaves `acyclic: false` relations (e.g. «es parte de»)
# untouched and does NOT try to keep the semantically-correct direction — that stays manual.
def break_cycles(typed: list[dict]) -> list[dict]:
    for group in typed:
        details = group["details"]
        if not (details.get("acyclic") and details.get("directed")):
            continue
        graph = nx.DiGraph()
        for source, targets in group["relations_data"].items():
            graph.add_edges_from((source, target) for target in targets)
        removed = []
        while not nx.is_directed_acyclic_graph(graph):
            source, target = nx.find_cycle(graph)[-1][:2]
            graph.remove_edge(source, target)
            removed.append((source, target))
        if not removed:
            continue
        rebuilt = defaultdict(list)
        for source, target in graph.edges():
            rebuilt[source].append(target)
        group["relations_data"] = {s: sorted(rebuilt[s]) for s in sorted(rebuilt)}
        logger.warning(
            f"Rotas {len(removed)} arista(s) de retroceso en «{details['verbose']}»: {removed}"
        )
    return typed

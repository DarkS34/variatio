"""Phase 3 — domains, the syllabus order, and the one file a build writes.

The result is still a DRAFT. The final curation into `instance/knowledge_graph.json`
(draining the unclassified bucket, fixing dubious directions) is manual.
"""

from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
from loguru import logger

from ... import config
from ...core import inference, progress
from ...core.json_io import write_json
from ...core.lexicon import fold
from . import blocks, parsing
from .schemas import DOMAIN_NAMES_SCHEMA, DOMAINS_SCHEMA, LINK_SCHEMA, UNITS_SCHEMA


def run(
    cleaned: dict,
    output_path: str | Path,
    sources_path: str | Path,
    *,
    schema,
    max_attempts: int,
    prompts,
) -> dict:
    """Group the concepts, link them, type the relations, write the draft and its sources."""
    concepts = cleaned["entities"]
    relations = cleaned["relations"]
    logger.info(f"Curating {len(concepts)} concept(s) and {len(relations)} relation(s)")

    positions = cleaned.get("positions") or {}
    definitions = cleaned.get("definitions") or {}

    progress.phase("domains", f"clasificando {len(concepts)} concepto(s)")
    with progress.step("kg_domains", "Agrupando los conceptos en dominios"):
        progress.checkpoint()
        concepts_by_domains, units = curate_units(cleaned, max_attempts=max_attempts, prompts=prompts)
        if not concepts_by_domains:
            concepts_by_domains = order_domains(
                curate_domains(
                    concepts,
                    relations,
                    cleaned.get("documents") or [],
                    cleaned.get("origins") or {},
                    definitions,
                    max_attempts=max_attempts,
            prompts=prompts,
                ),
                positions,
            )
        logger.info(f"Domains: {len(concepts_by_domains)}")
    progress.advance(1.0, f"{len(concepts_by_domains)} dominio(s)")

    relations = link_relations(
        concepts_by_domains,
        relations,
        definitions,
        schema=schema,
        max_attempts=max_attempts,
            prompts=prompts,
    )

    progress.phase("curate")
    with progress.step("kg_curate", "Tipando las relaciones y rompiendo ciclos"):
        universe = {c for cs in concepts_by_domains.values() for c in cs}
        typed = build_typed_relations(relations, universe, schema)
        report_against_order(typed, positions, schema.prerequisite_verbose)
        typed = break_cycles(typed, positions, schema.prerequisite_verbose)
        logger.info(
            f"Relations: {len(typed)} typed group(s) over {len(universe)} concept(s)"
        )
    progress.advance(1.0)

    curated = {
        "concepts_by_domains": concepts_by_domains,
        "generic_non_taggable_concepts": [],
        "taggability_reviewed": False,
        "relations": typed,
    }
    write_json(output_path, curated)
    write_sources(sources_path, cleaned, universe, units)
    logger.success(
        f"Draft curated into {Path(output_path).name}: {len(universe)} concept(s), "
        f"{len(typed)} relation group(s); taggability still has to be reviewed"
    )
    return curated


# ANCLAJE AL CORPUS -----------------------------------------------------------------------


def write_sources(
    path: str | Path, cleaned: dict, universe: set, units: list[dict] | None = None
) -> None:
    """Write each concept's anchoring to the corpus: the second and last file a build writes.

    It lives in `cache/` and not in the artifact: the curated graph is edited by hand and
    this is hundreds of KB of quotations, and a build regenerates it, so it is not user data.
    The whole document list travels with it because a prompt decision comes from it — naming
    each passage's document only makes sense when there is more than one.
    """
    passages = cleaned.get("passages") or {}
    definitions = cleaned.get("definitions") or {}
    documents = [d.get("name", "") for d in (cleaned.get("documents") or [])]
    anchored = {c: passages[c] for c in sorted(universe) if passages.get(c)}
    defined = {c: definitions[c] for c in sorted(universe) if definitions.get(c)}
    payload = {"documents": documents, "concepts": anchored, "definitions": defined}
    if cleaned.get("outline"):
        payload["outline"] = cleaned["outline"]
    if units:
        payload["units"] = units
    write_json(path, payload)

    orphans = len(universe) - len(anchored)
    if orphans:
        logger.warning(f"{orphans} concept(s) with no corpus passage behind them")
    logger.info(
        f"Corpus anchoring: {len(anchored)} of {len(universe)} concept(s) quoted "
        f"in {Path(path).name}"
    )


# UNITS -----------------------------------------------------------------------------------


MIN_UNITS = 2


def segment_syllabus(
    outline: list[dict], documents: list[dict], *, max_attempts: int, prompts
) -> list[dict]:
    """Ask the model where each unit of the syllabus opens in the corpus's heading index.

    Returns `[]` — never an error — when there is no index or the answer is unusable: the
    domains are then named without looking at the structure of the material.
    """
    if not outline:
        logger.info(
            "The corpus has no heading index; the domains are named without looking at "
            "the structure of the material"
        )
        return []
    prompt = prompts.segment_syllabus_prompt(blocks.outline_block(outline, documents))
    response = inference.generate(
        model=config.KG_UNITS_MODEL,
        prompt=prompt,
        think=config.THINK_KG_UNITS,
        format=None if config.THINK_KG_UNITS else UNITS_SCHEMA,
        temperature=inference.judgement_temperature(config.THINK_KG_UNITS),
    ).response
    raw = parsing.parse_object(response, "[units] ", UNITS_SCHEMA, max_attempts, prompts) or {}
    units = accept_units(raw.get("units") or [], outline)
    if not units:
        logger.warning(
            f"The model did not segment the syllabus over {len(outline)} heading(s); "
            "the domains are named without looking at the structure of the material"
        )
        return []
    logger.success(
        f"Syllabus: {len(units)} unit(s) over {len(outline)} heading(s) — "
        + " · ".join(unit["name"] for unit in units)
    )
    return units


def accept_units(proposed: list, outline: list[dict]) -> list[dict]:
    """Keep the proposed units that name a real heading, in the order of the material.

    A unit is refused when it repeats a name, a position or a chunk another already claims,
    and the whole segmentation is refused below `MIN_UNITS`: one unit is not a syllabus.
    """
    unclassified = config.KG_BUILDER_UNCLASSIFIED_DOMAIN
    units: list[dict] = []
    seen_positions: set[int] = set()
    seen_names: set[str] = set()
    seen_chunks: set[int] = set()

    for entry in proposed:
        if not isinstance(entry, dict):
            continue
        raw_name = entry.get("name")
        name = raw_name.strip() if isinstance(raw_name, str) else ""
        position = entry.get("opens_at")
        if not name or fold(name) == fold(unclassified):
            continue
        if not isinstance(position, int) or isinstance(position, bool):
            continue
        if not 1 <= position <= len(outline):
            continue
        if position in seen_positions or name.casefold() in seen_names:
            continue
        anchor = outline[position - 1]
        if anchor["chunk"] in seen_chunks:
            continue
        seen_positions.add(position)
        seen_names.add(name.casefold())
        seen_chunks.add(anchor["chunk"])
        units.append({"name": name, "heading": anchor["heading"], "chunk": anchor["chunk"]})

    units.sort(key=lambda unit: unit["chunk"])
    return units if len(units) >= MIN_UNITS else []


def unit_at(units: list[dict], chunk: int) -> str | None:
    """The unit a chunk falls in: the last one that opened at or before it."""
    found = None
    for unit in units:
        if unit["chunk"] > chunk:
            break
        found = unit["name"]
    return found


def unit_of(units: list[dict], chunks: list[int]) -> str | None:
    """The unit a concept belongs to: the one most of its chunks fall in, earliest wins."""
    order = {unit["name"]: index for index, unit in enumerate(units)}
    votes: Counter = Counter()
    for chunk in chunks:
        name = unit_at(units, chunk)
        if name is not None:
            votes[name] += 1
    if not votes:
        return None
    return min(votes, key=lambda name: (-votes[name], order[name]))


def assign_to_units(
    units: list[dict], concepts: list[str], occurrences: dict
) -> tuple[dict, list[str]]:
    """Place each concept in the unit the corpus mentions it in; `(by unit, leftovers)`."""
    by_unit: dict[str, list[str]] = {unit["name"]: [] for unit in units}
    leftovers: list[str] = []
    for concept in concepts:
        name = unit_of(units, occurrences.get(concept) or [])
        if name is None:
            leftovers.append(concept)
        else:
            by_unit[name].append(concept)
    return by_unit, leftovers


def curate_units(cleaned: dict, *, max_attempts: int, prompts) -> tuple[dict, list[dict]]:
    """Group the concepts by the syllabus's own units; `({}, [])` if none can be found."""
    outline = cleaned.get("outline") or []
    units = segment_syllabus(
        outline, cleaned.get("documents") or [], max_attempts=max_attempts,
            prompts=prompts,
    )
    if not units:
        return {}, []

    concepts = sorted(cleaned["entities"])
    by_unit, leftovers = assign_to_units(units, concepts, cleaned.get("occurrences") or {})
    logger.info(
        f"Syllabus: {len(concepts) - len(leftovers)} of {len(concepts)} concept(s) "
        f"placed by the corpus; {len(leftovers)} left for the second pass"
    )
    if leftovers:
        by_unit[config.KG_BUILDER_UNCLASSIFIED_DOMAIN] = sorted(leftovers)

    placed = place_leftovers(
        by_unit,
        cleaned.get("relations") or [],
        cleaned.get("definitions") or {},
        max_attempts=max_attempts,
            prompts=prompts,
    )
    positions = cleaned.get("positions") or {}
    return {d: blocks.ordered(m, positions) for d, m in placed.items()}, units


# DOMAINS ---------------------------------------------------------------------------------


def curate_domains(
    concepts: list[str],
    relations: list[list],
    documents: list[dict],
    origins: dict[str, list[int]],
    definitions: dict[str, str] | None = None,
    *,
    max_attempts: int,
    prompts,
) -> dict:
    """Name the blocks of the syllabus, then place every concept in them in batches.

    The naming call is shown every concept — the units of a syllabus cannot be named from a
    sample — but NOT the relation evidence, which is what justifies WHERE a concept goes and
    is `assign_round`'s question. It runs with a grammar and reasoning off, and that is
    load-bearing: asked to partition the whole inventory, the model turned the reasoning
    channel into the answer, enumerated for 36 929 characters, hit its stop token at concept
    60 and returned an empty `response` with `done_reason: "stop"` — indistinguishable
    upstream from a real answer, with every concept landing in «Sin clasificar» in silence.
    """
    prompt = prompts.curate_graph_domains_prompt(
        blocks.nodes_block(concepts, [], {}, origins),
        blocks.documents_block(documents),
    )
    response = inference.generate(
        model=config.KG_DOMAINS_MODEL,
        prompt=prompt,
        think=config.THINK_KG_DOMAINS,
        format=None if config.THINK_KG_DOMAINS else DOMAIN_NAMES_SCHEMA,
        temperature=inference.judgement_temperature(config.THINK_KG_DOMAINS),
    ).response
    raw = parsing.parse_object(response, "[domains] ", DOMAIN_NAMES_SCHEMA, max_attempts, prompts) or {}

    named: list[str] = []
    for domain in raw.get("domains") or []:
        name = domain.strip() if isinstance(domain, str) else ""
        if name and fold(name) != fold(config.KG_BUILDER_UNCLASSIFIED_DOMAIN) and name not in named:
            named.append(name)
    if not named:
        logger.warning("The model named no domain; everything is left unclassified")
        return {config.KG_BUILDER_UNCLASSIFIED_DOMAIN: sorted(concepts)}

    logger.info(f"{len(named)} domain(s) named; placing {len(concepts)} concept(s) in batches")
    by_domain = {domain: [] for domain in named}
    remaining = assign_round(
        sorted(concepts), by_domain, relations, definitions, max_attempts=max_attempts,
            prompts=prompts,
    )

    for domain in by_domain:
        by_domain[domain] = sorted(set(by_domain[domain]))
    if remaining:
        by_domain[config.KG_BUILDER_UNCLASSIFIED_DOMAIN] = sorted(remaining)
    return place_leftovers(
        by_domain, relations, definitions, max_attempts=max_attempts, prompts=prompts
    )


def place_leftovers(
    by_domain: dict,
    relations: list[list],
    definitions: dict[str, str] | None = None,
    *,
    max_attempts: int,
    prompts,
) -> dict:
    """Ask again about the unclassified bucket alone, with the domains already fixed.

    A concept parked there is not one the model judged hard to place — it is one it never
    reached — and it gets no domain-level review afterwards: neither the per-domain linking
    nor the taggability pass can reason about a bucket that shares no theme.
    """
    unclassified = config.KG_BUILDER_UNCLASSIFIED_DOMAIN
    leftovers = by_domain.get(unclassified)
    if not leftovers:
        return by_domain

    placed = {d: list(m) for d, m in by_domain.items() if d != unclassified}
    if not placed:
        return by_domain

    logger.info(f"Placing {len(leftovers)} leftover concept(s) into {len(placed)} domain(s)")
    remaining = list(leftovers)
    # Small batches and repeated rounds, because the failure being repaired is "forgot to
    # answer" and not "could not decide": at 60 names a call the model placed 24 of 84, and
    # asked again in a shorter list most of the rest get placed. A round that adds nothing
    # stops the loop, so a genuinely unplaceable concept costs one extra call and not three.
    for _ in range(config.KG_BUILDER_DOMAIN_ROUNDS):
        before = len(remaining)
        remaining = assign_round(
            remaining, placed, relations, definitions, max_attempts=max_attempts,
            prompts=prompts,
        )
        if not remaining or len(remaining) == before:
            break

    for domain in placed:
        placed[domain] = sorted(set(placed[domain]))
    if remaining:
        placed[unclassified] = sorted(remaining)
    logger.info(
        f"Leftovers: {len(leftovers) - len(remaining)} placed, "
        f"{len(remaining)} unclassified"
    )
    return placed


def assign_round(
    pending: list[str],
    placed: dict,
    relations: list[list],
    definitions: dict[str, str] | None = None,
    *,
    max_attempts: int,
    prompts,
) -> list[str]:
    """Place `pending` into the existing domains, batch by batch; returns what is still loose.

    `placed` is mutated as the answers arrive, so a concept is only ever put in a domain the
    caller already declared.
    """
    size = config.KG_BUILDER_DOMAIN_BATCH_SIZE
    batches = [pending[i : i + size] for i in range(0, len(pending), size)]
    unplaced = set(pending)

    for idx, batch in enumerate(batches, 1):
        progress.checkpoint()
        progress.advance(
            0.5 + 0.45 * (idx - 1) / len(batches), f"sin dominio: {len(unplaced)} concepto(s)"
        )
        prompt = prompts.assign_leftover_concepts_prompt(
            blocks.domains_block(placed),
            blocks.nodes_block(batch, relations, {}, definitions=definitions),
        )
        response = inference.generate(
            model=config.KG_DOMAINS_LEFTOVERS_MODEL,
            prompt=prompt,
            think=config.THINK_KG_DOMAINS_LEFTOVERS,
            format=None if config.THINK_KG_DOMAINS_LEFTOVERS else DOMAINS_SCHEMA,
            temperature=inference.judgement_temperature(config.THINK_KG_DOMAINS_LEFTOVERS),
        ).response
        raw = (
            parsing.parse_object(
                response,
                f"[domains · leftovers {idx}/{len(batches)}] ",
                DOMAINS_SCHEMA,
                max_attempts,
                prompts,
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


def order_domains(concepts_by_domains: dict, positions: dict[str, int]) -> dict:
    """Order the domains by the median position of their members, and the members by theirs.

    The order the material introduces things in is the oldest signal in prerequisite learning
    and it is free, since extraction recorded where each concept was first seen. It is what
    makes the linking prompts' «the list follows the material» true.
    """

    def median(members: list[str]) -> float:
        """The median position of a domain's members, infinite when none is known."""
        known = sorted(positions[m] for m in members if m in positions)
        if not known:
            return float("inf")
        middle = len(known) // 2
        return known[middle] if len(known) % 2 else (known[middle - 1] + known[middle]) / 2

    unclassified = config.KG_BUILDER_UNCLASSIFIED_DOMAIN
    domains = sorted(
        concepts_by_domains,
        key=lambda d: (d == unclassified, median(concepts_by_domains[d]), d),
    )
    return {d: blocks.ordered(concepts_by_domains[d], positions) for d in domains}


def link_relations(
    concepts_by_domains: dict,
    relations: list[list],
    definitions: dict[str, str] | None = None,
    *,
    schema,
    max_attempts: int,
    prompts,
) -> list[list]:
    """Ask for the missing relations once per domain, then once for what crosses domains.

    One question over the whole inventory produced 10 prerequisite edges for 199 concepts:
    ordering a syllabus is not something a model does in one turn over a flat list.
    """
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
                    domain,
                    members,
                    relations,
                    definitions,
                    schema=schema,
                    max_attempts=max_attempts,
            prompts=prompts,
                )
            )

        progress.checkpoint()
        reporter.tick(total, detail="relaciones entre dominios")
        progress.advance((total - 1) / total, "relaciones entre dominios")
        known.update(
            tuple(r)
            for r in link_cross_domain(
                concepts_by_domains, definitions, schema=schema, max_attempts=max_attempts,
            prompts=prompts,
            )
        )

    logger.info(f"Linking added {len(known) - before} relation(s)")
    progress.advance(1.0, f"{len(known) - before} relación(es) nuevas")
    return sorted(list(r) for r in known)


def link_domain(
    domain: str,
    members: list[str],
    relations: list[list],
    definitions: dict[str, str] | None = None,
    *,
    schema,
    max_attempts: int,
    prompts,
) -> list[list]:
    """The relations the model finds inside one domain, restricted to its own members."""
    if len(members) < 2:
        return []
    prompt = prompts.link_domain_relations_prompt(
        domain, blocks.nodes_block(members, relations, {}, definitions=definitions), schema
    )
    response = inference.generate(
        model=config.KG_LINK_DOMAIN_MODEL,
        prompt=prompt,
        think=config.THINK_KG_LINK_DOMAIN,
        temperature=inference.judgement_temperature(config.THINK_KG_LINK_DOMAIN),
    ).response
    raw = parsing.parse_object(response, f"[link · {domain}] ", LINK_SCHEMA, max_attempts, prompts)
    if raw is None:
        return []
    return parsing.valid_relations(raw.get("relations", []), schema, allowed=set(members))


def link_cross_domain(
    concepts_by_domains: dict,
    definitions: dict[str, str] | None = None,
    *,
    schema,
    max_attempts: int,
    prompts,
) -> list[list]:
    """The relations that genuinely cross a domain boundary; the rest are discarded."""
    if len(concepts_by_domains) < 2:
        return []
    prompt = prompts.link_cross_domain_relations_prompt(
        blocks.domains_block(concepts_by_domains, definitions), schema
    )
    response = inference.generate(
        model=config.KG_LINK_CROSS_DOMAIN_MODEL,
        prompt=prompt,
        think=config.THINK_KG_LINK_CROSS_DOMAIN,
        temperature=inference.judgement_temperature(config.THINK_KG_LINK_CROSS_DOMAIN),
    ).response
    raw = parsing.parse_object(response, "[link · global] ", LINK_SCHEMA, max_attempts, prompts)
    if raw is None:
        return []

    domain_of = {c: d for d, members in concepts_by_domains.items() for c in members}
    proposed = parsing.valid_relations(
        raw.get("relations", []), schema, allowed=set(domain_of)
    )
    crossing = [r for r in proposed if domain_of[r[0]] != domain_of[r[2]]]
    if len(crossing) < len(proposed):
        logger.debug(
            f"Cross-domain: discarded {len(proposed) - len(crossing)} relation(s) "
            "that crossed no domain"
        )
    return crossing


# TYPING AND CYCLES ---------------------------------------------------------------------------


def build_typed_relations(relations: list[list], universe: set, schema) -> list[dict]:
    """Group the triples by relation type, in the artifact's `details`/`relations_data` shape.

    A key the vocabulary does not hold falls back to the schema's own fallback relation, or
    is dropped when it declares none.
    """
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


def report_against_order(typed: list[dict], positions: dict, prerequisite: str | None) -> None:
    """Log how many prerequisite edges point at a concept the material introduces later.

    `A → B` reads «B before A», so this measures the draft against the one witness that is
    not a model. It is reported and never acted on: the order is evidence and not a verdict,
    and a textbook may well present a consequence before its foundation.
    """
    if not positions or prerequisite is None:
        return
    group = next((g for g in typed if g["details"]["verbose"] == prerequisite), None)
    if group is None:
        return
    edges = [(s, t) for s, ts in group["relations_data"].items() for t in ts]
    judged = [(s, t) for s, t in edges if s in positions and t in positions]
    backwards = [(s, t) for s, t in judged if positions[t] > positions[s]]
    logger.info(
        f"Order of the material: {len(backwards)} of {len(judged)} edge(s) of "
        f"«{prerequisite}» point at a concept the material introduces later"
    )


def break_cycles(
    typed: list[dict], positions: dict | None = None, prerequisite: str | None = None
) -> list[dict]:
    """Remove one edge per cycle of every `directed`+`acyclic` relation, so the loader loads.

    For the prerequisite relation the edge that goes is the one that most contradicts the
    order of the material; everywhere else it is the DFS BACK EDGE, and no attempt is made to
    keep the semantically correct direction — fixing a relation written backwards is manual.
    """
    positions = positions or {}
    for group in typed:
        details = group["details"]
        if not (details.get("acyclic") and details.get("directed")):
            continue
        ordered = bool(positions) and details["verbose"] == prerequisite
        graph = nx.DiGraph()
        for source, targets in group["relations_data"].items():
            graph.add_edges_from((source, target) for target in targets)
        removed = []
        while not nx.is_directed_acyclic_graph(graph):
            cycle = [edge[:2] for edge in nx.find_cycle(graph)]
            source, target = most_backwards(cycle, positions) if ordered else cycle[-1]
            graph.remove_edge(source, target)
            removed.append((source, target))
        if not removed:
            continue
        rebuilt = defaultdict(list)
        for source, target in graph.edges():
            rebuilt[source].append(target)
        group["relations_data"] = {s: sorted(rebuilt[s]) for s in sorted(rebuilt)}
        logger.warning(
            f"Broke {len(removed)} back edge(s) in «{details['verbose']}»: {removed}"
        )
    return typed


def most_backwards(cycle: list[tuple[str, str]], positions: dict) -> tuple[str, str]:
    """The edge of a cycle whose target is introduced furthest AFTER its source."""

    def lag(edge: tuple[str, str]) -> float:
        """How far after its source a target is introduced; `-inf` when either is unknown."""
        source, target = edge
        if source not in positions or target not in positions:
            return float("-inf")
        return positions[target] - positions[source]

    return max(cycle, key=lag)

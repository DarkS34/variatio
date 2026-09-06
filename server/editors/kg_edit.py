"""Editing the knowledge graph: domains, concepts, relations and descriptions.

The graph is the vocabulary every later stage is confined to, so it gets reviewed
before anything is tagged against it. Each write is validated by loading the result
through `KnowledgeGraph` — the same class the pipeline uses — and only then replacing
the file.
"""

import json
import tempfile
from pathlib import Path

from variatio import entrypoints
from variatio.core.workspace import Workspace
from variatio.instance.exemplars_profile import ITEM_TYPE_KEY
from variatio.instance.knowledge_graph import KnowledgeGraph

from .. import approvals, deps, storage

ARTIFACT = approvals.KNOWLEDGE_GRAPH


class KGError(ValueError):
    """A graph edit that the caller can be told about, in Spanish."""


# READ ---------------------------------------------------------------------------------------


def summary(ws: Workspace) -> dict:
    """Return the graph as the screen reads it: domains, concepts with counts, relations."""
    graph_raw = raw(ws)
    graph = _load(graph_raw)
    descriptions = entrypoints.load_concept_descriptions(ws)
    exemplars, by_type = _exemplar_counts(_bank(ws))
    degrees = _degrees(graph)

    concepts = [
        {
            "name": name,
            "domain": graph.concept_domain[name],
            "taggable": name not in graph.generic_non_taggable_concepts,
            "degree": degrees.get(name, 0),
            "description": descriptions.get(name),
            "exemplars": exemplars.get(name, 0),
            "exemplars_by_type": by_type.get(name, {}),
        }
        for name in graph.all_concepts
    ]

    return {
        "path": str(approvals.current_path(ws, ARTIFACT)),
        "domains": [
            {"name": domain, "concepts": list(names)}
            for domain, names in graph.concepts_by_domains.items()
        ],
        "concepts": concepts,
        "relations": [
            {
                "name": name,
                "details": details,
                "edges": graph.graphs[name].number_of_edges(),
            }
            for name, details in graph.relation_details.items()
        ],
        "totals": {
            "domains": len(graph.concepts_by_domains),
            "concepts": len(graph.all_concepts),
            "taggable": len(graph.taggable_concepts),
            "described": sum(1 for c in graph.taggable_concepts if descriptions.get(c)),
            "with_exemplars": sum(1 for c in graph.taggable_concepts if exemplars.get(c)),
            "taggability_reviewed": bool(graph_raw.get("taggability_reviewed", False)),
        },
    }


def _exemplar_counts(bank: dict) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    """Count exemplars per concept, and per concept and modality.

    Keyed by the modality the item DECLARES, so this stays a fact about the bank alone: the
    graph screen has no upstreams and must not start reading the exemplars profile. An item
    with no `item_type` is counted in the total and in no modality, exactly as
    `VariantGenerator._is_type` does whenever the profile declares more than one.
    """
    exemplars: dict[str, int] = {}
    by_type: dict[str, dict[str, int]] = {}
    for item in bank.values():
        declared = item.get(ITEM_TYPE_KEY)
        for concept in item.get("concepts") or []:
            exemplars[concept] = exemplars.get(concept, 0) + 1
            if declared:
                counts = by_type.setdefault(concept, {})
                counts[declared] = counts.get(declared, 0) + 1
    return exemplars, by_type


def _bank(ws: Workspace) -> dict:
    """Read the exemplars bank, empty when the workspace has none yet."""
    return storage.read_json(ws.exemplars_bank_path) or {}


def _degrees(graph: KnowledgeGraph) -> dict[str, int]:
    """Count each concept's edges, summed over every relation."""
    degrees: dict[str, int] = dict.fromkeys(graph.all_concepts, 0)
    for nx_graph in graph.graphs.values():
        for concept in graph.all_concepts:
            if concept in nx_graph:
                degrees[concept] += nx_graph.degree(concept)
    return degrees


def descriptions(ws: Workspace) -> dict:
    """Return every taggable concept's description, with the passages it was written from.

    The anchoring travels with the descriptions because it is what answers for them: it is
    what lets a reviewer tell a description of the material from a description of what the
    model already knew.
    """
    graph = _load(raw(ws))
    stored = entrypoints.load_concept_descriptions(ws)
    sources = entrypoints.load_concept_sources(ws)
    anchored = sources["concepts"]
    return {
        "descriptions": {c: stored.get(c) for c in graph.taggable_concepts},
        "missing": [c for c in graph.taggable_concepts if not stored.get(c)],
        "sources": {c: anchored[c] for c in graph.taggable_concepts if anchored.get(c)},
        "many_documents": len(sources["documents"]) > 1,
        "unanchored": [c for c in graph.taggable_concepts if not anchored.get(c)],
    }


def set_description(ws: Workspace, concept: str, text: str) -> dict:
    """Overwrite one concept's description by hand. Raises KGError for an unknown concept."""
    graph = _load(raw(ws))
    if concept not in graph.all_concepts:
        raise KGError(f"'{concept}' no existe en el grafo")
    stored = entrypoints.load_concept_descriptions(ws)
    stored[concept] = text
    entrypoints.save_concept_descriptions(stored, ws)
    # The embedding cache fingerprints the descriptions and invalidates itself; the
    # in-memory context does not, hence the explicit drop.
    deps.invalidate(ws.slug, f"descripción de '{concept}' editada")
    return {"concept": concept, "description": text}


def raw(ws: Workspace) -> dict:
    """Read the graph that wins — curated over draft. Raises KGError when there is none."""
    path = approvals.current_path(ws, ARTIFACT)
    if path is None:
        raise KGError("Todavía no hay grafo de conocimiento")
    return storage.read_json(path)


# WRITE --------------------------------------------------------------------------------------


def load_graph(ws: Workspace, graph_raw: dict | None = None) -> KnowledgeGraph:
    """Load the workspace's graph, or a candidate the caller already has in hand."""
    return _load(graph_raw if graph_raw is not None else raw(ws))


def replace(ws: Workspace, graph_raw: dict) -> dict:
    """Overwrite the whole graph with the one given."""
    return _save(ws, graph_raw, "grafo de conocimiento reemplazado")


def set_non_taggable(ws: Workspace, concepts: list[str]) -> dict:
    """Record which concepts do not work as labels, and mark the review as done.

    Both the job's verdict and a hand edit come through here, and both set
    `taggability_reviewed` in the same write, so the file is left in one shape either way.
    Names the graph does not hold are dropped rather than stored.
    """
    graph_raw = raw(ws)
    kept = sorted(set(concepts) & _all_concepts(graph_raw))
    graph_raw["generic_non_taggable_concepts"] = kept
    graph_raw["taggability_reviewed"] = True
    _save(ws, graph_raw, "etiquetabilidad revisada")
    return {"non_taggable": len(kept)}


def _save(ws: Workspace, graph_raw: dict, note: str) -> dict:
    """Validate, write as the curated graph, reopen its review and drop the cached context."""
    _load(graph_raw)
    target = approvals.canonical_path(ws, ARTIFACT)
    storage.write_json(target, graph_raw, ws=ws, artifact=ARTIFACT)
    approvals.Approvals(ws).invalidate(ARTIFACT)
    deps.invalidate(ws.slug, note)
    return {"path": str(target), "hash": storage.sha256_of(target)}


def _load(graph_raw: dict) -> KnowledgeGraph:
    """Load a candidate graph through the pipeline's own class. Raises KGError if it will not.

    The class takes a path, so the candidate goes through a temporary file: validating with
    anything other than the loader the pipeline uses would validate the wrong thing.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(graph_raw, tmp, ensure_ascii=False)
        probe = Path(tmp.name)
    try:
        return KnowledgeGraph(str(probe))
    except (KeyError, ValueError, TypeError) as exc:
        raise KGError(f"El grafo resultante no es válido: {exc}") from exc
    finally:
        probe.unlink(missing_ok=True)


def _all_concepts(graph_raw: dict) -> set[str]:
    """Every concept name in the graph, whatever domain it sits in."""
    return {c for names in graph_raw["concepts_by_domains"].values() for c in names}


def _bank_references(ws: Workspace, concept: str) -> int:
    """How many bank items are tagged with this concept."""
    return sum(
        1 for item in _bank(ws).values() if concept in (item.get("concepts") or [])
    )


# Domains -------------------------------------------------------------------------------------


def add_domain(ws: Workspace, name: str, after: str | None = None) -> dict:
    """Add an empty domain, at the end or right after another one.

    The order of the domains is the syllabus's teaching order, so inserting rebuilds the
    dict rather than appending.
    """
    graph_raw = raw(ws)
    domains = graph_raw["concepts_by_domains"]
    if name in domains:
        raise KGError(f"El dominio '{name}' ya existe")
    if after is not None and after not in domains:
        raise KGError(f"El dominio '{after}' no existe")
    if after is None:
        domains[name] = []
    else:
        rebuilt: dict[str, list[str]] = {}
        for key, value in domains.items():
            rebuilt[key] = value
            if key == after:
                rebuilt[name] = []
        graph_raw["concepts_by_domains"] = rebuilt
    return _save(ws, graph_raw, f"dominio '{name}' añadido")


def reorder_domains(ws: Workspace, order: list[str]) -> dict:
    """Re-lay the domains in the given order, which must name every one of them exactly once."""
    graph_raw = raw(ws)
    domains = graph_raw["concepts_by_domains"]
    if sorted(order) != sorted(domains):
        raise KGError(
            "El orden tiene que nombrar exactamente los dominios que existen, "
            "una sola vez cada uno"
        )
    graph_raw["concepts_by_domains"] = {name: domains[name] for name in order}
    return _save(ws, graph_raw, "orden de las unidades cambiado")


def rename_domain(ws: Workspace, name: str, new_name: str) -> dict:
    """Rename one domain, keeping its place in the order."""
    graph_raw = raw(ws)
    domains = graph_raw["concepts_by_domains"]
    if name not in domains:
        raise KGError(f"El dominio '{name}' no existe")
    if new_name in domains:
        raise KGError(f"El dominio '{new_name}' ya existe")
    graph_raw["concepts_by_domains"] = {
        (new_name if key == name else key): value for key, value in domains.items()
    }
    return _save(ws, graph_raw, f"dominio '{name}' renombrado")


def delete_domain(ws: Workspace, name: str, move_to: str | None = None) -> dict:
    """Delete a domain, moving its concepts elsewhere or purging them with it.

    With no `move_to` the concepts go too — edges, descriptions and anchoring included.
    """
    graph_raw = raw(ws)
    domains = graph_raw["concepts_by_domains"]
    if name not in domains:
        raise KGError(f"El dominio '{name}' no existe")

    orphans = list(domains.pop(name))
    if orphans and move_to is None:
        for concept in orphans:
            _purge_concept(ws, graph_raw, concept)
    elif orphans:
        if move_to not in domains:
            raise KGError(f"El dominio destino '{move_to}' no existe")
        domains[move_to].extend(c for c in orphans if c not in domains[move_to])

    return _save(ws, graph_raw, f"dominio '{name}' eliminado")


# Concepts ------------------------------------------------------------------------------------


def add_concept(ws: Workspace, name: str, domain: str, taggable: bool = True) -> dict:
    """Add a concept to a domain, optionally already marked as no good as a label."""
    graph_raw = raw(ws)
    if name in _all_concepts(graph_raw):
        raise KGError(f"El concepto '{name}' ya existe")
    if domain not in graph_raw["concepts_by_domains"]:
        raise KGError(f"El dominio '{domain}' no existe")
    graph_raw["concepts_by_domains"][domain].append(name)
    if not taggable:
        graph_raw.setdefault("generic_non_taggable_concepts", []).append(name)
    return _save(ws, graph_raw, f"concepto '{name}' añadido")


def update_concept(
    ws: Workspace,
    name: str,
    new_name: str | None = None,
    domain: str | None = None,
    taggable: bool | None = None,
) -> dict:
    """Rename, move or re-mark a concept, carrying everything keyed by its name with it.

    A rename reaches the relations, the description and the corpus anchoring, and the
    result reports how many bank items still refer to the old name — nothing here retags
    the bank.
    """
    graph_raw = raw(ws)
    if name not in _all_concepts(graph_raw):
        raise KGError(f"El concepto '{name}' no existe")

    target = new_name or name
    renamed = bool(new_name) and new_name != name
    if renamed and new_name in _all_concepts(graph_raw):
        raise KGError(f"El concepto '{new_name}' ya existe")

    _relocate(graph_raw["concepts_by_domains"], name, target, domain)

    if renamed:
        _rename_everywhere(ws, graph_raw, name, new_name)

    _set_taggable(graph_raw, target, taggable)

    references = _bank_references(ws, name) if renamed else 0
    result = _save(ws, graph_raw, f"concepto '{name}' modificado")
    result["bank_references"] = references
    return result


def _relocate(domains: dict, name: str, target: str, domain: str | None) -> None:
    """Move a concept into `domain`, or leave it exactly where it is.

    STAYING PUT IS THE COMMON CASE AND IT MUST NOT MOVE THE CONCEPT. This used to remove
    the name and append it, whatever the destination, so every edit that did not change
    the unit — marking a concept as not serving as a label, above all — dropped its row to
    the bottom of the list under the hand that pressed the switch. A rename replaces the
    entry in place for the same reason.

    Raises KGError when the destination does not exist.
    """
    current = next(d for d, names in domains.items() if name in names)
    destination = domain or current
    if destination not in domains:
        raise KGError(f"El dominio '{destination}' no existe")
    if destination == current:
        if target != name:
            names = domains[current]
            names[names.index(name)] = target
        return
    domains[current] = [c for c in domains[current] if c != name]
    if target not in domains[destination]:
        domains[destination].append(target)


def _rename_everywhere(ws: Workspace, graph_raw: dict, name: str, new_name: str) -> None:
    """Carry a rename through the non-taggable list, both ends of every edge, and the cache."""
    graph_raw["generic_non_taggable_concepts"] = [
        new_name if c == name else c
        for c in graph_raw.get("generic_non_taggable_concepts", [])
    ]
    for relation in graph_raw.get("relations", []):
        data = relation.get("relations_data", {})
        if name in data:
            data[new_name] = data.pop(name)
        for source, targets in data.items():
            data[source] = [new_name if t == name else t for t in targets]
    _move_description(ws, name, new_name)


def _move_description(ws: Workspace, name: str, new_name: str) -> None:
    """Carry a concept's description and corpus anchoring over to its new name.

    Both caches are keyed by concept name and nothing else invalidates them, so a rename
    without this strands the text and the passages under a key nobody will ask for again.
    """
    stored = entrypoints.load_concept_descriptions(ws)
    if name in stored:
        stored[new_name] = stored.pop(name)
        entrypoints.save_concept_descriptions(stored, ws)
    _rekey_sources(ws, name, new_name)


def _set_taggable(graph_raw: dict, concept: str, taggable: bool | None) -> None:
    """Add or remove a concept from the non-taggable list; `None` leaves it as it is."""
    non_taggable = set(graph_raw.get("generic_non_taggable_concepts", []))
    if taggable is True:
        non_taggable.discard(concept)
    elif taggable is False:
        non_taggable.add(concept)
    graph_raw["generic_non_taggable_concepts"] = sorted(non_taggable)


def delete_concept(ws: Workspace, name: str) -> dict:
    """Remove a concept from the graph, reporting how many bank items still name it."""
    graph_raw = raw(ws)
    if name not in _all_concepts(graph_raw):
        raise KGError(f"El concepto '{name}' no existe")
    references = _bank_references(ws, name)
    _purge_concept(ws, graph_raw, name)
    result = _save(ws, graph_raw, f"concepto '{name}' eliminado")
    result["bank_references"] = references
    return result


def _purge_concept(ws: Workspace, graph_raw: dict, name: str) -> None:
    """Erase a concept from its domain, the non-taggable list, every relation and the cache."""
    graph_raw["concepts_by_domains"] = {
        domain: [c for c in names if c != name]
        for domain, names in graph_raw["concepts_by_domains"].items()
    }
    graph_raw["generic_non_taggable_concepts"] = [
        c for c in graph_raw.get("generic_non_taggable_concepts", []) if c != name
    ]
    for relation in graph_raw.get("relations", []):
        data = relation.get("relations_data", {})
        data.pop(name, None)
        for source, targets in list(data.items()):
            data[source] = [t for t in targets if t != name]
    _forget_description(ws, name)


def _forget_description(ws: Workspace, name: str) -> None:
    """Drop a deleted concept's description and corpus anchoring."""
    stored = entrypoints.load_concept_descriptions(ws)
    if stored.pop(name, None) is not None:
        entrypoints.save_concept_descriptions(stored, ws)
    _rekey_sources(ws, name, None)


def _rekey_sources(ws: Workspace, name: str, new_name: str | None) -> None:
    """Move a concept's corpus passages to a new name, or drop them when it is `None`."""
    sources = entrypoints.load_concept_sources(ws)
    entries = sources["concepts"].pop(name, None)
    definition = sources.get("definitions", {}).pop(name, None)
    if entries is None and definition is None:
        return
    if new_name is not None:
        if entries is not None:
            sources["concepts"][new_name] = entries
        if definition is not None:
            sources["definitions"][new_name] = definition
    storage.write_json(ws.concept_sources_path, sources)


# Relations -----------------------------------------------------------------------------------


def add_edge(ws: Workspace, verb: str, source: str, target: str) -> dict:
    """Add one edge. Raises KGError for an unknown concept, a self-loop or a duplicate."""
    graph_raw = raw(ws)
    concepts = _all_concepts(graph_raw)
    for concept in (source, target):
        if concept not in concepts:
            raise KGError(f"El concepto '{concept}' no existe")
    if source == target:
        raise KGError("Una relación no puede unir un concepto consigo mismo")

    data = _relation(graph_raw, verb).setdefault("relations_data", {})
    targets = data.setdefault(source, [])
    if target in targets:
        raise KGError(f"'{source} {verb} {target}' ya existe")
    targets.append(target)
    return _save(ws, graph_raw, f"relación '{source} {verb} {target}' añadida")


def remove_edge(ws: Workspace, verb: str, source: str, target: str) -> dict:
    """Remove one edge, whichever way round it is stored. Raises KGError if there is none.

    Both orientations are tried because an undirected relation is stored under whichever
    endpoint the builder happened to write first.
    """
    graph_raw = raw(ws)
    data = _relation(graph_raw, verb).get("relations_data", {})
    changed = False
    for src, tgt in ((source, target), (target, source)):
        if tgt in data.get(src, []):
            data[src] = [t for t in data[src] if t != tgt]
            changed = True
    if not changed:
        raise KGError(f"No existe '{source} {verb} {target}'")
    return _save(ws, graph_raw, f"relación '{source} {verb} {target}' eliminada")


def _relation(graph_raw: dict, verb: str) -> dict:
    """Find a relation by its verbose label, which is how the graph file indexes them."""
    for relation in graph_raw.get("relations", []):
        if (relation.get("details") or {}).get("verbose") == verb:
            return relation
    raise KGError(f"La relación '{verb}' no existe")


def neighbours(ws: Workspace, concept: str) -> dict:
    """Return one concept's edges per relation, split into `out` and `in` where directed."""
    graph = _load(raw(ws))
    if concept not in graph.all_concepts:
        raise KGError(f"El concepto '{concept}' no existe")
    out: dict[str, dict] = {}
    for verb, nx_graph in graph.graphs.items():
        if concept not in nx_graph:
            continue
        if nx_graph.is_directed():
            out[verb] = {
                "out": graph.neighbors(concept, verb, "out"),
                "in": graph.neighbors(concept, verb, "in"),
                "directed": True,
            }
        else:
            out[verb] = {"out": graph.neighbors(concept, verb), "in": [], "directed": False}
    return out

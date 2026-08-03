"""Editing the knowledge graph: domains, concepts, relations and descriptions.

The graph is the vocabulary every later stage is confined to, so it gets reviewed
before anything is tagged against it. Each write is validated by loading the result
through `KnowledgeGraph` — the same class the pipeline uses — and only then replacing
the file.
"""

import json
import tempfile
from pathlib import Path

from variant_generator import config, stages
from variant_generator.knowledge_graph import KnowledgeGraph

from .. import deps, review, storage

ARTIFACT = review.KNOWLEDGE_GRAPH


class KGError(ValueError):
    pass


# READ ---------------------------------------------------------------------------------------


def raw() -> dict:
    path = review.current_path(ARTIFACT)
    if path is None:
        raise KGError("Todavía no hay grafo de conocimiento")
    return storage.read_json(path)


def _bank() -> dict:
    return storage.read_json(config.EXEMPLARS_BANK_PATH) or {}


def summary() -> dict:
    graph_raw = raw()
    graph = _load(graph_raw)
    descriptions = stages.load_concept_descriptions()

    exemplars: dict[str, int] = {}
    for item in _bank().values():
        for concept in item.get("concepts") or []:
            exemplars[concept] = exemplars.get(concept, 0) + 1

    degrees: dict[str, int] = dict.fromkeys(graph.all_concepts, 0)
    for nx_graph in graph.graphs.values():
        for concept in graph.all_concepts:
            if concept in nx_graph:
                degrees[concept] += nx_graph.degree(concept)

    concepts = [
        {
            "name": name,
            "domain": graph.concept_domain[name],
            "taggable": name not in graph.generic_non_taggable_concepts,
            "degree": degrees.get(name, 0),
            "description": descriptions.get(name),
            "exemplars": exemplars.get(name, 0),
        }
        for name in graph.all_concepts
    ]

    return {
        "path": str(review.current_path(ARTIFACT)),
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
        },
    }


def descriptions() -> dict:
    graph = _load(raw())
    stored = stages.load_concept_descriptions()
    return {
        "descriptions": {c: stored.get(c) for c in graph.taggable_concepts},
        "missing": [c for c in graph.taggable_concepts if not stored.get(c)],
    }


def set_description(concept: str, text: str) -> dict:
    graph = _load(raw())
    if concept not in graph.all_concepts:
        raise KGError(f"'{concept}' no existe en el grafo")
    stored = stages.load_concept_descriptions()
    stored[concept] = text
    stages.save_concept_descriptions(stored)
    # The concepts embedding cache fingerprints the descriptions, so it invalidates
    # itself; the in-memory context does not, hence the explicit drop.
    deps.invalidate(f"descripción de '{concept}' editada")
    return {"concept": concept, "description": text}


# WRITE --------------------------------------------------------------------------------------


def _load(graph_raw: dict) -> KnowledgeGraph:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
        json.dump(graph_raw, tmp, ensure_ascii=False)
        probe = Path(tmp.name)
    try:
        return KnowledgeGraph(str(probe))
    except (KeyError, ValueError, TypeError) as exc:
        raise KGError(f"El grafo resultante no es válido: {exc}") from exc
    finally:
        probe.unlink(missing_ok=True)


def load_graph(graph_raw: dict | None = None) -> KnowledgeGraph:
    return _load(graph_raw if graph_raw is not None else raw())


def _save(graph_raw: dict, note: str) -> dict:
    _load(graph_raw)
    target = review.canonical_path(ARTIFACT)
    storage.write_json(target, graph_raw, artifact=ARTIFACT)
    review.ReviewState().invalidate(ARTIFACT)
    deps.invalidate(note)
    return {"path": str(target), "hash": storage.sha256_of(target)}


def replace(graph_raw: dict) -> dict:
    return _save(graph_raw, "grafo de conocimiento reemplazado")


def _all_concepts(graph_raw: dict) -> set[str]:
    return {c for names in graph_raw["concepts_by_domains"].values() for c in names}


def _bank_references(concept: str) -> int:
    return sum(
        1 for item in _bank().values() if concept in (item.get("concepts") or [])
    )


# Domains -------------------------------------------------------------------------------------


def add_domain(name: str) -> dict:
    graph_raw = raw()
    if name in graph_raw["concepts_by_domains"]:
        raise KGError(f"El dominio '{name}' ya existe")
    graph_raw["concepts_by_domains"][name] = []
    return _save(graph_raw, f"dominio '{name}' añadido")


def rename_domain(name: str, new_name: str) -> dict:
    graph_raw = raw()
    domains = graph_raw["concepts_by_domains"]
    if name not in domains:
        raise KGError(f"El dominio '{name}' no existe")
    if new_name in domains:
        raise KGError(f"El dominio '{new_name}' ya existe")
    graph_raw["concepts_by_domains"] = {
        (new_name if key == name else key): value for key, value in domains.items()
    }
    return _save(graph_raw, f"dominio '{name}' renombrado")


def delete_domain(name: str, move_to: str | None = None) -> dict:
    graph_raw = raw()
    domains = graph_raw["concepts_by_domains"]
    if name not in domains:
        raise KGError(f"El dominio '{name}' no existe")

    orphans = list(domains.pop(name))
    if orphans and move_to is None:
        for concept in orphans:
            _purge_concept(graph_raw, concept)
    elif orphans:
        if move_to not in domains:
            raise KGError(f"El dominio destino '{move_to}' no existe")
        domains[move_to].extend(c for c in orphans if c not in domains[move_to])

    return _save(graph_raw, f"dominio '{name}' eliminado")


# Concepts ------------------------------------------------------------------------------------


def add_concept(name: str, domain: str, taggable: bool = True) -> dict:
    graph_raw = raw()
    if name in _all_concepts(graph_raw):
        raise KGError(f"El concepto '{name}' ya existe")
    if domain not in graph_raw["concepts_by_domains"]:
        raise KGError(f"El dominio '{domain}' no existe")
    graph_raw["concepts_by_domains"][domain].append(name)
    if not taggable:
        graph_raw.setdefault("generic_non_taggable_concepts", []).append(name)
    return _save(graph_raw, f"concepto '{name}' añadido")


def update_concept(
    name: str,
    new_name: str | None = None,
    domain: str | None = None,
    taggable: bool | None = None,
) -> dict:
    graph_raw = raw()
    if name not in _all_concepts(graph_raw):
        raise KGError(f"El concepto '{name}' no existe")

    target = new_name or name
    if new_name and new_name != name and new_name in _all_concepts(graph_raw):
        raise KGError(f"El concepto '{new_name}' ya existe")

    domains = graph_raw["concepts_by_domains"]
    current_domain = next(d for d, names in domains.items() if name in names)
    destination = domain or current_domain
    if destination not in domains:
        raise KGError(f"El dominio '{destination}' no existe")

    domains[current_domain] = [c for c in domains[current_domain] if c != name]
    if target not in domains[destination]:
        domains[destination].append(target)

    if new_name and new_name != name:
        _rename_everywhere(graph_raw, name, new_name)

    non_taggable = set(graph_raw.get("generic_non_taggable_concepts", []))
    if taggable is True:
        non_taggable.discard(target)
    elif taggable is False:
        non_taggable.add(target)
    graph_raw["generic_non_taggable_concepts"] = sorted(non_taggable)

    references = _bank_references(name) if new_name and new_name != name else 0
    result = _save(graph_raw, f"concepto '{name}' modificado")
    result["bank_references"] = references
    return result


def delete_concept(name: str) -> dict:
    graph_raw = raw()
    if name not in _all_concepts(graph_raw):
        raise KGError(f"El concepto '{name}' no existe")
    references = _bank_references(name)
    _purge_concept(graph_raw, name)
    result = _save(graph_raw, f"concepto '{name}' eliminado")
    result["bank_references"] = references
    return result


def _purge_concept(graph_raw: dict, name: str) -> None:
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
    _forget_description(name)


def _rename_everywhere(graph_raw: dict, name: str, new_name: str) -> None:
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
    _move_description(name, new_name)


# The description cache is keyed by concept name and nothing else invalidates it:
# a rename would otherwise leave the text stranded under the old key forever.
def _move_description(name: str, new_name: str) -> None:
    stored = stages.load_concept_descriptions()
    if name in stored:
        stored[new_name] = stored.pop(name)
        stages.save_concept_descriptions(stored)


def _forget_description(name: str) -> None:
    stored = stages.load_concept_descriptions()
    if stored.pop(name, None) is not None:
        stages.save_concept_descriptions(stored)


# Relations -----------------------------------------------------------------------------------


def _relation(graph_raw: dict, verb: str) -> dict:
    for relation in graph_raw.get("relations", []):
        if (relation.get("details") or {}).get("verbose") == verb:
            return relation
    raise KGError(f"La relación '{verb}' no existe")


def add_edge(verb: str, source: str, target: str) -> dict:
    graph_raw = raw()
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
    return _save(graph_raw, f"relación '{source} {verb} {target}' añadida")


def remove_edge(verb: str, source: str, target: str) -> dict:
    graph_raw = raw()
    data = _relation(graph_raw, verb).get("relations_data", {})
    changed = False
    for src, tgt in ((source, target), (target, source)):
        if tgt in data.get(src, []):
            data[src] = [t for t in data[src] if t != tgt]
            changed = True
    if not changed:
        raise KGError(f"No existe '{source} {verb} {target}'")
    return _save(graph_raw, f"relación '{source} {verb} {target}' eliminada")


def neighbours(concept: str) -> dict:
    graph = _load(raw())
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

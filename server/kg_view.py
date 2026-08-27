"""The graph as the canvas wants it: positional nodes and links, grouped by domain.

Nodes and links are emitted as positional arrays because they dominate the payload
and the whole graph is re-read on every load of the screen.
"""

import re
import unicodedata
from collections import defaultdict
from datetime import datetime

from variatio.instance.knowledge_graph import KnowledgeGraph
from variatio.instance.relations import RelationSchema


def _slug(text: str) -> str:
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "_", stripped.lower()).strip("_") or "relation"


# `key` is the verbose label because that is the name the edit endpoints speak.
# `type` is the schema key when the relation is one the builder knows about: it is
# what gives a relation the same colour and the same meaning across instances.
# The schema and the prerequisite label are the WORKSPACE's, not the installation's: they
# are written into `knowledge_graph.json` in the language the instance was built in, so
# reading a global here drew one instance's graph with another instance's vocabulary.
def _relation_entry(verbose: str, details: dict, schema: RelationSchema) -> dict:
    known = schema.by_verbose(verbose)
    return {
        "key": verbose,
        "verbose": verbose,
        "type": known.key if known is not None else _slug(verbose),
        "directed": bool(details.get("directed", True)),
        "acyclic": bool(details.get("acyclic", False)),
        "use_in_embedding": bool(details.get("use_in_embedding", True)),
        "prerequisite": verbose == schema.prerequisite_verbose,
        "count": 0,
    }


def build(
    graph_raw: dict,
    kg: KnowledgeGraph,
    schema: RelationSchema,
    title: str = "Grafo de conocimiento",
) -> dict:
    names = list(kg.all_concepts)
    node_index = {name: i for i, name in enumerate(names)}

    counts: dict[str, int] = defaultdict(int)
    for name in names:
        counts[kg.concept_domain[name]] += 1
    groups = [
        {"name": domain, "count": counts[domain]} for domain in kg.domains if counts[domain]
    ]
    group_index = {group["name"]: i for i, group in enumerate(groups)}

    relations = [
        _relation_entry(verbose, details, schema)
        for verbose, details in kg.relation_details.items()
    ]
    relation_index = {relation["key"]: i for i, relation in enumerate(relations)}

    links: list[list[int]] = []
    seen: set[tuple] = set()
    degree = [0] * len(names)
    for verbose, nx_graph in kg.graphs.items():
        r = relation_index[verbose]
        symmetric = not nx_graph.is_directed()
        for source, target in nx_graph.edges():
            s, t = node_index.get(source), node_index.get(target)
            # Self-loops have nothing to draw; a symmetric relation stated in both
            # directions is one edge, not two lines on top of each other.
            if s is None or t is None or s == t:
                continue
            signature = (min(s, t), max(s, t), r) if symmetric else (s, t, r)
            if signature in seen:
                continue
            seen.add(signature)
            links.append([s, t, r])
            relations[r]["count"] += 1
            degree[s] += 1
            degree[t] += 1

    nodes = [
        [
            name,
            group_index[kg.concept_domain[name]],
            1 if name in kg.generic_non_taggable_concepts else 0,
        ]
        for name in names
    ]

    prerequisite = next(
        (i for i, relation in enumerate(relations) if relation["prerequisite"]), None
    )

    return {
        "meta": {
            "title": title,
            "source": "instance",
            "kind": "curated",
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "isolated": sum(1 for d in degree if d == 0),
            "prerequisite": prerequisite,
        },
        "relations": relations,
        "groups": groups,
        "nodes": nodes,
        "links": links,
    }

"""The graph as the canvas wants it: positional nodes and links, grouped by domain.

kg-builder already computes this view model for its standalone HTML viewer, so we
reuse it when it is installed. It is an optional extra, though, and the graph screen
is not optional, so there is a local equivalent that produces the same shape from
`KnowledgeGraph` alone.
"""

from collections import defaultdict
from datetime import datetime

from variant_generator.knowledge_graph import KnowledgeGraph


def build(graph_raw: dict, kg: KnowledgeGraph, title: str = "Grafo de conocimiento") -> dict:
    try:
        from kg_builder import BUILTIN_SCHEMAS
        from kg_builder.visualization import build_view_model

        from variant_generator import config

        return build_view_model(
            graph_raw,
            BUILTIN_SCHEMAS.get(config.KG_RELATION_SCHEMA),
            title=title,
            source="instance",
        )
    except Exception:  # noqa: BLE001 - the local fallback is not a degraded mode
        return _local(kg, title)


def _local(kg: KnowledgeGraph, title: str) -> dict:
    names = list(kg.all_concepts)
    node_index = {name: i for i, name in enumerate(names)}

    sizes: dict[str, int] = defaultdict(int)
    for name in names:
        sizes[kg.concept_domain[name]] += 1
    groups = [
        {"name": name, "count": count}
        for name, count in sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    group_index = {group["name"]: i for i, group in enumerate(groups)}

    # `verbose` is the name the edit endpoints speak; kg-builder's view model carries
    # it too, so the client can identify a relation the same way on either path.
    relations = [
        {
            "key": verb,
            "verbose": verb,
            "directed": bool(details.get("directed", True)),
            "acyclic": bool(details.get("acyclic", False)),
            "use_in_embedding": bool(details.get("use_in_embedding", True)),
            "count": 0,
        }
        for verb, details in kg.relation_details.items()
    ]
    relation_index = {relation["key"]: i for i, relation in enumerate(relations)}

    links: list[list[int]] = []
    seen: set[tuple] = set()
    degree = [0] * len(names)
    for verb, nx_graph in kg.graphs.items():
        r = relation_index[verb]
        symmetric = not nx_graph.is_directed()
        for source, target in nx_graph.edges():
            s, t = node_index.get(source), node_index.get(target)
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

    return {
        "meta": {
            "title": title,
            "source": "instance",
            "kind": "curated",
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "isolated": sum(1 for d in degree if d == 0),
        },
        "relations": relations,
        "groups": groups,
        "nodes": nodes,
        "links": links,
    }

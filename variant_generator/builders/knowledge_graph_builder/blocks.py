"""What the model is shown: one renderer per block the KG prompts interpolate.

Pure functions over plain data, so every one of them is readable — and checkable —
without a builder, a workspace or a model.
"""

from collections import defaultdict

from ... import config


def outgoing(relations: list[list], node_map: dict) -> dict:
    out = defaultdict(list)
    for source, relation, target in relations:
        out[node_map.get(source, source)].append(f"{relation} {node_map.get(target, target)}")
    return out


# Each node is listed with its outgoing relations (remapped to survivors)
# so the model can disambiguate short or ambiguous names.
def nodes_block(
    nodes: list[str],
    relations: list[list],
    node_map: dict,
    origins: dict[str, list[int]] | None = None,
) -> str:
    edges = outgoing(relations, node_map)
    lines = []
    for n in nodes:
        evidence = "; ".join(edges[n][: config.KG_MAX_EVIDENCE_RELATIONS])
        sources = (origins or {}).get(n) or []
        line = f"- {n}"
        if evidence:
            line += f"  [{evidence}]"
        if sources:
            line += "  (" + ", ".join(f"D{i + 1}" for i in sources) + ")"
        lines.append(line)
    return "\n".join(lines)


def groups_block(groups: list[list[str]], relations: list[list], node_map: dict) -> str:
    edges = outgoing(relations, node_map)
    lines = []
    for idx, group in enumerate(groups, 1):
        lines.append(f"## Grupo {idx}")
        for name in group:
            evidence = "; ".join(edges[name][: config.KG_MAX_EVIDENCE_RELATIONS])
            lines.append(f"- {name}" + (f"  [{evidence}]" if evidence else ""))
    return "\n".join(lines)


def documents_block(documents: list[dict]) -> str:
    lines = []
    for idx, document in enumerate(documents, 1):
        label = " · ".join(document.get("titles") or []) or document.get("name", "")
        lines.append(f"- D{idx}: {label}")
    return "\n".join(lines)


def domains_block(concepts_by_domains: dict) -> str:
    return "\n\n".join(
        f"## {domain}\n" + "\n".join(f"- {c}" for c in members)
        for domain, members in concepts_by_domains.items()
    )


def concepts_block(concepts: list[str]) -> str:
    return "\n".join(f"- {c}" for c in concepts)

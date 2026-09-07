"""What the model is shown: one renderer per block the KG prompts interpolate.

Pure functions over plain data, so every one of them is readable — and checkable —
without a builder, a workspace or a model.
"""

from collections import defaultdict

from ... import config


def nodes_block(
    nodes: list[str],
    relations: list[list],
    node_map: dict,
    origins: dict[str, list[int]] | None = None,
    definitions: dict[str, str] | None = None,
) -> str:
    """One line per node: its definition, its outgoing relations and its documents.

    A node is shown as an idea and not as a bare name, which is what the model is being
    asked to judge.
    """
    edges = outgoing(relations, node_map)
    lines = []
    for n in nodes:
        evidence = "; ".join(edges[n][: config.KG_MAX_EVIDENCE_RELATIONS])
        sources = (origins or {}).get(n) or []
        line = node_line(n, definitions)
        if evidence:
            line += f"  [{evidence}]"
        if sources:
            line += "  (" + ", ".join(f"D{i + 1}" for i in sources) + ")"
        lines.append(line)
    return "\n".join(lines)


def groups_block(
    groups: list[list[str]],
    relations: list[list],
    node_map: dict,
    definitions: dict[str, str] | None = None,
) -> str:
    """The candidate merge groups, each under its own heading."""
    edges = outgoing(relations, node_map)
    lines = []
    for idx, group in enumerate(groups, 1):
        lines.append(f"## Grupo {idx}")
        for name in group:
            evidence = "; ".join(edges[name][: config.KG_MAX_EVIDENCE_RELATIONS])
            lines.append(node_line(name, definitions) + (f"  [{evidence}]" if evidence else ""))
    return "\n".join(lines)


def outgoing(relations: list[list], node_map: dict) -> dict:
    """The outgoing edges of each node, remapped to the names that survived."""
    out = defaultdict(list)
    for source, relation, target in relations:
        out[node_map.get(source, source)].append(f"{relation} {node_map.get(target, target)}")
    return out


def ordered(names: list[str], positions: dict[str, int] | None) -> list[str]:
    """Sort names by the order the material introduces them in.

    Unknown positions go last, and ties keep the alphabetical order so the block is stable
    between two runs over the same corpus.
    """
    positions = positions or {}
    return sorted(names, key=lambda n: (n not in positions, positions.get(n, 0), n))


def documents_block(documents: list[dict]) -> str:
    """The corpus as a numbered list, each document under the `D<n>` the nodes cite."""
    lines = []
    for idx, document in enumerate(documents, 1):
        label = " · ".join(document.get("titles") or []) or document.get("name", "")
        lines.append(f"- D{idx}: {label}")
    return "\n".join(lines)


def outline_block(outline: list[dict], documents: list[dict] | None = None) -> str:
    """The corpus's headings as a numbered index, naming the document when there are several."""
    names = [d.get("name", "") for d in (documents or [])]
    lines = []
    for index, entry in enumerate(outline, 1):
        position = entry.get("document")
        document = names[position] if isinstance(position, int) and position < len(names) else ""
        suffix = f"  ({document})" if len(names) > 1 and document else ""
        lines.append(f"{index}. {entry.get('heading', '')}{suffix}")
    return "\n".join(lines)


def domains_block(concepts_by_domains: dict, definitions: dict[str, str] | None = None) -> str:
    """The domains as headings, each with its members as bullets."""
    return "\n\n".join(
        f"## {domain}\n" + "\n".join(node_line(c, definitions) for c in members)
        for domain, members in concepts_by_domains.items()
    )


def node_line(name: str, definitions: dict[str, str] | None) -> str:
    """One node as a bullet, with its definition when the extraction wrote one."""
    definition = (definitions or {}).get(name)
    return f"- {name} — {definition}" if definition else f"- {name}"


def concepts_block(concepts: list[str]) -> str:
    """A plain bullet list of concept names."""
    return "\n".join(f"- {c}" for c in concepts)

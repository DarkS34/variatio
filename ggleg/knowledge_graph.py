import json

import networkx as nx
from loguru import logger


class KnowledgeGraph:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.concepts_by_domains: dict[str, list[str]] = data["concepts_by_domains"]
        self.all_concepts: list[str] = [c for cs in self.concepts_by_domains.values() for c in cs]
        self.concept_domain: dict[str, str] = {c: d for d, cs in self.concepts_by_domains.items() for c in cs}

        self.relation_types: dict[str, dict] = data["relation_types"]
        relations_data: dict[str, dict] = data.get("relations", {})

        unknown = set(relations_data) - set(self.relation_types)
        if unknown:
            logger.warning("Relations present in 'relations' but not declared in 'relation_types' (will be ignored): {unknown}")

        node_attrs = [(c, {"domain": self.concept_domain[c]}) for c in self.all_concepts]

        self.graphs: dict[str, nx.Graph] = {}
        for rel_name, meta in self.relation_types.items():
            GraphCls = nx.DiGraph if meta.get("directed", True) else nx.Graph
            g = GraphCls()
            g.add_nodes_from(node_attrs)
            g.add_edges_from(
                (src, tgt)
                for src, targets in relations_data.get(rel_name, {}).items()
                for tgt in targets
            )
            self.graphs[rel_name] = g

        for rel_name, meta in self.relation_types.items():
            if not meta.get("acyclic", False):
                continue
            g = self.graphs[rel_name]
            
            if not g.is_directed():
                logger.warning(f"'{rel_name}' is marked as 'acyclic' but not as 'directed' - skipping cycle validation.")
                continue
            
            if not nx.is_directed_acyclic_graph(g):
                cycle = nx.find_cycle(g)
                logger.error(f"Cycle detected in '{rel_name}': {cycle}")

        logger.success("Knowledge graph loaded ")

    def __getitem__(self, relation: str) -> nx.Graph:
        return self.graphs[relation]

    @property
    def relations(self) -> list[str]:
        return list(self.graphs)

    def neighbors(self,concept: str, relation: str, direction: str = "both") -> list[str]:
        g = self.graphs[relation]

        if not g.is_directed():
            return sorted(g.neighbors(concept))
        if direction == "out":
            return sorted(g.successors(concept))
        if direction == "in":
            return sorted(g.predecessors(concept))
        if direction == "both":
            return sorted(set(g.successors(concept)) | set(g.predecessors(concept)))

        logger.error(f"Direction must be 'out', 'in' or 'both', not {direction!r}")
        return []

    def frontier(self, mastered: set[str], relation: str) -> list[str]:
        g = self.graphs[relation]

        if not g.is_directed():
            logger.error(f"Frontier requires a directed relation; '{relation}' is not.")
            return []

        return sorted(
            n for n in g.nodes
            if n not in mastered and all(p in mastered for p in g.predecessors(n))
        )
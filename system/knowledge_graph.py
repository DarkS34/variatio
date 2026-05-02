import json

import networkx as nx
from loguru import logger


class KnowledgeGraph:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.main_theme = data.get("main_theme", None)

        self.concepts_by_domains: dict[str, list[str]] = data["concepts_by_domains"]
        self.concept_domain: dict[str, str] = {
            c: d for d, cs in self.concepts_by_domains.items() for c in cs
        }
        self.all_concepts: list[str] = [c for cs in self.concepts_by_domains.values() for c in cs]

        node_attrs = [(c, {"domain": self.concept_domain[c]}) for c in self.all_concepts]
        self.graphs: dict[str, nx.Graph] = {}
        self.relation_details: dict[str, dict] = {}

        relations_list = data.get("relations", [])
        for rel_obj in relations_list:
            details = rel_obj.get("details", {})
            rel_name = details.get("verbose", "unknown")
            rel_data = rel_obj.get("relations_data", {})

            self.relation_details[rel_name] = details

            g = nx.DiGraph() if details.get("directed", True) else nx.Graph()
            g.add_nodes_from(node_attrs)
            g.add_edges_from((src, tgt) for src, targets in rel_data.items() for tgt in targets)
            self.graphs[rel_name] = g

            if details.get("acyclic", False):
                if not g.is_directed():
                    logger.warning(f"'{rel_name}' is marked as 'acyclic' but not as 'directed' - skipping cycle validation.")
                    continue

                if not nx.is_directed_acyclic_graph(g):
                    cycle = nx.find_cycle(g)
                    logger.error(f"Cycle detected in '{rel_name}': {cycle}")

        logger.success("Knowledge graph loaded correctly")

    def __getitem__(self, relation: str) -> nx.Graph:
        return self.graphs[relation]

    def details(self, relation: str) -> dict:
        return self.relation_details[relation]

    def neighbors(self, concept: str, relation: str, direction: str = "both") -> list[str]:
        g = self.graphs[relation]

        if not g.is_directed():
            return sorted(g.neighbors(concept))
        if direction == "out":
            return sorted(g.successors(concept))
        if direction == "in":
            return sorted(g.predecessors(concept))
        if direction == "both":
            return {"out": set(g.successors(concept)), "in": set(g.predecessors(concept))}

        logger.error(f"Direction must be 'out', 'in' or 'both', not {direction!r}")
        return []
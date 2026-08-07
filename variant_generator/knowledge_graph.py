import json

import networkx as nx
from loguru import logger


class KnowledgeGraph:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.concepts_by_domains: dict[str, list[str]] = data["concepts_by_domains"]
        self.concept_domain: dict[str, str] = {
            c: d for d, cs in self.concepts_by_domains.items() for c in cs
        }
        self.all_concepts: list[str] = [c for cs in self.concepts_by_domains.values() for c in cs]

        self.generic_non_taggable_concepts: set[str] = set(
            data.get("generic_non_taggable_concepts", [])
        )
        self.taggable_concepts: list[str] = [
            c for c in self.all_concepts if c not in self.generic_non_taggable_concepts
        ]

        self.graphs: dict[str, nx.Graph] = {}
        self.relation_details: dict[str, dict] = {}
        self._build_graphs(data.get("relations", []))
        self._report_cycles()

        logger.success(f"Knowledge graph loaded ({len(self.all_concepts)} concept(s))")

    def _build_graphs(self, relations: list[dict]) -> None:
        node_attrs = [(c, {"domain": self.concept_domain[c]}) for c in self.all_concepts]

        for rel_obj in relations:
            details = rel_obj.get("details", {})
            rel_name = details.get("verbose", "unknown")
            self.relation_details[rel_name] = details

            graph = nx.DiGraph() if details.get("directed", True) else nx.Graph()
            graph.add_nodes_from(node_attrs)
            graph.add_edges_from(
                (src, tgt)
                for src, targets in rel_obj.get("relations_data", {}).items()
                for tgt in targets
            )
            self.graphs[rel_name] = graph

    def _report_cycles(self) -> None:
        for rel_name, graph in self.graphs.items():
            if not self.relation_details[rel_name].get("acyclic", False):
                continue
            if not graph.is_directed():
                logger.warning(
                    f"'{rel_name}' is marked as 'acyclic' but not as 'directed' - skipping cycle validation."
                )
                continue
            if not nx.is_directed_acyclic_graph(graph):
                logger.error(f"Cycle detected in '{rel_name}': {nx.find_cycle(graph)}")

    def __getitem__(self, relation: str) -> nx.Graph:
        return self.graphs[relation]

    def details(self, relation: str) -> dict:
        return self.relation_details[relation]

    def has_relation(self, relation: str) -> bool:
        return relation in self.graphs

    def neighbors(self, concept: str, relation: str, direction: str = "out") -> list[str]:
        graph = self.graphs[relation]

        if not graph.is_directed():
            return sorted(graph.neighbors(concept))
        if direction == "out":
            return sorted(graph.successors(concept))
        if direction == "in":
            return sorted(graph.predecessors(concept))

        raise ValueError(f"direction must be 'out' or 'in', not {direction!r}")
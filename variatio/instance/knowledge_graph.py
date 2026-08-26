import json

import networkx as nx
from loguru import logger


class KnowledgeGraph:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self.concepts_by_domains: dict[str, list[str]] = data["concepts_by_domains"]
        self.domains: list[str] = list(self.concepts_by_domains)
        self.domain_index: dict[str, int] = {d: i for i, d in enumerate(self.domains)}
        self.concept_domain: dict[str, str] = {
            c: d for d, cs in self.concepts_by_domains.items() for c in cs
        }
        self.all_concepts: list[str] = [c for cs in self.concepts_by_domains.values() for c in cs]

        # A build writes `false` here and an empty list below, so an unreviewed graph loads
        # with EVERY concept taggable — including the ones that label everything and
        # therefore identify nothing. Refusing to tag would leave a fresh build with nothing
        # to work with, so the loader states the flag and the caller decides what to do
        # about it; `stages.initialize` says it out loud.
        self.taggability_reviewed: bool = bool(data.get("taggability_reviewed", False))
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
                    f"«{rel_name}» es acíclica pero no dirigida; no se comprueban ciclos"
                )
                continue
            if not nx.is_directed_acyclic_graph(graph):
                logger.error(f"Ciclo en «{rel_name}»: {nx.find_cycle(graph)}")

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

    # `A → B` means "B is a prerequisite of A", so OUTGOING edges point to the
    # prerequisites. In networkx that is `descendants`, not `ancestors`: the domain's
    # names and the library's names are crossed, and confusing them swaps "assumed
    # known" with "not yet taught" with nothing failing.
    def _closure(self, concepts: list[str], relation: str, forward: bool) -> list[str]:
        if not self.has_relation(relation):
            return []
        graph = self.graphs[relation]
        if not graph.is_directed():
            logger.warning(f"«{relation}» no es dirigida; no se puede calcular su cierre")
            return []
        reach = nx.descendants if forward else nx.ancestors
        found: set[str] = set()
        for concept in concepts:
            if concept in graph:
                found |= reach(graph, concept)
        return sorted(found - set(concepts))

    def prerequisite_closure(self, concepts: list[str], relation: str) -> list[str]:
        return self._closure(concepts, relation, forward=True)

    def dependent_closure(self, concepts: list[str], relation: str) -> list[str]:
        return self._closure(concepts, relation, forward=False)

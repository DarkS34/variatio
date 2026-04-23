import json
from loguru import logger

import networkx as nx

DEPTH_LEVELS: dict[int, str] = {
    1: "Fácil",      # profundidad 0-1: conceptos sin prerequisitos o con uno
    2: "Moderado",   # profundidad 2-3: requiere conocimientos previos básicos
    3: "Difícil",    # profundidad 4-5: combina varios conceptos encadenados
    4: "Avanzado",   # profundidad 6+: recursividad, algoritmos, casos especiales complejos
}


class KnowledgeGraph:
    def __init__(self, raw_kg_path: str):
        
        with open(raw_kg_path, encoding="utf-8") as f:
            data = json.load(f)

        self._rel = data["relation_types"]
        self.concepts: dict[str, list[str]] = data["concepts"]
        self.relations: list = data["relations"]
        self.all_concepts: list[str] = [c for cs in self.concepts.values() for c in cs]
        self.concept_domain: dict[str, str] = {
            c: d for d, cs in self.concepts.items() for c in cs
        }
        self._graph = self._build_graph()

    def _build_graph(self) -> nx.DiGraph:
        G = nx.DiGraph()
        for domain, cs in self.concepts.items():
            for c in cs:
                G.add_node(c, domain=domain)
        for origin, destination, rel_type in self.relations:
            G.add_edge(origin, destination, type=rel_type)
        
        logger.info("Knowledge graph built successfully")
        return G

    def _subgraph(self, types: list[str]) -> nx.DiGraph:
        return nx.DiGraph(
            (u, v, d) for u, v, d in self._graph.edges(data=True) if d["type"] in types
        )

    def learning_frontier(self, mastered: set[str]) -> list[str]:
        G_req = self._subgraph([self._rel["prerequisite"]])
        return sorted(
            node
            for node in G_req.nodes
            if node not in mastered
            and all(p in mastered for p in G_req.successors(node))
        )

    def natural_combinations(self, concept: str) -> list[str]:
        G = self._subgraph([self._rel["combines_with"]])
        return sorted(set(G.successors(concept)) | set(G.predecessors(concept)))

    def special_cases(self, concept: str) -> list[str]:
        G = self._subgraph([self._rel["special_case"]])
        return [n for n, _ in G.in_edges(concept)]

    def concept_depth(self, concept: str) -> int:
        G_req = self._subgraph([self._rel["prerequisite"]])
        if concept not in G_req:
            return 1

        memo: dict[str, int] = {}

        def _depth(node: str) -> int:
            if node in memo:
                return memo[node]
            succs = list(G_req.successors(node))
            memo[node] = 0 if not succs else 1 + max(_depth(s) for s in succs)
            return memo[node]

        d = _depth(concept)
        if d <= 1:
            return 1
        if d <= 3:
            return 2
        if d <= 5:
            return 3
        return 4
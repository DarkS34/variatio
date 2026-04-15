import json
from pathlib import Path
from loguru import logger


import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import networkx as nx


class KnowledgeGraph:
    def __init__(self, raw_kg_path: Path = Path(__file__).parent / "data" / "kg_es.json"):
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

    def visualize(self, figsize: tuple[int, int] = (22, 16)) -> None:
        DOMAIN_COLORS = [
            "#4E79A7",
            "#E15759",
            "#76B7B2",
            "#F28E2B",
            "#59A14F",
            "#EDC948",
            "#B07AA1",
            "#FF9DA7",
            "#9C755F",
            "#BAB0AC",
        ]
        EDGE_STYLES = {
            self._rel["prerequisite"]: {
                "style": "solid",
                "color": "#888888",
                "alpha": 0.5,
            },
            self._rel["combines_with"]: {
                "style": "dashed",
                "color": "#2ca02c",
                "alpha": 0.7,
            },
            self._rel["special_case"]: {
                "style": "dotted",
                "color": "#d62728",
                "alpha": 0.7,
            },
        }

        domain_color = {
            d: DOMAIN_COLORS[i % len(DOMAIN_COLORS)]
            for i, d in enumerate(self.concepts)
        }
        node_colors = [domain_color[self.concept_domain[n]] for n in self._graph.nodes]
        node_sizes = [300 + 80 * self._graph.degree(n) for n in self._graph.nodes]

        pos = nx.kamada_kawai_layout(self._graph)

        fig, ax = plt.subplots(figsize=figsize)
        ax.set_facecolor("#FAFAFA")
        fig.patch.set_facecolor("#FAFAFA")

        for rel_type, style in EDGE_STYLES.items():
            edges = [
                (u, v)
                for u, v, d in self._graph.edges(data=True)
                if d["type"] == rel_type
            ]
            if edges:
                nx.draw_networkx_edges(
                    self._graph,
                    pos,
                    edgelist=edges,
                    ax=ax,
                    style=style["style"],
                    edge_color=style["color"],
                    alpha=style["alpha"],
                    arrows=True,
                    arrowsize=15,
                    connectionstyle="arc3,rad=0.08",
                    min_source_margin=12,
                    min_target_margin=12,
                )

        nx.draw_networkx_nodes(
            self._graph,
            pos,
            ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            edgecolors="#333333",
            linewidths=0.8,
            alpha=0.9,
        )
        nx.draw_networkx_labels(
            self._graph,
            pos,
            ax=ax,
            font_size=7,
            font_weight="bold",
            font_color="#222222",
        )

        domain_patches = [
            mpatches.Patch(color=domain_color[d], label=d) for d in self.concepts
        ]
        edge_patches = [
            mpatches.Patch(color=s["color"], label=f"{t} ({s['style']})")
            for t, s in EDGE_STYLES.items()
        ]
        ax.legend(
            handles=domain_patches + edge_patches,
            loc="upper left",
            fontsize=9,
            framealpha=0.9,
            title="Legend",
            title_fontsize=10,
        )

        ax.set_title("Knowledge Graph", fontsize=16, fontweight="bold", pad=20)
        ax.axis("off")
        plt.tight_layout()
        plt.show()

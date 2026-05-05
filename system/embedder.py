import hashlib
import json
import os

from . import config
import numpy as np
import ollama
from loguru import logger

from system.knowledge_graph import KnowledgeGraph


class Embedder:
    def __init__(self, knowledge_graph: KnowledgeGraph, embedding_model: str):
        self.knowledge_graph = knowledge_graph
        self.embedding_model = embedding_model
        self.similarity_threshold = 0.6
        self.concept_name_index: dict[str, np.ndarray] = {}
        self.content_bank_index: dict[str, np.ndarray] = {}

        self.index: dict[str, np.ndarray] = {}

    # FIGERPRINTS ---------------------------------------------------------------------------------

    def _concept_fingerprint(self) -> str:
        concepts_serialized = json.dumps(
            sorted(self.knowledge_graph.all_concepts), ensure_ascii=False
        )
        return hashlib.md5(f"{self.embedding_model}::{concepts_serialized}".encode()).hexdigest()

    def _content_bank_fingerprint(self) -> str:
        statements = sorted((ex_id, ex["statement"]) for ex_id, ex in self.content_bank.items())
        statements_serialized = json.dumps(statements, ensure_ascii=False)
        return hashlib.md5(f"{self.embedding_model}::{statements_serialized}".encode()).hexdigest()

    # CONCEPT CACHE VALIDATION --------------------------------------------------------------------

    def _is_concept_cache_valid(self) -> bool:
        if not os.path.exists(config.PARTIAL_EMBEDDINGS_FILE):
            return False
        try:
            data = np.load(config.PARTIAL_EMBEDDINGS_FILE, allow_pickle=True)
            return str(data["fingerprint"]) == self._concept_fingerprint()
        except Exception:
            return False

    def _load_concept_cache(self) -> None:
        data = np.load(config.PARTIAL_EMBEDDINGS_FILE, allow_pickle=True)
        self.concept_name_index = dict(zip(data["keys"], data["vectors"]))

    def _save_concept_cache(self) -> None:
        config.PARTIAL_EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            config.PARTIAL_EMBEDDINGS_FILE,
            keys=list(self.concept_name_index.keys()),
            vectors=np.array(list(self.concept_name_index.values())),
            fingerprint=self._concept_fingerprint(),
        )

    # CONTENT BANK CACHE VALIDATION --------------------------------------------------------------------

    def _is_content_bank_cache_valid(self) -> bool:
        if not os.path.exists(config.FINAL_EMBEDDINGS_FILE):
            return False
        try:
            data = np.load(config.FINAL_EMBEDDINGS_FILE, allow_pickle=True)
            return str(data["fingerprint"]) == self._content_bank_fingerprint()
        except Exception:
            return False

    def _load_content_bank_cache(self) -> None:
        data = np.load(config.FINAL_EMBEDDINGS_FILE, allow_pickle=True)
        self.content_bank_index = dict(zip(data["keys"], data["vectors"]))

    def _save_content_bank_cache(self) -> None:
        config.FINAL_EMBEDDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            config.FINAL_EMBEDDINGS_FILE,
            keys=list(self.content_bank_index.keys()),
            vectors=np.array(list(self.content_bank_index.values())),
            fingerprint=self._content_bank_fingerprint(),
        )

    # BUILD INDICES -------------------------------------------------------------------------------

    def init_index_with_concepts(self) -> None:
        def _describe(concept: str) -> str:
            kg = self.knowledge_graph
            domain = kg.concept_domain[concept]

            lines = [f'Concepto: "{concept}".', f'Dominio: "{domain}"']

            for verb, graph in kg.graphs.items():
                if kg.details(verb).get("use_in_embedding", True):
                    if graph.is_directed():
                        forward = sorted(graph.predecessors(concept))
                        backward = sorted(graph.successors(concept))

                        if forward:
                            lines.append(f'Este concepto {verb}: {", ".join(forward)}.')
                        for s in backward:
                            lines.append(f"{s} {verb} este concepto.")
                    else:
                        nbrs = sorted(graph.neighbors(concept))
                        if nbrs:
                            lines.append(f'Este concepto {verb}: {", ".join(nbrs)}.')

            return "\n".join(lines)

        for concept in self.knowledge_graph.all_concepts:
            self.concept_name_index[concept] = self._embed(_describe(concept))

    def enrich_index_with_content(self, annotated_bank: dict) -> None:
        self.content_bank = annotated_bank
        self.content_bank_index = {}
        logger.info(f"Embedding {len(annotated_bank)} content bank examples...")

        for content_id, content in annotated_bank.items():
            self.content_bank_index[content_id] = self._embed(content["statement"])

        for concept in self.knowledge_graph.all_concepts:
            name_vec = self.concept_name_index[concept]

            example_vecs = [
                self.content_bank_index[ex_id]
                for ex_id, ex in self.content_bank.items()
                if concept in ex.get("concepts", []) and ex_id in self.content_bank_index
            ]

            all_vecs = [name_vec] + example_vecs
            self.index[concept] = self._l2_normalize(np.mean(all_vecs, axis=0))

        logger.info(f"Enriched concept embeddings with {len(annotated_bank)} exercises")

    # TECHNICAL STUFF -----------------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        resp = ollama.embeddings(model=self.embedding_model, prompt=text)["embedding"]
        return self._l2_normalize(np.array(resp))

    def _l2_normalize(self, vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return float(np.dot(vec_a, vec_b))

    def top_k_concepts(self, text: str, k: int) -> list[tuple[str, float]]:
        vec = self._embed(text)
        scores = sorted(
            ((c, self.cosine_similarity(vec, v)) for c, v in self.index.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        return scores[:k]

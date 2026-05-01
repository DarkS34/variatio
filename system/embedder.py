import hashlib
import json
import os
from pathlib import Path

import numpy as np
from langchain_ollama import OllamaEmbeddings
from loguru import logger

from system.knowledge_graph import KnowledgeGraph

PARTIAL_CONCEPT_CACHE =  Path(__file__).parent / "cache" / "partial_concept_embeddings.cache.npz"
TOTAL_CONTENT_BANK_CACHE = Path(__file__).parent / "cache" / "total_content_bank_embeddings.cache.npz"

class Embedder:
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedding_model: OllamaEmbeddings,
        similarity_threshold: float = 0.6,
    ):
        self.knowledge_graph = knowledge_graph
        self.embedding_model = embedding_model
        self.similarity_threshold = similarity_threshold     # TODO Calculate sim threshhold dinamically

        self.concept_name_index: dict[str, np.ndarray] = {}

        self.content_bank_index: dict[str, np.ndarray] = {}

        self.index: dict[str, np.ndarray] = {}

        self.exercise_bank: dict | None = None  

        
        if self._is_concept_cache_valid():
            self._load_concept_cache()
            logger.info(f"Concept name index loaded from '{self._concept_cache_path}'")
        else:
            logger.info(f"Building concept name embeddings ({len(self.knowledge_graph.all_concepts)} concepts)...")
            self._build_concepts_index()
            self._save_concept_cache()
            logger.info(f"Concept name index saved to '{self._concept_cache_path}'.")

        self.index = dict(self.concept_name_index)

    # FIGERPRINTS ---------------------------------------------------------------------------------
    
    def _concept_fingerprint(self) -> str:
        concepts_serialized = json.dumps(sorted(self.all_concepts), ensure_ascii=False)
        return hashlib.md5(f"{self.embedding_model}::{concepts_serialized}".encode()).hexdigest()

    def _content_bank_fingerprint(self) -> str:
        statements = sorted(
            (ex_id, ex["statement"]) for ex_id, ex in self.exercise_bank.items()
        )
        statements_serialized = json.dumps(statements, ensure_ascii=False)
        return hashlib.md5(f"{self.embedding_model}::{statements_serialized}".encode()).hexdigest()

    # CONCEPT CACHE VALIDATION --------------------------------------------------------------------

    def _is_concept_cache_valid(self) -> bool:
        if not os.path.exists(self._concept_cache_path):
            return False
        try:
            data = np.load(self._concept_cache_path, allow_pickle=True)
            return str(data["fingerprint"]) == self._concept_fingerprint()
        except Exception:
            return False

    def _load_concept_cache(self) -> None:
        data = np.load(self._concept_cache_path, allow_pickle=True)
        self.concept_name_index = dict(zip(data["keys"], data["vectors"]))

    def _save_concept_cache(self) -> None:
        self._concept_cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self._concept_cache_path,
            keys=list(self.concept_name_index.keys()),
            vectors=np.array(list(self.concept_name_index.values())),
            fingerprint=self._concept_fingerprint(),
        )
    
    # CONCEPT CACHE VALIDATION --------------------------------------------------------------------

    def _is_content_bank_cache_valid(self) -> bool:
        if not os.path.exists(self._content_bank_cache_path):
            return False
        try:
            data = np.load(self._content_bank_cache_path, allow_pickle=True)
            return str(data["fingerprint"]) == self._content_bank_fingerprint()
        except Exception:
            return False

    def _load_content_bank_cache(self) -> None:
        data = np.load(self._content_bank_cache_path, allow_pickle=True)
        self.content_bank_index = dict(zip(data["keys"], data["vectors"]))

    def _save_content_bank_cache(self) -> None:
        self._content_bank_cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self._content_bank_cache_path,
            keys=list(self.content_bank_index.keys()),
            vectors=np.array(list(self.content_bank_index.values())),
            fingerprint=self._content_bank_fingerprint(),
        )
    
    # BUILD INDICES -------------------------------------------------------------------------------

    def _build_concepts_index(self) -> None:
        def _describe(concept: str) -> str:
            kg = self.knowledge_graph
            domain = kg.concept_domain[concept]
            theme = kg.main_theme

            lines = [
                f'Concepto: "{concept}".',
                f'Dominio: "{domain}", dentro del temario de "{theme}".',
            ]

            for verb, graph in kg.graphs.items():
                if graph.is_directed():
                    forward = sorted(graph.predecessors(concept))
                    backward = sorted(graph.successors(concept))
                    
                    if forward:
                        lines.append(f'Este concepto {verb}: {", ".join(forward)}.')
                    for s in backward:
                        lines.append(f'{s} {verb} este concepto.')
                else:
                    nbrs = sorted(graph.neighbors(concept))
                    if nbrs:
                        lines.append(f'Este concepto {verb}: {", ".join(nbrs)}.')

            return "\n".join(lines)

        for concept in self.knowledge_graph.all_concepts:
            self.concept_name_index[concept] = self._embed(_describe(concept))

    def _build_content_bank_index(self) -> None:
        for exercise_id, exercise in self.exercise_bank.items():
            self.content_bank_index[exercise_id] = self._embed(exercise["statement"])

    def _build_centroid_index(self) -> None:
        for concept in self.all_concepts:
            name_vec = self.concept_name_index[concept]
           
            example_vecs = [
                self.content_bank_index[ex_id]
                for ex_id, ex in self.exercise_bank.items()
                if concept in ex.get("concepts", []) and ex_id in self.content_bank_index
            ]

            all_vecs = [name_vec] + example_vecs
            self.index[concept] = self._l2_normalize(np.mean(all_vecs, axis=0))
    
    # TECHNICAL STUFF -----------------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        resp = self.embedding_model.embed_query(text)
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


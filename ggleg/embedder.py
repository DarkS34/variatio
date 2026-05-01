import hashlib
import json
import os
from pathlib import Path

from loguru import logger
import numpy as np
import ollama


class Embedder:
    def __init__(
        self,
        all_concepts: list[str],
        embedding_model: str,
        concept_cache_path: Path = Path(__file__).parent / "data" / "concept_embeddings.cache.npz",
        exercise_cache_path: Path = Path(__file__).parent / "data" / "exercise_embeddings.cache.npz",
        similarity_threshold: float = 0.6,
    ):
        self.all_concepts = all_concepts
        self.embedding_model = embedding_model
        self._concept_cache_path = concept_cache_path
        self._exercise_cache_path = exercise_cache_path
        self.similarity_threshold = similarity_threshold


        self.concept_name_index: dict[str, np.ndarray] = {}

        self.exercise_index: dict[str, np.ndarray] = {}

        self.index: dict[str, np.ndarray] = {}

        self.exercise_bank: dict | None = None  

        # === Fase 1: nombre-embeddings de conceptos ===
        if self._is_concept_cache_valid():
            self._load_concept_cache()
            logger.info(f"Concept name cache loaded from '{self._concept_cache_path}'")
        else:
            logger.info(f"Building concept name embeddings ({len(all_concepts)} concepts)...")
            self._build_concept_name_index()
            self._save_concept_cache()
            logger.info(f"Concept name index saved to '{self._concept_cache_path}'.")

        self.index = dict(self.concept_name_index)


    def enrich_with_exercises(self, exercise_bank: dict) -> None:
        """Fase 2: embebe enunciados de ejercicio y reconstruye centroides de concepto.
        Reutiliza los nombre-embeddings ya almacenados — no recalcula nada que ya esté cacheado.
        """
        self.exercise_bank = exercise_bank

        if self._is_exercise_cache_valid():
            self._load_exercise_cache()
            logger.info(f"Exercise cache loaded from '{self._exercise_cache_path}'")
        else:
            logger.info(f"Building exercise embeddings ({len(exercise_bank)} exercises)...")
            self._build_exercise_index()
            self._save_exercise_cache()
            logger.info(f"Exercise index saved to '{self._exercise_cache_path}'.")

        self._build_centroid_index()
        logger.success("Concept centroids enriched with tagged exercises.")

    def _concept_fingerprint(self) -> str:
        # Solo depende del modelo + lista de conceptos (orden-independiente)
        concepts_serialized = json.dumps(sorted(self.all_concepts), ensure_ascii=False)
        return hashlib.md5(f"{self.embedding_model}::{concepts_serialized}".encode()).hexdigest()

    def _exercise_fingerprint(self) -> str:
        # Solo depende del modelo + statements (cambios en otros campos del banco no invalidan)
        statements = sorted(
            (ex_id, ex["statement"]) for ex_id, ex in self.exercise_bank.items()
        )
        statements_serialized = json.dumps(statements, ensure_ascii=False)
        return hashlib.md5(f"{self.embedding_model}::{statements_serialized}".encode()).hexdigest()

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

    def _is_exercise_cache_valid(self) -> bool:
        if not os.path.exists(self._exercise_cache_path):
            return False
        try:
            data = np.load(self._exercise_cache_path, allow_pickle=True)
            return str(data["fingerprint"]) == self._exercise_fingerprint()
        except Exception:
            return False

    def _load_exercise_cache(self) -> None:
        data = np.load(self._exercise_cache_path, allow_pickle=True)
        self.exercise_index = dict(zip(data["keys"], data["vectors"]))

    def _save_exercise_cache(self) -> None:
        self._exercise_cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self._exercise_cache_path,
            keys=list(self.exercise_index.keys()),
            vectors=np.array(list(self.exercise_index.values())),
            fingerprint=self._exercise_fingerprint(),
        )

    def _build_concept_name_index(self) -> None:
        for concept in self.all_concepts:
            self.concept_name_index[concept] = self._embed(concept)

    def _build_exercise_index(self) -> None:
        for exercise_id, exercise in self.exercise_bank.items():
            self.exercise_index[exercise_id] = self._embed(exercise["statement"])

    def _build_centroid_index(self) -> None:
        for concept in self.all_concepts:
            name_vec = self.concept_name_index[concept]
            example_vecs = [
                self.exercise_index[ex_id]
                for ex_id, ex in self.exercise_bank.items()
                if concept in ex.get("concepts", []) and ex_id in self.exercise_index
            ]

            all_vecs = [name_vec] + example_vecs
            self.index[concept] = self._l2_normalize(np.mean(all_vecs, axis=0))

    def _embed(self, text: str) -> np.ndarray:
        resp = ollama.embed(model=self.embedding_model, input=text)
        return self._l2_normalize(np.array(resp.embeddings[0]))

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

    def label_concepts_with_scores(self, text: str) -> list[tuple[str, float]]:
        return [
            (c, s) for c, s in self.top_k_concepts(text, len(self.index))
            if s >= self.similarity_threshold
        ]

    def label_concepts(self, text: str) -> list[str]:
        return [c for c, _ in self.label_concepts_with_scores(text)]

    def most_similar_concept(self, text: str) -> tuple[str, float]:
        return self.top_k_concepts(text, 1)[0]

    def find_similar_exercises(self, text: str, n: int = 3) -> list[tuple[str, float]]:
        vec = self._embed(text)
        scores = sorted(
            ((ex_id, self.cosine_similarity(vec, v)) for ex_id, v in self.exercise_index.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        return scores[:n]

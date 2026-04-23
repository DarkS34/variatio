import hashlib
import json
import os

from loguru import logger
import numpy as np
import ollama
from pathlib import Path

from .knowledge_graph import KnowledgeGraph

MIN_EXAMPLES_FOR_CENTROID = 2


class Embedder:
    def __init__(
        self,
        all_concepts: KnowledgeGraph,
        exercise_bank: dict,
        embedding_model: str = "embeddinggemma",
        generation_model: str = "",
        cache_path: Path = Path(__file__).parent / "data" / "concept_embeddings.cache.npz",
        exercise_cache_path: Path = Path(__file__).parent / "data" / "exercise_embeddings.cache.npz",
        similarity_threshold: float = 0.6,
    ):
        self.all_concepts = all_concepts
        self.exercise_bank = exercise_bank
        self.embedding_model = embedding_model
        self.generation_model = generation_model
        self.cache_path = cache_path
        self.exercise_cache_path = exercise_cache_path
        self.similarity_threshold = similarity_threshold
        self.index: dict[str, np.ndarray] = {}
        self.exercise_index: dict[str, np.ndarray] = {}

        if self._is_cache_valid():
            self._load_cache()
            logger.info(f"Concept cache loaded from '{self.cache_path}'")
        else:
            logger.info("Building concept embedding index ...")
            self._build_index()
            self._save_cache()
            logger.info(f"Concept index built and saved at '{self.cache_path}'.")

        if self._is_exercise_cache_valid():
            self._load_exercise_cache()
            logger.info(f"Exercise cache loaded from '{self.exercise_cache_path}'")
        else:
            logger.info("Building exercise embedding index ...")
            self._build_exercise_index()
            self._save_exercise_cache()
            logger.info(f"Exercise index built and saved at '{self.exercise_cache_path}'.")


    def _compute_cache_fingerprint(self) -> str:
        bank_serialized = json.dumps(self.exercise_bank, sort_keys=True, ensure_ascii=False)
        bank_hash = hashlib.md5(bank_serialized.encode()).hexdigest()
        return hashlib.md5(f"{self.embedding_model}::{bank_hash}".encode()).hexdigest()


    def _is_cache_valid(self) -> bool:
        if not os.path.exists(self.cache_path):
            return False
        try:
            data = np.load(self.cache_path, allow_pickle=True)
            return str(data["fingerprint"]) == self._compute_cache_fingerprint()
        except Exception:
            return False


    def _load_cache(self) -> None:
        data = np.load(self.cache_path, allow_pickle=True)
        self.index = dict(zip(data["keys"], data["vectors"]))


    def _save_cache(self) -> None:
        np.savez(self.cache_path,
                 keys=list(self.index.keys()),
                 vectors=np.array(list(self.index.values())),
                 fingerprint=self._compute_cache_fingerprint()
                 )


    def _is_exercise_cache_valid(self) -> bool:
        if not os.path.exists(self.exercise_cache_path):
            return False
        try:
            data = np.load(self.exercise_cache_path, allow_pickle=True)
            return str(data["fingerprint"]) == self._compute_cache_fingerprint()
        except Exception:
            return False


    def _load_exercise_cache(self) -> None:
        data = np.load(self.exercise_cache_path, allow_pickle=True)
        self.exercise_index = dict(zip(data["keys"], data["vectors"]))


    def _save_exercise_cache(self) -> None:
        np.savez(self.exercise_cache_path,
                 keys=list(self.exercise_index.keys()),
                 vectors=np.array(list(self.exercise_index.values())),
                 fingerprint=self._compute_cache_fingerprint()
                 )


    def _build_index(self) -> None:
        for concept in self.all_concepts:
            examples = [
                ex["statement"]
                for ex in self.exercise_bank.values()
                if concept in ex.get("concepts", [])
            ]

            name_vec = self._embed(concept)
            if len(examples) >= MIN_EXAMPLES_FOR_CENTROID:
                example_vecs = [self._embed(s) for s in examples]
                all_vecs = [name_vec] + example_vecs
            elif len(examples) == 1:
                real_vec = self._embed(examples[0])
                all_vecs = [name_vec, real_vec]
            else:
                all_vecs = [name_vec]

            self.index[concept] = self._l2_normalize(np.mean(all_vecs, axis=0))


    def _build_exercise_index(self) -> None:
        for exercise_id, exercise in self.exercise_bank.items():
            self.exercise_index[exercise_id] = self._embed(exercise["statement"])


    def _embed(self, text: str) -> np.ndarray:
        resp = ollama.embed(model=self.embedding_model, input=text)
        return self._l2_normalize(np.array(resp.embeddings[0]))

    def _generate_synthetic(self, concept: str):
        pass

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
        vec = self._embed(text)
        scores = sorted(((c, self.cosine_similarity(vec, v))
                         for c, v in self.index.items()),
                        key=lambda x: x[1],
                        reverse=True
                        )
        return [(c, s) for c, s in scores if s >= self.similarity_threshold]


    def label_concepts(self, text: str) -> list[str]:
        return [c for c, _ in self.label_concepts_with_scores(text)]


    def most_similar_concept(self, text: str) -> tuple[str, float]:
        vec = self._embed(text)
        best_concept = max(self.index, key=lambda c: self.cosine_similarity(vec, self.index[c]))
        return best_concept, self.cosine_similarity(vec, self.index[best_concept])


    def find_similar_exercises(self, text: str, n: int = 3) -> list[tuple[str, float]]:
        vec = self._embed(text)
        scores = sorted(
            ((ex_id, self.cosine_similarity(vec, v)) for ex_id, v in self.exercise_index.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        return scores[:n]

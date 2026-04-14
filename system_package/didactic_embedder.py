import hashlib
import json
import os

import numpy as np
import ollama

from .knowledge_graph import KnowledgeGraph

_kg = KnowledgeGraph()
ALL_CONCEPTS: list[str] = _kg.all_concepts

MIN_EXAMPLES_FOR_CENTROID = 2


class DidacticEmbedder:
    def __init__(
        self,
        exercise_bank: dict,
        embedding_model: str = "embeddinggemma",
        generation_model: str = "",
        cache_path: str = "concept_embeddings.cache.npz",
        similarity_threshold: float = 0.5,
    ):
        self.exercise_bank = exercise_bank
        self.embedding_model = embedding_model
        self.generation_model = generation_model
        self.cache_path = cache_path
        self.similarity_threshold = similarity_threshold
        self.index: dict[str, np.ndarray] = {}

        if self._is_cache_valid():
            self._load_cache()
            print(f"[DidacticEmbedder] Cache loaded from '{self.cache_path}'.")
        else:
            print("[DidacticEmbedder] Building embedding index ...")
            self._build_index()
            self._save_cache()
            print(f"[DidacticEmbedder] Index built and saved at '{self.cache_path}'.")

    def _compute_cache_fingerprint(self) -> str:
        bank_serialized = json.dumps(
            self.exercise_bank, sort_keys=True, ensure_ascii=False)
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

    def _build_index(self) -> None:
        for concept in ALL_CONCEPTS:
            examples = [
                ex["statement"]
                for ex in self.exercise_bank.values()
                if concept in ex.get("concepts", [])
            ]
            if len(examples) >= MIN_EXAMPLES_FOR_CENTROID:
                centroid = self._l2_normalize(np.mean([self._embed(s) for s in examples], axis=0))
            elif len(examples) == 1:
                real_vec = self._embed(examples[0])
                synth_vec = self._embed(self._generate_synthetic(concept))
                centroid = self._l2_normalize(np.mean([real_vec, synth_vec], axis=0))
            else:
                centroid = self._embed(self._generate_synthetic(concept))
            self.index[concept] = centroid

    def _embed(self, text: str) -> np.ndarray:
        resp = ollama.embed(model=self.embedding_model, input=text)
        return self._l2_normalize(np.array(resp.embeddings[0]))

    def _l2_normalize(self, vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return float(np.dot(vec_a, vec_b))

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

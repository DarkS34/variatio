import hashlib
import json

from . import config
import numpy as np
import ollama
from loguru import logger

from system.knowledge_graph import KnowledgeGraph


class Embedder:
    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedding_model: str,
        primary_field: str,
    ):
        self.knowledge_graph = knowledge_graph
        self.embedding_model = embedding_model
        self.primary_field = primary_field

        self.similarity_threshold = config.EMBEDDER_SIMILARITY_THRESHOLD

        self.concepts_index: dict[str, np.ndarray] = {}
        self.content_bank_index: dict[str, np.ndarray] = {}

        if self._is_concept_cache_valid():
            self._load_concept_cache()
            logger.info(f"Loaded concepts index from cache ({len(self.concepts_index)} concepts)")
        else:
            logger.info("Building concepts index...")
            self.init_index_with_concepts()
            self._save_concept_cache()
            logger.info(f"Saved concepts index cache ({len(self.concepts_index)} concepts)")

        self.index: dict[str, np.ndarray] = dict(self.concepts_index)

        if config.CONTENT_BANK_EMBEDDINGS_PATH.exists():
            self._load_content_bank_cache()
            self._merge_into_index()
            logger.info(f"Loaded content bank cache and merged index ({len(self.content_bank_index)} items)")
        else:
            logger.warning("Content bank embeddings cache not found - call enrich_index_with_content to generate it.")

    # FIGERPRINTS ---------------------------------------------------------------------------------

    def _concept_fingerprint(self) -> str:
        concepts_serialized = json.dumps(
            sorted(self.knowledge_graph.all_concepts), ensure_ascii=False
        )
        return hashlib.md5(f"{self.embedding_model}::{concepts_serialized}".encode()).hexdigest()

    def _content_bank_fingerprint(self) -> str:
        entries = sorted(
            (ex_id, ex[self.primary_field], sorted(ex.get("concepts", [])))
            for ex_id, ex in self.content_bank.items()
        )
        entries_serialized = json.dumps(entries, ensure_ascii=False)
        return hashlib.md5(f"{self.embedding_model}::{entries_serialized}".encode()).hexdigest()

    # CONCEPT CACHE VALIDATION --------------------------------------------------------------------

    def _is_concept_cache_valid(self) -> bool:
        if not config.CONCEPTS_EMBEDDINGS_PATH.exists():
            return False
        try:
            data = np.load(config.CONCEPTS_EMBEDDINGS_PATH, allow_pickle=True)
            return str(data["fingerprint"]) == self._concept_fingerprint()
        except Exception:
            return False

    def _load_concept_cache(self) -> None:
        data = np.load(config.CONCEPTS_EMBEDDINGS_PATH, allow_pickle=True)
        self.concepts_index = dict(zip(data["keys"], data["vectors"]))

    def _save_concept_cache(self) -> None:
        config.CONCEPTS_EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            config.CONCEPTS_EMBEDDINGS_PATH,
            keys=list(self.concepts_index.keys()),
            vectors=np.array(list(self.concepts_index.values())),
            fingerprint=self._concept_fingerprint(),
        )

    # CONTENT BANK CACHE VALIDATION ---------------------------------------------------------------

    def _is_content_bank_cache_valid(self) -> bool:
        if not config.CONTENT_BANK_EMBEDDINGS_PATH.exists():
            return False
        try:
            data = np.load(config.CONTENT_BANK_EMBEDDINGS_PATH, allow_pickle=True)
            return str(data["fingerprint"]) == self._content_bank_fingerprint()
        except Exception:
            return False

    def _load_content_bank_cache(self) -> None:
        data = np.load(config.CONTENT_BANK_EMBEDDINGS_PATH, allow_pickle=True)
        self.content_bank_index = dict(zip(data["keys"], data["vectors"]))
        self.content_bank = json.loads(str(data["assignments"]))
        self._cached_content_bank_fingerprint = str(data["fingerprint"])

    def _save_content_bank_cache(self) -> None:
        config.CONTENT_BANK_EMBEDDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        assignments = {
            ex_id: {"concepts": sorted(ex.get("concepts", []))}
            for ex_id, ex in self.content_bank.items()
        }
        np.savez(
            config.CONTENT_BANK_EMBEDDINGS_PATH,
            keys=list(self.content_bank_index.keys()),
            vectors=np.array(list(self.content_bank_index.values())),
            assignments=json.dumps(assignments, ensure_ascii=False),
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
            self.concepts_index[concept] = self._embed(_describe(concept))

    def enrich_index_with_content(self, annotated_bank: dict) -> None:
        self.content_bank = annotated_bank
        new_fingerprint = self._content_bank_fingerprint()

        if (
            getattr(self, "_cached_content_bank_fingerprint", None) == new_fingerprint
            and self.content_bank_index
        ):
            logger.info("Content bank index already up to date; skipping re-embedding.")
            return

        self.content_bank_index = {}
        logger.info(f"Embedding {len(annotated_bank)} content bank examples...")

        for content_id, content in annotated_bank.items():
            self.content_bank_index[content_id] = self._embed(content[self.primary_field])

        self._save_content_bank_cache()
        self._cached_content_bank_fingerprint = new_fingerprint
        self._merge_into_index()
        logger.info(
            f"Saved content bank cache and merged index ({len(self.content_bank_index)} items)"
        )

    def _merge_into_index(self) -> None:
        for concept in self.knowledge_graph.all_concepts:
            name_vec = self.concepts_index[concept]

            example_vecs = [
                self.content_bank_index[ex_id]
                for ex_id, ex in self.content_bank.items()
                if concept in ex.get("concepts", []) and ex_id in self.content_bank_index
            ]

            all_vecs = [name_vec] + example_vecs
            self.index[concept] = self._l2_normalize(np.mean(all_vecs, axis=0))

    # TECHNICAL STUFF -----------------------------------------------------------------------------

    def _embed(self, text: str) -> np.ndarray:
        resp = ollama.embeddings(model=self.embedding_model, prompt=text)["embedding"]
        return self._l2_normalize(np.array(resp))

    def _l2_normalize(self, vec: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        return float(np.dot(vec_a, vec_b))

    # RETRIEVE  -----------------------------------------------------------------------------

    def top_k_concepts(self, text: str, k: int) -> list[tuple[str, float]]:
        vec = self._embed(text)
        scores = sorted(
            ((c, self.cosine_similarity(vec, v)) for c, v in self.index.items()),
            key=lambda x: x[1],
            reverse=True,
        )
        if not scores:
            return []

        candidates = [(c, s) for c, s in scores[:k] if s >= self.similarity_threshold]
        if not candidates:
            return []

        gap_threshold = max(0.03, candidates[0][1] * 0.05)
        result = [candidates[0]]
        for prev, curr in zip(candidates, candidates[1:]):
            if prev[1] - curr[1] > gap_threshold:
                break
            result.append(curr)
        return result

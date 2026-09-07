"""The index the pipeline retrieves against: concept centroids plus the exemplars' kNN leg."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
from loguru import logger

from ... import config
from ...core import inference, progress
from ...instance.knowledge_graph import KnowledgeGraph
from . import cache
from .descriptions import ConceptDescriber
from .vectors import l2_normalize, prefix_for


class Embedder:
    """The concepts index, the exemplars bank index, and the score that fuses them."""

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedding_model: str,
        prompts,
        embed_text: Callable[[dict], str],
        embed_signature: str,
        context: dict,
        descriptions_path: str | Path,
        concept_sources_path: str | Path,
        concepts_cache_path: str | Path,
        exemplars_bank_cache_path: str | Path,
    ):
        """Write any missing concept description, then load or build both indices."""
        self.knowledge_graph = knowledge_graph
        self.embedding_model = embedding_model
        self.embed_text = embed_text
        self.embed_signature = embed_signature
        self.context = context

        self.descriptions_path = Path(descriptions_path)
        self.concept_sources_path = Path(concept_sources_path)
        self.concepts_cache_path = Path(concepts_cache_path)
        self.exemplars_bank_cache_path = Path(exemplars_bank_cache_path)

        self.similarity_threshold = config.EMBEDDER_SIMILARITY_THRESHOLD
        self.description_weight = config.EMBEDDER_DESCRIPTION_WEIGHT

        self.concepts_index: dict[str, np.ndarray] = {}
        self.exemplars_bank_index: dict[str, np.ndarray] = {}
        self.concept_descriptions: dict[str, str] = {}
        self.exemplars_bank: dict[str, dict] = {}
        self._cached_exemplars_bank_fingerprint: str | None = None
        self._cached_text_fingerprints: dict[str, str] = {}
        self._embed_cache: dict[str, np.ndarray] = {}

        self._concept_keys: list[str] = []
        self._concept_matrix: np.ndarray = np.zeros((0, 0))
        self._exemplar_keys: list[str] = []
        self._exemplar_matrix: np.ndarray = np.zeros((0, 0))
        self._exemplar_rows_by_concept: dict[str, list[int]] = {}

        self.describer = ConceptDescriber(
            knowledge_graph, context, prompts, self.descriptions_path, self.concept_sources_path
        )
        self.concept_descriptions = self.describer.ensure()
        self._ensure_concepts_index()

        self.merged_index: dict[str, np.ndarray] = dict(self.concepts_index)
        self._load_previous_bank_index()
        self._rebuild_matrices()

    # SETUP ---------------------------------------------------------------------------------------

    def _ensure_concepts_index(self) -> None:
        """Reuse the concepts cache when it is still valid, else embed and save it."""
        if cache.concept_cache_is_valid(self.concepts_cache_path, self._concept_fingerprint()):
            self.concepts_index = cache.load_concept_cache(self.concepts_cache_path)
            logger.info(
                f"Concepts index reused from the cache "
                f"({len(self.concepts_index)} concept(s))"
            )
            return
        logger.info("Building the concepts index")
        self.init_index_with_concepts()
        cache.save_concept_cache(
            self.concepts_cache_path, self.concepts_index, self._concept_fingerprint()
        )

    def _load_previous_bank_index(self) -> None:
        """Adopt the bank index the previous run left, as a warm start for this run.

        `enrich_index_with_content` re-embeds and re-merges it once the current bank is
        known, so tagging already benefits from what the last run learned.
        """
        if not self.exemplars_bank_cache_path.exists():
            return
        (
            self.exemplars_bank_index,
            self.exemplars_bank,
            self._cached_text_fingerprints,
            self._cached_exemplars_bank_fingerprint,
        ) = cache.load_bank_cache(self.exemplars_bank_cache_path)
        self._merge_into_index()

    # FINGERPRINTS --------------------------------------------------------------------------------

    def _concept_fingerprint(self) -> str:
        """The fingerprint of the concepts index as it currently stands."""
        return cache.concept_fingerprint(
            self._embedding_fingerprint(),
            self.knowledge_graph.taggable_concepts,
            self.concept_descriptions,
        )

    def _text_fingerprints(self, bank: dict) -> dict[str, str]:
        """Hash every item's indexed text once, for the whole bank.

        `embed_text` renders every indexed field, so the hash is computed here and threaded
        through the fingerprint, the reuse test and the cache file rather than four times.
        """
        return {ex_id: self._text_fingerprint(self.embed_text(ex)) for ex_id, ex in bank.items()}

    @staticmethod
    def _text_fingerprint(text: str) -> str:
        """The digest of one item's indexed text."""
        return cache.text_fingerprint(text)

    def _exemplars_bank_fingerprint(self, text_fingerprints: dict[str, str]) -> str:
        """The fingerprint of the bank index as it currently stands."""
        return cache.bank_fingerprint(
            self._embedding_fingerprint(), self.exemplars_bank, text_fingerprints
        )

    def _embedding_fingerprint(self) -> str:
        """The fingerprint of the embedding setup: model, indexed fields and prefixes."""
        return cache.embedding_fingerprint(
            self.embedding_model,
            self.embed_signature,
            config.EMBEDDING_QUERY_PREFIX,
            config.EMBEDDING_DOCUMENT_PREFIX,
        )

    # INDICES -------------------------------------------------------------------------------

    def init_index_with_concepts(self) -> None:
        """Embed every taggable concept's description into the concepts index."""
        concepts = self.knowledge_graph.taggable_concepts
        with progress.step(
            "index_concepts", "Indexing the concepts", total=len(concepts)
        ) as reporter:
            vectors = self._embed_many(
                [self.concept_descriptions[c] for c in concepts], "document", reporter
            )
        self.concepts_index = dict(zip(concepts, vectors))

    def enrich_index_with_content(self, annotated_bank: dict) -> None:
        """Adopt a bank: embed what changed, reuse the rest, re-merge the centroids."""
        cached_vectors = self.exemplars_bank_index
        cached_texts = self._cached_text_fingerprints

        self.exemplars_bank = annotated_bank
        text_fingerprints = self._text_fingerprints(annotated_bank)
        new_fingerprint = self._exemplars_bank_fingerprint(text_fingerprints)

        if self._cached_exemplars_bank_fingerprint == new_fingerprint and cached_vectors:
            logger.info("Bank index up to date; there is nothing to embed")
            return

        reusable = {
            ex_id: cached_vectors[ex_id]
            for ex_id in annotated_bank
            if ex_id in cached_vectors and cached_texts.get(ex_id) == text_fingerprints[ex_id]
        }
        pending = [ex_id for ex_id in annotated_bank if ex_id not in reusable]

        if pending:
            logger.info(
                f"Embedding {len(pending)} bank item(s) "
                f"({len(reusable)} reused from the cache)"
            )
            with progress.step(
                "embed_bank", "Indexing the exemplars bank", total=len(pending)
            ) as reporter:
                vectors = self._embed_many(
                    [self.embed_text(annotated_bank[ex_id]) for ex_id in pending],
                    "document",
                    reporter,
                )
            reusable.update(zip(pending, vectors))

        self.exemplars_bank_index = {ex_id: reusable[ex_id] for ex_id in annotated_bank}
        cache.save_bank_cache(
            self.exemplars_bank_cache_path,
            self.exemplars_bank_index,
            annotated_bank,
            text_fingerprints,
            new_fingerprint,
        )
        self._cached_text_fingerprints = text_fingerprints
        self._cached_exemplars_bank_fingerprint = new_fingerprint
        self._merge_into_index()
        self._rebuild_matrices()

    def _merge_into_index(self) -> None:
        """Fuse each concept's description with its exemplars into a weighted centroid.

        `α·description + (1-α)·centroid(exemplars)`, L2-normalised. The weighting is the
        point: a plain mean let the description drop to 1/(1+n) as exemplars accumulated,
        so a concept's anchor faded with its popularity and mis-tagged exemplars drifted
        the centroid with nothing to pull it back. No exemplars keeps the description.
        """
        alpha = self.description_weight
        for concept in self.knowledge_graph.taggable_concepts:
            description_vec = self.concepts_index[concept]

            example_vecs = [
                self.exemplars_bank_index[ex_id]
                for ex_id, ex in self.exemplars_bank.items()
                if concept in ex.get("concepts", []) and ex_id in self.exemplars_bank_index
            ]

            if not example_vecs:
                self.merged_index[concept] = description_vec
                continue

            examples_centroid = l2_normalize(np.mean(example_vecs, axis=0))
            self.merged_index[concept] = l2_normalize(
                alpha * description_vec + (1.0 - alpha) * examples_centroid
            )

    def _rebuild_matrices(self) -> None:
        """Stack both indices into matrices, so a score is one dot product per side.

        Only items carrying a `primary_concept` enter the exemplar matrix — that is what
        keeps the kNN leg from propagating an incidental tag.
        """
        self._concept_keys = list(self.merged_index.keys())
        self._concept_matrix = (
            np.stack([self.merged_index[c] for c in self._concept_keys])
            if self._concept_keys
            else np.zeros((0, 0))
        )

        self._exemplar_keys = [
            ex_id
            for ex_id in self.exemplars_bank_index
            if (self.exemplars_bank.get(ex_id) or {}).get("primary_concept")
        ]
        self._exemplar_matrix = (
            np.stack([self.exemplars_bank_index[ex_id] for ex_id in self._exemplar_keys])
            if self._exemplar_keys
            else np.zeros((0, 0))
        )
        self._exemplar_rows_by_concept = {}
        for row, ex_id in enumerate(self._exemplar_keys):
            concept = self.exemplars_bank[ex_id]["primary_concept"]
            self._exemplar_rows_by_concept.setdefault(concept, []).append(row)

    # VECTOR MATH -----------------------------------------------------------------------------

    def embed_document(self, text: str) -> np.ndarray:
        """Embed one text on the indexed side."""
        return self._embed(text, "document")

    def _embed(self, text: str, kind: str) -> np.ndarray:
        """Embed one text, memoised by PREFIXED text.

        The same statement embedded for tagging and for the bank index costs one call.
        """
        key = self._prefix(kind) + text
        cached = self._embed_cache.get(key)
        if cached is not None:
            return cached
        raw = inference.embed(model=self.embedding_model, text=key)
        vector = l2_normalize(np.array(raw, dtype=np.float32))
        self._embed_cache[key] = vector
        return vector

    def _embed_many(self, texts: list[str], kind: str, reporter=None) -> list[np.ndarray]:
        """Embed a list of texts in batches, memoising each and reporting progress."""
        keys = [self._prefix(kind) + t for t in texts]
        pending = self._pending_keys(keys)

        done = 0
        for start in range(0, len(pending), config.EMBEDDING_BATCH_SIZE):
            progress.checkpoint()
            batch = pending[start : start + config.EMBEDDING_BATCH_SIZE]
            vectors = inference.embed_batch(model=self.embedding_model, texts=batch)
            for key, vector in zip(batch, vectors):
                self._embed_cache[key] = l2_normalize(np.array(vector, dtype=np.float32))
            done += len(batch)
            if reporter is not None:
                reporter.tick(done)

        return [self._embed_cache[k] for k in keys]

    @staticmethod
    def _prefix(kind: str) -> str:
        """The task prefix for one side of retrieval."""
        return prefix_for(kind)

    def _pending_keys(self, keys: list[str]) -> list[str]:
        """Return the distinct keys not already memoised, in order."""
        return [k for k in dict.fromkeys(keys) if k not in self._embed_cache]

    # RETRIEVAL -----------------------------------------------------------------------------

    def prefetch_queries(self, texts: list[str]) -> None:
        """Embed a batch of statements on the query side, ahead of scoring them."""
        pending = self._pending_keys([self._prefix("query") + t for t in texts])
        if not pending:
            return
        logger.info(f"Embedding {len(pending)} statement(s) for retrieval")
        with progress.step(
            "embed_queries", "Embedding the statements", total=len(pending)
        ) as reporter:
            self._embed_many(texts, "query", reporter)

    def rank_exemplars(self, concepts: list[str], exemplar_ids: list[str]) -> list[str]:
        """Order exemplars by how well they match some concepts.

        Ranked against the concept DESCRIPTIONS and never the merged centroids: the
        centroid is built from these same exemplars, so ranking them by it would be
        circular.
        """
        vectors = [self.concepts_index[c] for c in concepts if c in self.concepts_index]
        if not vectors:
            return list(exemplar_ids)

        matrix = np.stack(vectors)
        scored = []
        for ex_id in exemplar_ids:
            vector = self.exemplars_bank_index.get(ex_id)
            scored.append((float((matrix @ vector).max()) if vector is not None else -1.0, ex_id))
        scored.sort(key=lambda pair: -pair[0])
        return [ex_id for _, ex_id in scored]

    def top_k_concepts(self, text: str, k: int) -> list[tuple[str, float]]:
        """Return the k best-scoring concepts for a statement, or nothing at all.

        `EMBEDDER_SIMILARITY_THRESHOLD` gates ONLY the top-1 score — it answers "is this
        item about anything in the KG at all?". Below it the item matches nothing in the
        graph and no candidate is returned.
        """
        scores = self._score_concepts(self._embed(text, "query"))
        if not scores:
            return []

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if ranked[0][1] < self.similarity_threshold:
            return []

        return ranked[:k]

    def _score_concepts(self, vec: np.ndarray) -> dict[str, float]:
        """Score every concept against a query vector, as a two-signal MAX.

        Concepts are multimodal — the same one is practised in dissimilar ways — so a
        centroid lands between the modes and the kNN leg recovers those. That leg is
        restricted to `primary_concept` on purpose: a max over every incidental tag would
        propagate one mis-tag to everything resembling it.
        """
        if not self._concept_keys:
            return {}

        centroid_scores = self._concept_matrix @ vec
        scores = {c: float(s) for c, s in zip(self._concept_keys, centroid_scores)}

        if not self._exemplar_keys:
            return scores

        exemplar_scores = self._exemplar_matrix @ vec
        for concept, rows in self._exemplar_rows_by_concept.items():
            if concept in scores:
                scores[concept] = max(scores[concept], float(exemplar_scores[rows].max()))
        return scores

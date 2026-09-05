"""A flat vector index over plain text pieces: what a competent engineer builds without a graph.

Deliberately NOT the pipeline's index. That one already contains the graph — concept
descriptions fused into weighted centroids, a kNN leg restricted to `primary_concept` —
so reusing it would measure the system against itself.

What this one knows is a text per key and nothing else: the pieces of the raw documents
`evaluation.raw_text` cut, keyed by document and position. No modality, no tag, no concept.

Same embedding model as the pipeline on purpose: the variable under test is the graph,
not the quality of the embedder.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from loguru import logger

from variatio import config
from variatio.core import inference, progress

CACHE_VERSION = 2


class FlatIndex:
    """Texts as one matrix of L2-normalised vectors, cached to one `.npz`.

    `cache_path` is required and never defaulted: the fingerprint deliberately does not
    name the workspace, so the PATH is the only thing separating two instances' indices.
    """

    def __init__(
        self,
        entries: dict[str, str],
        cache_path: str | Path,
        model: str | None = None,
        label: str = "Indexando los documentos para la propuesta comparativa",
        step_id: str = "eval_rag_index",
    ):
        """Hold the texts and where their index lives; nothing is embedded until `ensure`.

        `step_id` is the caller's for the same reason `label` is: two indices built one
        after the other under one id are two rows of one name in the run's timeline, and
        the client translates by id, so the slot has to be in the id to reach the screen.
        """
        self.entries = dict(entries)
        self.model = model or config.EMBEDDING_LLM
        self.cache_path = Path(cache_path)
        self.label = label
        self.step_id = step_id

        self.ids: list[str] = []
        self.matrix: np.ndarray = np.zeros((0, 0), dtype=np.float32)

    def ensure(self) -> None:
        """Load the index from cache or build it, once per process."""
        if self.ids or not self.entries:
            return
        if self._load_cache():
            logger.info(f"Índice RAG reutilizado de la caché ({len(self.ids)} fragmento(s))")
            return
        self._build()
        self._save_cache()
        logger.info(f"Índice RAG construido y guardado ({len(self.ids)} fragmento(s))")

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        """Plain cosine, top-k. No threshold, no relative band, no query prefix."""
        self.ensure()
        if not self.ids or k <= 0:
            return []
        vector = self._embed([query])[0]
        scores = self.matrix @ vector
        order = np.argsort(-scores)[:k]
        return [(self.ids[int(i)], float(scores[int(i)])) for i in order]

    # BUILD -----------------------------------------------------------------------------------

    def _build(self) -> None:
        """Embed every text and keep the matrix and the keys."""
        self.ids = list(self.entries)
        with progress.step(self.step_id, self.label, total=len(self.ids)) as reporter:
            vectors = self._embed([self.entries[key] for key in self.ids], reporter)
        self.matrix = np.stack(vectors) if vectors else np.zeros((0, 0), dtype=np.float32)

    def _embed(self, texts: list[str], reporter=None) -> list[np.ndarray]:
        """Embed in batches, normalised, checking for cancellation between them."""
        out: list[np.ndarray] = []
        for start in range(0, len(texts), config.EMBEDDING_BATCH_SIZE):
            progress.checkpoint()
            batch = texts[start : start + config.EMBEDDING_BATCH_SIZE]
            for raw in inference.embed_batch(model=self.model, texts=batch):
                out.append(_l2_normalize(np.array(raw, dtype=np.float32)))
            if reporter is not None:
                reporter.tick(len(out))
        return out

    # CACHE -----------------------------------------------------------------------------------

    def _fingerprint(self) -> str:
        """Hash the model and every text, which is what invalidates the cache."""
        digest = sorted(
            (key, hashlib.md5(text.encode("utf-8")).hexdigest())
            for key, text in self.entries.items()
        )
        payload = json.dumps(digest, ensure_ascii=False)
        return hashlib.md5(f"{CACHE_VERSION}::{self.model}::{payload}".encode()).hexdigest()

    def _load_cache(self) -> bool:
        """Read the `.npz` back, answering False for anything stale or unreadable."""
        if not self.cache_path.exists():
            return False
        try:
            data = np.load(self.cache_path, allow_pickle=False)
            if str(data["fingerprint"]) != self._fingerprint():
                return False
            self.ids = [str(key) for key in data["keys"]]
            self.matrix = np.array(data["vectors"], dtype=np.float32)
        except Exception:
            return False
        return bool(self.ids)

    def _save_cache(self) -> None:
        """Write the matrix, the keys and the fingerprint to the workspace's own `.npz`."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self.cache_path,
            keys=self.ids,
            vectors=self.matrix,
            fingerprint=self._fingerprint(),
        )


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    """Scale a vector to unit length, leaving a zero vector alone."""
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector

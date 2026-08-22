"""A flat vector index over the bank: what a competent engineer builds without a graph.

Deliberately NOT the pipeline's index. That one already contains the graph — concept
descriptions fused into weighted centroids, a kNN leg restricted to `primary_concept` —
so reusing it would measure the system against itself.

What this one is allowed to know: the statement of each item and which modality it is.
Both come from the exemplars profile, not from the knowledge graph. What it must not touch:
`concepts` and `primary_concept`, which sit in the very same JSON and are the tagger's
output, i.e. the graph's.

Same embedding model as the pipeline on purpose: the variable under test is the graph,
not the quality of the embedder.
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
from loguru import logger

from .. import config
from ..core import inference, progress

# `cache_path` is required, and that is the point: it used to fall back to the default
# workspace, so every instance that evaluated read and wrote ITS index under
# `workspaces/default/cache/`. Two workspaces with different banks produce different
# fingerprints, so each run found the other's file stale, rebuilt, and overwrote it — a
# workspace paying for the other's re-embedding, in a directory it may not even belong to.
# The fingerprint deliberately does not name the workspace; the PATH is what separates them.

CACHE_VERSION = 1


class FlatBankIndex:
    def __init__(
        self,
        bank: dict,
        primary_text: Callable[[dict], str],
        type_key_of: Callable[[dict], str | None],
        cache_path: str | Path,
        model: str | None = None,
    ):
        self.bank = bank
        self.primary_text = primary_text
        self.type_key_of = type_key_of
        self.model = model or config.EMBEDDING_LLM
        self.cache_path = Path(cache_path)

        self.ids: list[str] = []
        self.types: list[str] = []
        self.matrix: np.ndarray = np.zeros((0, 0), dtype=np.float32)

    def ensure(self) -> None:
        if self.ids:
            return
        if self._load_cache():
            logger.info(f"Índice RAG reutilizado de la caché ({len(self.ids)} ítem(s))")
            return
        self._build()
        self._save_cache()
        logger.info(f"Índice RAG construido y guardado ({len(self.ids)} ítem(s))")

    def search(self, query: str, k: int, item_type: str | None = None) -> list[tuple[str, float]]:
        """Plain cosine, top-k. No threshold, no relative band, no query prefix."""
        self.ensure()
        if not self.ids:
            return []

        rows = [i for i, key in enumerate(self.types) if item_type is None or key == item_type]
        if not rows:
            return []

        vector = self._embed([query])[0]
        scores = self.matrix[rows] @ vector
        order = np.argsort(-scores)[:k]
        return [(self.ids[rows[int(i)]], float(scores[int(i)])) for i in order]

    # BUILD -----------------------------------------------------------------------------------

    def _texts(self) -> dict[str, str]:
        return {item_id: self.primary_text(item) for item_id, item in self.bank.items()}

    def _build(self) -> None:
        texts = self._texts()
        self.ids = list(texts)
        self.types = [self.type_key_of(self.bank[item_id]) or "" for item_id in self.ids]
        with progress.step(
            "eval_rag_index", "Indexando el banco para la propuesta comparativa", total=len(self.ids)
        ) as reporter:
            vectors = self._embed([texts[item_id] for item_id in self.ids], reporter)
        self.matrix = np.stack(vectors) if vectors else np.zeros((0, 0), dtype=np.float32)

    def _embed(self, texts: list[str], reporter=None) -> list[np.ndarray]:
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
        entries = sorted(
            (item_id, hashlib.md5(text.encode("utf-8")).hexdigest())
            for item_id, text in self._texts().items()
        )
        payload = json.dumps(entries, ensure_ascii=False)
        return hashlib.md5(f"{CACHE_VERSION}::{self.model}::{payload}".encode()).hexdigest()

    def _load_cache(self) -> bool:
        if not self.cache_path.exists():
            return False
        try:
            data = np.load(self.cache_path, allow_pickle=True)
            if str(data["fingerprint"]) != self._fingerprint():
                return False
            self.ids = [str(key) for key in data["keys"]]
            self.types = [str(key) for key in data["types"]]
            self.matrix = np.array(data["vectors"], dtype=np.float32)
        except Exception:
            return False
        return bool(self.ids)

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            self.cache_path,
            keys=self.ids,
            types=self.types,
            vectors=self.matrix,
            fingerprint=self._fingerprint(),
        )


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector

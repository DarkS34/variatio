"""Vector arithmetic and the batched embedding calls, shared by everything that embeds.

`embed_normalized` is one function and not three — the KG builder's merge candidates, the
describer's name shortlist and its collision check all want the same batching, the same L2
normalisation and the same "warn and carry on without the signal". The model is an argument.
"""

import numpy as np
from loguru import logger

from ... import config
from ...core import inference, progress


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    """Return the unit vector, or the vector itself when its norm is zero."""
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


def normalize_rows(vectors: list[list[float]]) -> np.ndarray:
    """Return a row-normalised float32 matrix.

    Vectors are cast to float32 at the point of embedding and stay float32 through the
    merge and the `.npz`: at 2560 dimensions that halves a tracked cache for no measurable
    loss. Do not "restore" float64.
    """
    matrix = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


def embed_normalized(texts: list[str], what: str, model: str | None = None):
    """Return a row-normalised matrix, or None when the engine could not answer.

    None is not an error: every caller uses these as an optional signal — a merge
    shortlist, a sibling shortlist, a collision check — and degrading to "no signal" is
    better than failing a build that can still produce a graph.
    """
    model = model or config.EMBEDDING_LLM
    try:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), config.EMBEDDING_BATCH_SIZE):
            progress.checkpoint()
            vectors.extend(
                inference.embed_batch(
                    model=model, texts=texts[start : start + config.EMBEDDING_BATCH_SIZE]
                )
            )
    except progress.Cancelled:
        raise
    except Exception as e:
        logger.warning(f"Could not embed {what} ({e}); carrying on without that signal")
        return None

    return normalize_rows(vectors)


def prefix_for(kind: str) -> str:
    """Return the task prefix for one side of retrieval.

    `EMBEDDING_DOCUMENT_PREFIX` is empty while the query one is not: that asymmetry is
    qwen3-embedding's prescribed usage, not an omission. It also splits the memo, so a
    statement is embedded once per side rather than once in total.
    """
    if kind == "query":
        return config.EMBEDDING_QUERY_PREFIX
    return config.EMBEDDING_DOCUMENT_PREFIX

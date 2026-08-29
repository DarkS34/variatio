"""Vector arithmetic and the batched embedding calls, shared by everything that embeds.

`embed_normalized` is one function and not three: the KG builder's merge-candidate pass
had its own copy, and so did the describer's name shortlist — same batching, same L2
normalisation, same "warn and carry on without the signal" on failure, differing only in
which model they ask. The model is an argument now.
"""

import numpy as np
from loguru import logger

from .. import config
from ..core import inference, progress


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


# Vectors are cast to float32 at the point of embedding and stay float32 through the merge
# and the `.npz`: at 2560 dimensions that halves a tracked cache for no measurable loss.
# Do not "restore" float64.
def normalize_rows(vectors: list[list[float]]) -> np.ndarray:
    matrix = np.array(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)


def embed_normalized(texts: list[str], what: str, model: str | None = None):
    """A row-normalised matrix, or None when the engine could not answer.

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
    """The task prefix for one side of retrieval.

    The asymmetry is qwen3-embedding's prescribed usage, not an omission: the query states
    the retrieval task, the indexed side stays raw. It also splits the memo, so a statement
    is embedded once per side rather than once in total.
    """
    if kind == "query":
        return config.EMBEDDING_QUERY_PREFIX
    return config.EMBEDDING_DOCUMENT_PREFIX

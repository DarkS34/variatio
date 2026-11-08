"""Retrieval: the two vector indices the bank and the graph are searched with.

    cache.py         the two `.npz` and the fingerprints that decide they are still valid
    index.py         `Embedder`: the concept centroids, the bank, and the two-signal score

The prose the concept index is built from is `knowledge_graph/descriptions.py`; the vector
arithmetic and the batched embedding calls are `inference/vectors.py`, shared with the builders
and the tutor.
"""

from . import cache, index
from .index import Embedder

__all__ = ["Embedder", "cache", "index"]

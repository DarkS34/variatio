"""Two indices and the prose one of them is built from.

    descriptions.py  the retrieval surface: LLM-written concept descriptions and their cache
    vectors.py       L2 normalisation, batched embedding, the query/document prefixes
    cache.py         the two `.npz` and the fingerprints that decide they are still valid
    index.py         `Embedder`: the concept centroids, the bank, and the two-signal score

The public names are unchanged, so `from .embedder import Embedder, ConceptDescriber,
load_descriptions, save_descriptions` resolves exactly as it did when this was one file.
"""

from . import cache, descriptions, index, vectors
from .descriptions import (
    ConceptDescriber,
    load_descriptions,
    load_sources,
    save_descriptions,
)
from .index import Embedder
from .vectors import embed_normalized, l2_normalize

__all__ = [
    "ConceptDescriber",
    "Embedder",
    "load_descriptions",
    "load_sources",
    "save_descriptions",
    "embed_normalized",
    "l2_normalize",
    "cache",
    "descriptions",
    "index",
    "vectors",
]

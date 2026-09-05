"""Two indices and the prose one of them is built from.

    descriptions.py  the retrieval surface: LLM-written concept descriptions and their cache
    vectors.py       L2 normalisation, batched embedding, the query/document prefixes
    cache.py         the two `.npz` and the fingerprints that decide they are still valid
    index.py         `Embedder`: the concept centroids, the bank, and the two-signal score

Every public name is re-exported here, so splitting the package cost no caller an import.
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
    "cache",
    "descriptions",
    "embed_normalized",
    "index",
    "l2_normalize",
    "load_descriptions",
    "load_sources",
    "save_descriptions",
    "vectors",
]

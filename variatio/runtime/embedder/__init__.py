"""Two indices, and a re-export of the prose one of them is built from.

    cache.py         the two `.npz` and the fingerprints that decide they are still valid
    index.py         `Embedder`: the concept centroids, the bank, and the two-signal score

The prose is `knowledge_graph/descriptions.py`: LLM-written concept descriptions and their cache.

Every public name is re-exported here, so splitting the package cost no caller an import.
The vector arithmetic and the batched embedding calls are `inference/vectors.py`, shared with
the builders and the tutor.
"""

from ...inference.vectors import embed_normalized, l2_normalize
from . import cache, index
from ...knowledge_graph import descriptions
from ...knowledge_graph.descriptions import (
    ConceptDescriber,
    load_descriptions,
    load_sources,
    save_descriptions,
)
from .index import Embedder

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
]

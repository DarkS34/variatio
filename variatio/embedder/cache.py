"""The two `.npz` caches and the fingerprints that decide whether they are still valid.

A fingerprint answers one question — "would re-embedding produce the same vectors?" — so
everything that changes the vectors has to be inside it, and nothing else may be. That is
why the concept cache is fingerprinted by `embed_signature` too: change which fields are
indexed and the merged centroids change, while the descriptions that built them do not.
"""

import hashlib
import json
from pathlib import Path

import numpy as np


def text_fingerprint(text: str) -> str:
    """Return the digest of one item's indexed text."""
    return hashlib.md5((text or "").encode()).hexdigest()


def embedding_fingerprint(model: str, embed_signature: str, query_prefix: str, document_prefix: str) -> str:
    """Return the fingerprint of the embedding setup itself.

    The signature is appended only when non-empty, so a profile indexing primary fields
    alone produces the exact string this used to and keeps its caches: a separator on its
    own would invalidate every vector for no change in the text they were built from.
    """
    base = f"{model}::{query_prefix}::{document_prefix}"
    return f"{base}::{embed_signature}" if embed_signature else base


def concept_fingerprint(
    embedding: str, taggable: list[str], descriptions: dict[str, str]
) -> str:
    """Return the fingerprint of the concepts index: the setup, the names and their prose."""
    payload = json.dumps(
        {
            "concepts": sorted(taggable),
            "descriptions": {
                c: descriptions[c] for c in sorted(taggable) if c in descriptions
            },
        },
        ensure_ascii=False,
    )
    return hashlib.md5(f"{embedding}::{payload}".encode()).hexdigest()


def bank_fingerprint(embedding: str, bank: dict, text_fingerprints: dict[str, str]) -> str:
    """Return the fingerprint of the bank index: the setup, each item's text and its tags."""
    entries = sorted(
        (
            ex_id,
            text_fingerprints[ex_id],
            sorted(ex.get("concepts", [])),
            ex.get("primary_concept") or "",
        )
        for ex_id, ex in bank.items()
    )
    serialized = json.dumps(entries, ensure_ascii=False)
    return hashlib.md5(f"{embedding}::{serialized}".encode()).hexdigest()


# CONCEPT INDEX ---------------------------------------------------------------------------


def concept_cache_is_valid(path: Path, fingerprint: str) -> bool:
    """Return whether the concepts cache on disk still matches this fingerprint.

    Any failure to read it counts as invalid: a corrupt cache costs one re-embedding, not
    a broken run.
    """
    if not path.exists():
        return False
    try:
        data = np.load(path, allow_pickle=False)
        return str(data["fingerprint"]) == fingerprint
    except Exception:
        return False


def load_concept_cache(path: Path) -> dict[str, np.ndarray]:
    """Read the concept vectors from their `.npz`."""
    data = np.load(path, allow_pickle=False)
    return dict(zip(data["keys"], data["vectors"]))


def save_concept_cache(path: Path, index: dict[str, np.ndarray], fingerprint: str) -> None:
    """Write the concept vectors and the fingerprint they were built under."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        keys=list(index.keys()),
        vectors=np.array(list(index.values())),
        fingerprint=fingerprint,
    )


# BANK INDEX ------------------------------------------------------------------------------
#
# The bank cache stores a per-item text hash alongside the vectors, so re-tagging the bank
# re-merges without re-embedding anything and an edited item re-embeds alone. It persists
# `primary_concept` too, or the kNN leg would be dead exactly during tagging.


def load_bank_cache(path: Path) -> tuple[dict[str, np.ndarray], dict[str, dict], dict[str, str], str]:
    """Read the bank vectors, their tags, their text hashes and the cache's fingerprint."""
    data = np.load(path, allow_pickle=False)
    index = dict(zip(data["keys"], data["vectors"]))
    assignments = json.loads(str(data["assignments"]))
    bank = {
        ex_id: {
            "concepts": entry.get("concepts", []),
            "primary_concept": entry.get("primary_concept"),
        }
        for ex_id, entry in assignments.items()
    }
    texts = {ex_id: entry.get("text", "") for ex_id, entry in assignments.items()}
    return index, bank, texts, str(data["fingerprint"])


def save_bank_cache(
    path: Path,
    index: dict[str, np.ndarray],
    bank: dict,
    text_fingerprints: dict[str, str],
    fingerprint: str,
) -> None:
    """Write the bank vectors beside the tags and text hashes that justify reusing them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    assignments = {
        ex_id: {
            "concepts": sorted(ex.get("concepts", [])),
            "primary_concept": ex.get("primary_concept"),
            "text": text_fingerprints[ex_id],
        }
        for ex_id, ex in bank.items()
    }
    np.savez(
        path,
        keys=list(index.keys()),
        vectors=np.array(list(index.values())),
        assignments=json.dumps(assignments, ensure_ascii=False),
        fingerprint=fingerprint,
    )

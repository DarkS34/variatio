from pathlib import Path

import numpy as np
import pytest

from variatio.embedder import cache

FINGERPRINT = "0123456789abcdef0123456789abcdef"


def _mark(marker: str, value: str) -> str:
    Path(marker).write_text("ejecutado", encoding="utf-8")
    return value


class _Payload:
    def __init__(self, marker: str, value: str):
        self.marker = marker
        self.value = value

    def __reduce__(self):
        return (_mark, (self.marker, self.value))


# `NpzFile` unpickles a member only when it is read, so the payload has to sit in the
# field the function under test actually reaches for.
def _hostile(path: Path, marker: Path, field: str, **fields) -> Path:
    payload = _Payload(str(marker), FINGERPRINT)
    if field == "fingerprint":
        fields[field] = np.array(payload, dtype=object)
    else:
        array = np.empty(1, dtype=object)
        array[0] = payload
        fields[field] = array
    np.savez(path, **fields)
    return path.with_suffix(".npz") if path.suffix != ".npz" else path


@pytest.fixture
def marker(tmp_path) -> Path:
    return tmp_path / "ejecutado.txt"


def test_a_hostile_fingerprint_never_validates_a_concept_cache(tmp_path, marker):
    path = _hostile(
        tmp_path / "concepts_embeddings",
        marker,
        "fingerprint",
        keys=["Variable"],
        vectors=np.zeros((1, 4), dtype=np.float32),
    )

    assert cache.concept_cache_is_valid(path, FINGERPRINT) is False
    assert not marker.exists()


def test_a_hostile_concept_cache_is_refused_instead_of_executed(tmp_path, marker):
    path = _hostile(
        tmp_path / "concepts_embeddings",
        marker,
        "keys",
        vectors=np.zeros((1, 4), dtype=np.float32),
        fingerprint=FINGERPRINT,
    )

    with pytest.raises(ValueError):
        cache.load_concept_cache(path)
    assert not marker.exists()


def test_a_hostile_bank_cache_is_refused_instead_of_executed(tmp_path, marker):
    path = _hostile(
        tmp_path / "exemplars_bank_embeddings",
        marker,
        "keys",
        vectors=np.zeros((1, 4), dtype=np.float32),
        assignments="{}",
        fingerprint=FINGERPRINT,
    )

    with pytest.raises(ValueError):
        cache.load_bank_cache(path)
    assert not marker.exists()


# The refusal has to leave the legitimate round trip alone: what this installation writes
# is `<U…` and `float32`, never an object array.
def test_a_real_concept_cache_still_round_trips(tmp_path):
    path = tmp_path / "concepts_embeddings.npz"
    index = {"Variable": np.zeros(4, dtype=np.float32), "Función": np.ones(4, dtype=np.float32)}
    cache.save_concept_cache(path, index, FINGERPRINT)

    assert cache.concept_cache_is_valid(path, FINGERPRINT) is True
    assert cache.concept_cache_is_valid(path, "otra") is False
    assert sorted(cache.load_concept_cache(path)) == ["Función", "Variable"]


def test_a_real_bank_cache_still_round_trips(tmp_path):
    path = tmp_path / "exemplars_bank_embeddings.npz"
    bank = {"C001": {"concepts": ["Variable"], "primary_concept": "Variable"}}
    cache.save_bank_cache(
        path, {"C001": np.zeros(4, dtype=np.float32)}, bank, {"C001": "hash"}, FINGERPRINT
    )

    index, stored, texts, fingerprint = cache.load_bank_cache(path)
    assert list(index) == ["C001"]
    assert stored["C001"]["primary_concept"] == "Variable"
    assert texts == {"C001": "hash"}
    assert fingerprint == FINGERPRINT

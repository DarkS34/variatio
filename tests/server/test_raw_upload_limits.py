import io
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import auth, raw_data
from server.auth.deps import Access
from server.routers.raw import router as raw_router
from variatio.core.workspace import Workspace


class _Upload:
    def __init__(self, name: str, data: bytes):
        self.filename = name
        self.file = io.BytesIO(data)


@pytest.fixture
def corpus(tmp_path) -> Workspace:
    ws = Workspace(tmp_path / "ws", slug="ws")
    raw_data.directory(ws, "corpus").mkdir(parents=True, exist_ok=True)
    return ws


# The per-file cap was the only one there was, so N × 512 MB was a legitimate request from
# anybody with the EDIT role.
def test_too_many_files_in_one_request_are_refused(corpus):
    uploads = [_Upload(f"a{i}.pdf", b"x") for i in range(raw_data.MAX_FILES + 1)]

    with pytest.raises(raw_data.RawLimitError) as exc:
        raw_data.save(corpus, "corpus", uploads)

    assert str(raw_data.MAX_FILES) in str(exc.value)
    assert not list(raw_data.directory(corpus, "corpus").iterdir())


def test_the_request_total_is_capped_beyond_the_per_file_one(corpus, monkeypatch):
    monkeypatch.setattr(raw_data, "MAX_REQUEST_BYTES", 12)

    result = raw_data.save(
        corpus, "corpus", [_Upload("a.pdf", b"y" * 8), _Upload("b.pdf", b"y" * 8)]
    )

    assert [entry["name"] for entry in result["added"]] == ["a.pdf"]
    assert "en total" in result["rejected"][0]["reason"]


# The one that makes the cap a cap: without counting the disk already there, the same
# request repeated fills the volume one call at a time.
def test_what_the_slot_already_holds_counts_against_the_cap(corpus, monkeypatch):
    monkeypatch.setattr(raw_data, "MAX_SLOT_BYTES", 25)
    (raw_data.directory(corpus, "corpus") / "ya.pdf").write_bytes(b"x" * 20)

    result = raw_data.save(corpus, "corpus", [_Upload("nuevo.pdf", b"y" * 9)])

    assert result["added"] == []
    assert "El origen supera" in result["rejected"][0]["reason"]
    assert [p.name for p in raw_data.directory(corpus, "corpus").iterdir()] == ["ya.pdf"]


def test_a_refused_file_leaves_nothing_half_written(corpus, monkeypatch):
    monkeypatch.setattr(raw_data, "MAX_BYTES", 4)

    result = raw_data.save(corpus, "corpus", [_Upload("grande.pdf", b"y" * 40)])

    assert "por archivo" in result["rejected"][0]["reason"]
    assert not list(raw_data.directory(corpus, "corpus").iterdir())


def test_what_fits_is_still_written(corpus):
    result = raw_data.save(
        corpus, "corpus", [_Upload("a.pdf", b"y" * 8), _Upload("b.md", b"z" * 3)]
    )

    assert [entry["bytes"] for entry in result["added"]] == [8, 3]
    assert result["rejected"] == []


# A cap is a 413 and not the 404 every other `RawError` means: «no existe» about a request
# that exists and was refused reads as a bug in the client.
def test_the_route_answers_413_and_names_the_limit(corpus):
    access = Access(
        user=SimpleNamespace(id=1, name="Ana"),
        workspace=SimpleNamespace(slug="ws", name="WS"),
        role="owner",
        ws=corpus,
    )
    app = FastAPI()
    app.include_router(raw_router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access

    response = TestClient(app).post(
        "/api/raw/corpus",
        files=[
            ("files", (f"a{i}.pdf", b"x", "application/pdf"))
            for i in range(raw_data.MAX_FILES + 1)
        ],
    )

    assert response.status_code == 413
    assert str(raw_data.MAX_FILES) in response.json()["detail"]


def test_the_listing_declares_the_three_limits(corpus):
    listing = raw_data.listing(corpus)

    assert listing["max_bytes"] == raw_data.MAX_BYTES
    assert listing["max_files"] == raw_data.MAX_FILES
    assert listing["max_slot_bytes"] == raw_data.MAX_SLOT_BYTES

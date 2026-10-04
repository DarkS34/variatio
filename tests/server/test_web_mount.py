"""The built client is served from `dist/`, and its build bookkeeping is not.

`pnpm build` writes `dist/.vite/chunks.json`, the chunk graph `pnpm check:lazy` reads. It
lists the client's source modules, which is no secret but nothing the app needs to publish
either, so the catch-all route answers `index.html` for any path through a dot-directory.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import app as app_module


def _client(tmp_path, monkeypatch) -> TestClient:
    dist = tmp_path / "dist"
    (dist / ".vite").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>index</title>", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (dist / ".vite" / "chunks.json").write_text('{"chunks": []}', encoding="utf-8")
    monkeypatch.setattr(app_module.installation, "WEB_DIST_DIR", dist)
    app = FastAPI()
    app_module._mount_web(app)
    return TestClient(app)


def test_a_file_of_the_bundle_is_served(tmp_path, monkeypatch):
    assert _client(tmp_path, monkeypatch).get("/favicon.svg").text == "<svg/>"


def test_the_build_bookkeeping_is_not_served(tmp_path, monkeypatch):
    answer = _client(tmp_path, monkeypatch).get("/.vite/chunks.json")

    assert answer.status_code == 200
    assert "index" in answer.text and "chunks" not in answer.text


def test_an_unknown_path_is_left_to_the_client_router(tmp_path, monkeypatch):
    assert "index" in _client(tmp_path, monkeypatch).get("/tutor").text

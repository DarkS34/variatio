import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import app as app_module
from server import settings, storage
from variatio.core.workspace import Workspace


def _spa_client(dist: Path, monkeypatch) -> TestClient:
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("SPA", encoding="utf-8")
    monkeypatch.setattr(settings, "WEB_DIST_DIR", dist)
    app = FastAPI()
    app_module._mount_web(app)
    return TestClient(app)


def test_the_spa_refuses_an_encoded_traversal(tmp_path, monkeypatch):
    (tmp_path / "secret.txt").write_text("PGPASSWORD=hunter2", encoding="utf-8")
    client = _spa_client(tmp_path / "dist", monkeypatch)

    assert "hunter2" not in client.get("/%2e%2e/secret.txt").text
    assert "hunter2" not in client.get("/%2e%2e%2fsecret.txt").text


def test_the_spa_still_serves_a_real_asset(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    client = _spa_client(dist, monkeypatch)
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")

    assert client.get("/favicon.svg").text == "<svg/>"


def test_a_snapshot_id_may_not_leave_its_history_directory(tmp_path):
    ws = Workspace(tmp_path / "ws", slug="ws")
    outside = tmp_path / "outside.json"
    outside.write_text('{"leaked": true}', encoding="utf-8")
    escape = os.path.relpath(outside, ws.history_dir / "knowledge_graph")

    with pytest.raises(FileNotFoundError):
        storage.restore(ws, "knowledge_graph", escape, tmp_path / "ws" / "target.json")

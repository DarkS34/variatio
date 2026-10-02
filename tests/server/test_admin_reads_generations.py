"""The installation administrator reads every exercise of a workspace, whoever wrote it.

The author's own routes stay private (`test_generations_are_private.py`); this is the one
other door, behind `require_admin`, and it only reads.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import auth, installation
from server import generations as store
from server.db import identity, repository
from server.routers import admin
from variatio.core.workspace import Workspace

ANA, BEA, GONE = 1, 2, 3


def _save(ws, user_id, text, second):
    store.save(
        ws,
        user_id,
        f"job{user_id}",
        1,
        {
            "commission": {"concepts": [], "think": False},
            "resolved": {"item_type": "ejercicio", "targets": ["Bucles"]},
            "output": {"item": {"enunciado": text}},
        },
        now=datetime(2026, 10, 1, 12, 0, second, tzinfo=timezone.utc),
    )


@pytest.fixture
def ws(tmp_path):
    ws = Workspace(tmp_path / "ws", slug="ws")
    _save(ws, ANA, "de Ana", 1)
    _save(ws, BEA, "de Bea", 3)
    _save(ws, GONE, "de alguien que ya no está", 2)
    _save(ws, None, "huérfano", 0)
    return ws


@pytest.fixture
def client(ws, monkeypatch):
    users = [
        SimpleNamespace(id=ANA, username="ana", name="Ana"),
        SimpleNamespace(id=BEA, username="bea", name="Bea"),
    ]
    monkeypatch.setattr(
        repository, "get_workspace", lambda db, slug: object() if slug == "ws" else None
    )
    monkeypatch.setattr(identity, "list_users", lambda db: users)
    monkeypatch.setattr(installation, "workspace_for", lambda slug: ws)
    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[auth.require_admin] = lambda: None
    app.dependency_overrides[auth.db] = lambda: None
    return TestClient(app)


def test_every_authors_exercises_are_listed_newest_first(client):
    body = client.get("/api/admin/workspaces/ws/generations").json()

    assert [row["item"]["enunciado"] for row in body["generations"]] == [
        "de Bea",
        "de alguien que ya no está",
        "de Ana",
        "huérfano",
    ]
    assert body["total"] == 4


def test_each_row_names_its_author_and_a_deleted_account_names_nobody(client):
    rows = client.get("/api/admin/workspaces/ws/generations").json()["generations"]
    authors = {row["item"]["enunciado"]: row["author"]["username"] for row in rows}

    assert authors == {
        "de Bea": "bea",
        "de Ana": "ana",
        "de alguien que ya no está": None,
        "huérfano": None,
    }


def test_the_author_filter_reads_one_directory(client):
    body = client.get(f"/api/admin/workspaces/ws/generations?author={ANA}").json()

    assert [row["item"]["enunciado"] for row in body["generations"]] == ["de Ana"]
    assert [a["username"] for a in body["authors"]] == ["ana", "bea"]


def test_an_unknown_workspace_is_a_404(client):
    assert client.get("/api/admin/workspaces/otra/generations").status_code == 404


def test_nothing_here_writes():
    writes = [
        route
        for route in admin.router.routes
        if "/generations" in route.path and route.methods - {"GET", "HEAD"}
    ]
    assert writes == []

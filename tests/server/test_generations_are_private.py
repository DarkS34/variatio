"""A generated exercise belongs to whoever asked for it, and to nobody else.

Two accounts may share a subject — that is what a membership is for — so the AUTHOR bounds
the exercises the way the membership bounds the workspace: each account's are a directory of
their own, and every route reads the asker's. There is no scope to flip: a filter somebody
can turn off is not privacy.

The four routes are pinned together because they are one rule seen from four sides: what is
listed, what can be read, what can be promoted and what can be deleted. The owner is not an
exception, and the answer for an exercise that is not yours is 404 and not 403 — a 403 would
confirm that the id names something.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import auth
from server import generations as store
from server.auth.deps import Access
from server.routers.generations import router as generations_router
from variatio.core.workspace import Workspace

MINE, THEIRS = 1, 2


@pytest.fixture
def ws(tmp_path):
    ws = Workspace(tmp_path / "ws", slug="ws")
    for user_id, text in ((MINE, "el mío"), (THEIRS, "el suyo")):
        store.save(
            ws,
            user_id,
            f"job{user_id}",
            1,
            {
                "commission": {"concepts": [], "think": "high"},
                "resolved": {"item_type": "ejercicio", "targets": ["Bucles"], "effort": "high"},
                "prompt": f"el prompt de {text}",
                "output": {"item": {"enunciado": text}, "thinking": "pensado"},
            },
        )
    return ws


def client(ws, *, role: str = "editor", user_id: int = MINE) -> TestClient:
    """A logged-in tab of workspace `ws`, as `user_id` with the given role."""
    access = Access(
        user=SimpleNamespace(id=user_id, name="Ana", username="ana"),
        workspace=SimpleNamespace(id=1, slug="ws", name="WS"),
        role=role,
        ws=ws,
    )
    app = FastAPI()
    app.include_router(generations_router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    return TestClient(app)


def id_of(ws, user_id: int) -> str:
    [record], _ = store.list_for(ws, user_id)
    return record["id"]


# THE LISTING -------------------------------------------------------------------------------------


def test_the_listing_answers_your_own_exercises_and_no_others(ws):
    body = client(ws).get("/api/generations").json()

    assert [row["item"]["enunciado"] for row in body["generations"]] == ["el mío"]
    assert body["total"] == 1


def test_a_row_carries_its_string_id_the_commission_and_what_ran(ws):
    [row] = client(ws).get("/api/generations").json()["generations"]

    assert row["id"] == id_of(ws, MINE)
    assert row["concepts"] == []
    assert row["targets"] == ["Bucles"]
    assert row["think"] == "high"
    assert row["effort"] == "high"
    assert row["author"]["id"] == MINE


def test_the_old_scope_parameter_no_longer_widens_it(ws):
    """An old bundle asking for the whole subject gets its own rows, not a 422 and not more."""
    body = client(ws).get("/api/generations?scope=workspace").json()

    assert [row["item"]["enunciado"] for row in body["generations"]] == ["el mío"]


def test_nothing_reports_how_much_anybody_else_has(ws):
    body = client(ws).get("/api/generations").json()

    assert "workspace_total" not in body
    assert "scope" not in body


def test_the_owner_is_not_an_exception(ws):
    body = client(ws, role="owner").get("/api/generations").json()

    assert body["total"] == 1


# ONE EXERCISE ------------------------------------------------------------------------------------


def test_reading_somebody_elses_exercise_is_a_404_and_not_a_403(ws):
    response = client(ws).get(f"/api/generations/{id_of(ws, THEIRS)}")

    assert response.status_code == 404


def test_your_own_exercise_still_reads_with_how_it_was_made(ws):
    body = client(ws).get(f"/api/generations/{id_of(ws, MINE)}").json()

    generation = body["generation"]
    assert generation["item"]["enunciado"] == "el mío"
    assert generation["thinking"] == "pensado"
    assert generation["provenance"]["prompt"] == "el prompt de el mío"
    assert generation["provenance"]["resolved"]["targets"] == ["Bucles"]


@pytest.mark.parametrize("bad", ["..", "..%2F2", "nada", "20261001T101530Z-ABC-1", "%2Fetc%2Fpasswd"])
def test_a_malformed_id_is_the_same_404(ws, bad):
    response = client(ws).get(f"/api/generations/{bad}")

    assert response.status_code == 404


def test_deleting_somebody_elses_exercise_is_refused_even_for_the_owner(ws):
    response = client(ws, role="owner").delete(f"/api/generations/{id_of(ws, THEIRS)}")

    assert response.status_code == 404
    assert store.count(ws) == 2


def test_deleting_your_own_removes_its_file(ws):
    mine = id_of(ws, MINE)
    response = client(ws).delete(f"/api/generations/{mine}")

    assert response.json() == {"deleted": mine}
    assert store.get(ws, MINE, mine) is None
    assert store.count(ws) == 1


def test_promoting_somebody_elses_exercise_is_refused(ws):
    response = client(ws).post(f"/api/generations/{id_of(ws, THEIRS)}/promote")

    assert response.status_code == 404


# THE "NO REPITAS ESTOS" BLOCK --------------------------------------------------------------------


def test_the_recent_reminder_reads_your_own_statements_only(ws):
    """It reaches a prompt, so a colleague's statement here is the same reading by another door."""
    assert store.recent_items(ws, MINE) == [{"enunciado": "el mío"}]
    assert store.recent_items(ws, THEIRS) == [{"enunciado": "el suyo"}]

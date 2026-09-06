"""A generated exercise belongs to whoever asked for it, and to nobody else.

Two accounts may share a subject — that is what a membership is for — so the AUTHOR bounds
the rows the way the membership bounds the workspace. There is no scope to flip: a filter
somebody can turn off is not privacy.

The four routes are pinned together because they are one rule seen from four sides: what is
listed, what can be read, what can be promoted and what can be deleted. The owner is not an
exception, and the answer for a row that is not yours is 404 and not 403 — a 403 would
confirm that the id names something.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import auth
from server.auth.deps import Access
from server.db import Base
from server.db import generations as db_generations
from server.db.models import Generation
from server.routers.generations import router as generations_router

MINE, THEIRS = 1, 2


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    for user_id, text in ((MINE, "el mío"), (THEIRS, "el suyo")):
        session.add(
            Generation(
                workspace_id=1,
                user_id=user_id,
                item_type="ejercicio",
                item={"enunciado": text},
                concepts=[],
                curriculum=[],
                fixed={},
            )
        )
    session.commit()
    yield session
    session.close()


def client(db, *, role: str = "editor", user_id: int = MINE) -> TestClient:
    """A logged-in tab of workspace 1, as `user_id` with the given role."""
    access = Access(
        user=SimpleNamespace(id=user_id, name="Ana"),
        workspace=SimpleNamespace(id=1, slug="ws", name="WS"),
        role=role,
        ws=SimpleNamespace(slug="ws"),
    )
    app = FastAPI()
    app.include_router(generations_router)
    app.dependency_overrides[auth.VIEW.dependency] = lambda: access
    app.dependency_overrides[auth.EDIT.dependency] = lambda: access
    app.dependency_overrides[auth.db] = lambda: db
    return TestClient(app)


def other_id(db) -> int:
    return db.query(Generation).filter(Generation.user_id == THEIRS).one().id


# THE LISTING -------------------------------------------------------------------------------------


def test_the_listing_answers_your_own_rows_and_no_others(db):
    body = client(db).get("/api/generations").json()

    assert [row["item"]["enunciado"] for row in body["generations"]] == ["el mío"]
    assert body["total"] == 1


def test_the_old_scope_parameter_no_longer_widens_it(db):
    """An old bundle asking for the whole subject gets its own rows, not a 422 and not more."""
    body = client(db).get("/api/generations?scope=workspace").json()

    assert [row["item"]["enunciado"] for row in body["generations"]] == ["el mío"]


def test_nothing_reports_how_much_anybody_else_has(db):
    body = client(db).get("/api/generations").json()

    assert "workspace_total" not in body
    assert "scope" not in body


def test_the_owner_is_not_an_exception(db):
    body = client(db, role="owner").get("/api/generations").json()

    assert body["total"] == 1


# ONE ROW -----------------------------------------------------------------------------------------


def test_reading_somebody_elses_row_is_a_404_and_not_a_403(db):
    response = client(db).get(f"/api/generations/{other_id(db)}")

    assert response.status_code == 404


def test_your_own_row_still_reads(db):
    mine = db.query(Generation).filter(Generation.user_id == MINE).one().id

    body = client(db).get(f"/api/generations/{mine}").json()

    assert body["generation"]["item"]["enunciado"] == "el mío"


def test_deleting_somebody_elses_row_is_refused_even_for_the_owner(db):
    response = client(db, role="owner").delete(f"/api/generations/{other_id(db)}")

    assert response.status_code == 404
    assert db.query(Generation).count() == 2


def test_promoting_somebody_elses_row_is_refused(db):
    response = client(db).post(f"/api/generations/{other_id(db)}/promote")

    assert response.status_code == 404


# THE "NO REPITAS ESTOS" BLOCK --------------------------------------------------------------------


def test_the_recent_reminder_reads_your_own_statements_only(db):
    """It reaches a prompt, so a colleague's statement here is the same reading by another door."""
    assert db_generations.recent_items(db, 1, author=MINE) == [{"enunciado": "el mío"}]
    assert db_generations.recent_items(db, 1, author=THEIRS) == [{"enunciado": "el suyo"}]

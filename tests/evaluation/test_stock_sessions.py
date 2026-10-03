"""A comparison stocked from the panel belongs to nobody until it is handed over.

The bug this pins: every `evaluate` job recorded its session under whoever launched it,
so a batch an administrator prepared FOR SOMEBODY ELSE landed in that administrator's own
"Mis sesiones", offered itself in "Evaluar", and could be answered there unassigned. Worse
than an inconvenience: `record_choice` rewrites the row without ever touching `user_id`,
so the judgement would have been filed under the name of whoever the row already said —
and an administrator answering a colleague's session filed it under the colleague.

Three items nobody has been handed have no evaluator. `assign` is what gives them one.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.auth.deps import Access
from server.db import identity, repository
from server.db.models import Base
from server.jobs.catalogue import Job
from evaluation.api import admin as evaluation_admin
from evaluation.api import jobs as evaluation_jobs
from evaluation.api import queries
from evaluation.api import router as evaluation_router
from evaluation.api import store as evaluation_store


def _arm(name):
    return {
        "arm": name,
        "status": "ok",
        "item": {"enunciado": f"el de {name}"},
        "raw_response": "{}",
        "prompt": "",
        "model": "modelo",
        "provider": "local",
        "exemplar_ids": [],
        "elapsed_ms": 1200,
        "error": None,
        "checks": None,
        "retried": 0,
    }


def _trace(session_id):
    return {
        "id": session_id,
        "created_at": 1787000000.0,
        "job_id": "job1",
        "set_id": session_id,
        "assigned_by": None,
        "concepts": ["Recursividad"],
        "item_type": "escritura_codigo",
        "fixed": {},
        "curriculum": [],
        "instructions": "",
        "seed": 42,
        "shuffle": ["naive", "rag", "system"],
        "think": False,
        "arms": {name: _arm(name) for name in ("naive", "rag", "system")},
        "triage": {},
        "choice": None,
        "choice_arm": None,
        "chosen_at": None,
        "opened_at": None,
        "declined_at": None,
        "evaluator_note": None,
        "rating": None,
    }


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    workspace = repository.ensure_workspace(session, "default", "cs0")
    admin = identity.create_user(
        session, username="admin", name="admin", password_hash="x", is_admin=True
    )
    nombre = identity.create_user(
        session, username="nombre", name="Nombre", password_hash="x"
    )
    identity.grant(session, workspace.id, nombre.id, "editor")
    session.flush()

    # What the panel leaves behind: three items in the workspace, evaluator still nobody.
    queries.upsert_evaluation(session, "stock0000001", workspace.id, None, _trace("stock0000001"))
    session.flush()

    yield session, {"workspace": workspace, "admin": admin, "nombre": nombre}
    session.close()


def _access(user, workspace):
    return Access(user=user, workspace=workspace, role="owner", ws=None, as_admin=user.is_admin)


def _stock(db):
    return queries.get_evaluation(db, "stock0000001")


# WHO THE JOB RECORDS THE SESSION UNDER ---------------------------------------------------


def test_a_comparison_stocked_from_the_panel_has_no_evaluator():
    job = Job(kind="evaluate", params={"stock": True}, workspace="default", user_id=7)
    assert evaluation_jobs.evaluator_of(job) is None


def test_a_comparison_somebody_commissioned_for_themselves_belongs_to_them():
    job = Job(kind="evaluate", params={}, workspace="default", user_id=7)
    assert evaluation_jobs.evaluator_of(job) == 7


def test_the_panel_marks_every_job_it_launches_as_stock():
    # The flag is what the handler reads, and the panel is its only writer: without it the
    # two routes are indistinguishable at the point the session is saved.
    assert evaluation_admin.STOCK_PARAM == "stock"


# WHOSE SCREEN IT SHOWS UP ON -------------------------------------------------------------


def test_it_is_not_in_the_listing_of_the_administrator_who_ordered_it(db):
    session, users = db
    _, total = queries.list_evaluations(
        session, workspace_id=users["workspace"].id, author=users["admin"].id
    )
    assert total == 0


def test_it_is_not_in_anybody_elses_listing_either(db):
    session, users = db
    _, total = queries.list_evaluations(
        session, workspace_id=users["workspace"].id, author=users["nombre"].id
    )
    assert total == 0


def test_it_is_not_in_anybody_queue(db):
    session, users = db
    assert queries.assigned_to(session, users["workspace"].id, users["admin"].id) == []


# WHO MAY ANSWER IT -----------------------------------------------------------------------


def test_the_administrator_who_ordered_it_cannot_answer_it(db):
    session, users = db
    with pytest.raises(HTTPException) as raised:
        evaluation_router._require(session, "stock0000001", _access(users["admin"], users["workspace"]))
    assert raised.value.status_code == 404


def test_an_administrator_cannot_answer_somebody_elses_session(db):
    session, users = db
    copy = evaluation_store.assign(
        session, _stock(session), users["nombre"].id, assigned_by=users["admin"].id
    )
    with pytest.raises(HTTPException) as raised:
        evaluation_router._require(session, copy.id, _access(users["admin"], users["workspace"]))
    assert raised.value.status_code == 404


def test_the_evaluator_it_was_assigned_to_may_answer_it(db):
    session, users = db
    copy = evaluation_store.assign(
        session, _stock(session), users["nombre"].id, assigned_by=users["admin"].id
    )
    row = evaluation_router._require(session, copy.id, _access(users["nombre"], users["workspace"]))
    assert row.id == copy.id


def test_an_administrator_may_answer_a_set_once_it_is_assigned_to_them(db):
    session, users = db
    # A stocked session cannot be answered by the administrator who stocked it unless it is
    # assigned to them from the panel: stocking is not holding.
    copy = evaluation_store.assign(
        session, _stock(session), users["admin"].id, assigned_by=users["admin"].id
    )
    row = evaluation_router._require(session, copy.id, _access(users["admin"], users["workspace"]))
    assert row.id == copy.id


# WHAT THE PANEL SAYS ABOUT IT ------------------------------------------------------------


def test_the_unassigned_source_is_not_listed_as_holding_itself(db):
    session, users = db
    listing = evaluation_admin.sets(workspace="default", db=session)
    assert [entry["set_id"] for entry in listing["sets"]] == ["stock0000001"]
    assert listing["sets"][0]["holders"] == []


def test_an_assignment_is_what_makes_a_holder(db):
    session, users = db
    evaluation_store.assign(
        session, _stock(session), users["nombre"].id, assigned_by=users["admin"].id
    )
    holders = evaluation_admin.sets(workspace="default", db=session)["sets"][0]["holders"]
    assert [entry["account"] for entry in holders] == ["nombre"]


def test_stock_is_reported_as_having_no_evaluator_and_not_as_a_deleted_account(db):
    session, users = db
    # `account_id` goes null for two different reasons — nobody was ever handed these
    # items, or the account that held them was deleted (`user_id` is SET NULL). "Cuenta
    # borrada" is only true of the second and reads as data loss when said of the first.
    groups = evaluation_store.by_account(evaluation_store.headers(session))
    assert [group["label"] for group in groups] == ["Sin evaluador"]

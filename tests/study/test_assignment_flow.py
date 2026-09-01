"""The two lookups the assignment screen is built on, and the bug that made it unusable.

Both are regressions with a shape worth naming: a list that LOOKS right on a populated
installation and is empty or wrong on the one that matters — the installation where nobody
has evaluated anything yet, which is every installation the first time.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.db import identity, repository
from server.db.models import Base


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    ejercicios = repository.ensure_workspace(session, "default", "cs0-ejercicios")
    examenes = repository.ensure_workspace(session, "examenes-cs1", "cs0-examenes")

    admin = identity.create_user(
        session, username="admin", name="admin", password_hash="x", is_admin=True
    )
    ana = identity.create_user(
        session, username="ana", name="Ana", password_hash="x", evaluator_profile="teacher"
    )
    nadie = identity.create_user(session, username="nadie", name="Nadie", password_hash="x")

    # The real shape of the installation this was found on: the administrator holds a
    # membership of ONE workspace and reaches the other through the bypass.
    identity.grant(session, examenes.id, admin.id, "owner")
    identity.grant(session, ejercicios.id, ana.id, "editor")

    session.flush()
    yield session, {"admin": admin, "ana": ana, "nadie": nadie}
    session.close()


def _accounts(session):
    from study.api.admin import assignable_accounts

    return {row["username"]: row for row in assignable_accounts(db=session)["accounts"]}


# WHICH WORKSPACES CAN BE PICKED ----------------------------------------------------------


def test_the_workspace_list_does_not_depend_on_anything_having_been_evaluated():
    # The bug: the filter's options were derived from the recorded sessions, so a fresh
    # installation offered none — and with no workspace to pick, nothing could ever be
    # handed out, so nothing was ever evaluated. The list is the installation's, full stop.
    from study.api.store import headers

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repository.ensure_workspace(session, "default", "cs0")
    session.flush()

    assert headers(session) == []
    assert [row.slug for row in repository.list_workspaces(session)] == ["default"]


def test_an_administrator_may_pick_every_workspace_not_only_their_memberships(db):
    session, _ = db
    # Otherwise the screen refuses an assignment that `assign_set` would accept, because
    # both read the same bypass — one of them just did not know it.
    assert sorted(w["slug"] for w in _accounts(session)["admin"]["workspaces"]) == [
        "default",
        "examenes-cs1",
    ]


def test_anybody_else_gets_exactly_the_workspaces_they_are_a_member_of(db):
    session, _ = db
    assert [w["slug"] for w in _accounts(session)["ana"]["workspaces"]] == ["default"]


def test_an_account_with_no_membership_is_listed_with_nowhere_to_be_assigned(db):
    session, _ = db
    # Listed rather than hidden: the screen has to be able to say «dale acceso primero»,
    # which it cannot do about somebody it never shows.
    assert _accounts(session)["nadie"]["workspaces"] == []


def test_a_deleted_workspace_is_never_offered(db):
    session, _ = db
    repository.get_workspace(session, "examenes-cs1")
    workspace = repository.get_workspace(session, "examenes-cs1")
    from server.db.identity import now

    workspace.deleted_at = now()
    session.flush()

    assert [w["slug"] for w in _accounts(session)["admin"]["workspaces"]] == ["default"]


# WHETHER ANYTHING CAN BE COMMISSIONED THERE ----------------------------------------------
#
# Since 2026-08-27 the commission form reads the workspace CHOSEN in step 2 rather than the
# one the tab is standing in, so each instance has to say whether it can take a commission
# at all — otherwise the only way to find out is a 409 after composing the whole thing.


def test_each_workspace_says_whether_a_commission_can_be_composed_in_it(db):
    session, _ = db
    from server import review

    # Neither of these instances has anything built, which is the state every workspace
    # starts in: not ready, and the three stages named. The names are ARTIFACT KEYS and
    # not the gate's Spanish sentence, because `web/src/lib/names.ts` is what says them in
    # the reader's own language.
    for entry in _accounts(session)["admin"]["workspaces"]:
        assert entry["ready"] is False
        assert entry["pending"] == list(review.ARTIFACTS)


def test_an_approved_chain_is_offered_with_nothing_pending(db, monkeypatch):
    session, _ = db
    # The rule is `gate_error`'s and only `gate_error`'s — the same one the endpoint that
    # generates enforces, so the screen can never offer what it would refuse.
    monkeypatch.setattr("study.api.admin.gate_error", lambda ws, kind: None)

    entry = _accounts(session)["ana"]["workspaces"][0]
    assert entry["ready"] is True
    assert entry["pending"] == []


def test_the_gate_is_read_once_per_workspace_and_not_once_per_account(db, monkeypatch):
    session, _ = db
    # It touches the filesystem, and this endpoint loops over every account of the
    # installation: three accounts over two instances used to mean three reads, of which
    # one was «default» measured twice.
    asked = []
    monkeypatch.setattr(
        "study.api.admin.gate_error",
        lambda ws, kind: asked.append(ws.slug) or "Para crear ejercicios hay que dar antes por buenos: X.",
    )

    _accounts(session)
    assert sorted(asked) == ["default", "examenes-cs1"]


# WHO CAN BE PICKED -----------------------------------------------------------------------


def test_the_profile_travels_so_the_screen_can_say_who_is_unclassified(db):
    session, _ = db
    accounts = _accounts(session)

    assert accounts["ana"]["evaluator_profile"] == "teacher"
    # Unset is what the panel draws in the attention colour so it gets corrected.
    assert accounts["admin"]["evaluator_profile"] is None


def test_a_disabled_account_is_not_offered(db):
    session, users = db
    users["ana"].disabled_at = identity.now()
    session.flush()

    assert "ana" not in _accounts(session)

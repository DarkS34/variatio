"""The account's profile: a teacher or a student, which the invitation sets and nobody chooses.

It decides one thing outside the subjects — whether the account creates them — so it cannot
be the answer of whoever registers: a profile somebody picks for themselves is a door they
open for themselves. The invitation says it, the form asks nothing, and a profile sent in
the request is ignored. Afterwards it only climbs: the administrator makes a student a
teacher and nobody lowers a teacher, and an administrator is a teacher. Inside a subject it
authorises nothing — the membership does.
"""

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from server.auth import passwords, rate_limit
from server.db import identity, repository
from server.db.models import Base
from server.routers import admin as admin_routes
from server.routers import workspaces as workspace_routes
from server.routers.admin import InviteBody, InviteEditBody, ProfileBody
from server.routers.auth import AcceptBody, accept_invite, preview_invite


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    # SQLite drops the offset Postgres keeps; every link below is far from expiring.
    monkeypatch.setattr(identity, "now", datetime.now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    yield session
    session.close()


@pytest.fixture
def admin(db):
    return identity.create_user(
        db, username="admin", name="admin", password_hash="x", is_admin=True,
        evaluator_profile="teacher",
    )


@pytest.fixture(autouse=True)
def forget_the_address():
    rate_limit.unlock("accept", "10.0.0.1")
    rate_limit.unlock("invite", "10.0.0.1")


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"host", b"localhost"), (b"origin", b"http://localhost")],
            "client": ("10.0.0.1", 1234),
            "scheme": "http",
            "server": ("localhost", 8000),
            "query_string": b"",
        }
    )


def _invite(db, admin, **terms) -> dict:
    return admin_routes.create_invite(InviteBody(**terms), _request(), admin=admin, db=db)


def _register(db, link: str, username: str, **sent):
    accept_invite(
        AcceptBody(
            token=link.split("token=")[1],
            username=username,
            name=username,
            password="una-contraseña-larga",
            **sent,
        ),
        _request(),
        Response(),
        session=db,
    )
    return identity.get_user(db, username)


# THE INVITATION SETS IT ------------------------------------------------------------------------


@pytest.mark.parametrize("profile", ["teacher", "student"])
def test_the_account_is_what_its_invitation_says(db, admin, profile):
    link = _invite(db, admin, profile=profile)["link"]

    assert _register(db, link, "ana").evaluator_profile == profile


def test_a_profile_sent_while_registering_is_ignored(db, admin):
    link = _invite(db, admin, profile="student")["link"]

    assert _register(db, link, "ana", evaluator_profile="teacher").evaluator_profile == "student"


def test_the_preview_says_the_profile_and_asks_nothing(db, admin):
    link = _invite(db, admin, profile="student")["link"]

    preview = preview_invite(link.split("token=")[1], session=db)

    assert preview["profile"] == "student"
    assert "asks_profile" not in preview


def test_an_invitation_without_a_profile_is_refused(db, admin):
    with pytest.raises(HTTPException) as refused:
        _invite(db, admin)

    assert refused.value.status_code == 422
    assert identity.unused_invites(db) == []


def test_an_invitation_with_an_unknown_profile_is_refused(db, admin):
    with pytest.raises(HTTPException) as refused:
        _invite(db, admin, profile="profesora")

    assert refused.value.status_code == 422
    assert "profesora" in refused.value.detail


def test_each_row_of_the_panel_shows_the_profile_and_it_can_be_changed_before_use(db, admin):
    minted = _invite(db, admin, profile="student")
    assert minted["invite"]["profile"] == "student"

    edited = admin_routes.edit_invite(
        minted["invite"]["id"], InviteEditBody(profile="teacher"), admin=admin, db=db
    )

    assert edited["invite"]["profile"] == "teacher"
    assert _register(db, minted["link"], "ana").evaluator_profile == "teacher"


def test_an_invitation_minted_without_saying_is_a_students():
    """The column's default, for whatever writes one without the argument: it fails closed."""
    assert Base.metadata.tables["invites"].c.profile.server_default.arg == "student"


# IT ONLY CLIMBS ---------------------------------------------------------------------------------


def _account(db, username: str, profile: str | None):
    return identity.create_user(
        db, username=username, name=username, password_hash="x", evaluator_profile=profile
    )


def _raise(db, user, profile):
    return admin_routes.set_profile(user.id, ProfileBody(evaluator_profile=profile), db=db)


def test_the_administrator_makes_a_student_a_teacher(db):
    alumna = _account(db, "alumna", "student")

    assert _raise(db, alumna, "teacher")["evaluator_profile"] == "teacher"
    assert alumna.evaluator_profile == "teacher"


@pytest.mark.parametrize("profile", ["student", None, "admin"])
def test_nobody_lowers_or_clears_a_profile(db, profile):
    docente = _account(db, "docente", "teacher")

    with pytest.raises(HTTPException) as refused:
        _raise(db, docente, profile)

    assert refused.value.status_code == 409
    assert refused.value.headers == {"X-Error-Code": admin_routes.PROFILE_ONLY_CLIMBS}
    assert docente.evaluator_profile == "teacher"


def test_raising_a_teacher_changes_nothing_and_is_no_error(db):
    docente = _account(db, "docente", "teacher")

    assert _raise(db, docente, "teacher")["evaluator_profile"] == "teacher"


def test_an_administrator_is_a_teacher(db, admin):
    alumna = _account(db, "alumna", "student")

    admin_routes.set_admin(alumna.id, admin_routes.AdminBody(is_admin=True), admin=admin, db=db)
    assert alumna.evaluator_profile == "teacher"

    admin_routes.set_admin(alumna.id, admin_routes.AdminBody(is_admin=False), admin=admin, db=db)
    assert alumna.evaluator_profile == "teacher"


# WHAT IT DECIDES: CREATING A SUBJECT ----------------------------------------------------------


def test_a_teacher_creates_a_subject(db):
    docente = _account(db, "docente", "teacher")

    created = workspace_routes.create(
        workspace_routes.CreateBody(slug="prog-uno", name="Programación I"), user=docente, db=db
    )

    assert created["workspace"]["slug"] == "prog-uno"
    workspace = repository.get_workspace(db, "prog-uno")
    assert identity.membership(db, workspace.id, docente.id).via == "owner"


@pytest.mark.parametrize("profile", ["student", None])
def test_a_student_creates_none_and_a_missing_profile_fails_closed(db, profile):
    cuenta = _account(db, "cuenta", profile)

    with pytest.raises(HTTPException) as refused:
        workspace_routes.create(workspace_routes.CreateBody(slug="suya"), user=cuenta, db=db)

    assert refused.value.status_code == 403
    assert refused.value.headers == {"X-Error-Code": workspace_routes.CANNOT_CREATE}


def test_the_listing_says_whether_the_account_creates(db):
    assert workspace_routes.listing(user=_account(db, "docente", "teacher"), db=db)["can_create"] is True
    assert workspace_routes.listing(user=_account(db, "alumna", "student"), db=db)["can_create"] is False


# HOW SOMEBODY ENTERED A SUBJECT ---------------------------------------------------------------


def test_a_membership_remembers_the_invitation_and_who_minted_it(db, admin):
    workspace = repository.ensure_workspace(db, "aula", "Aula")
    link = _invite(db, admin, profile="student", workspace="aula", role="viewer")["link"]

    alumna = _register(db, link, "alumna")
    row = identity.membership(db, workspace.id, alumna.id)

    assert (row.role, row.via, row.invited_by) == ("viewer", "invite", admin.id)
    assert row.disabled_at is None

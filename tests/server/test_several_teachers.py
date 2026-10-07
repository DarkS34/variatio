"""A subject with several teachers, a tutor opened to whole subjects, and invitations by mail.

The class plan's phase 15. An owner names other owners, lowers them, removes teachers and
hands the ownership over — two role changes, after which the subject still has an owner and
never none. The tutor may list subjects as well as accounts: everybody in a listed subject
uses it there, and only there. A teacher's personal invitations may go by mail where the
installation sends mail; the address is kept nowhere.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from server import features
from server.auth import mail, passwords, rate_limit
from server.db import identity, repository
from server.db.models import EDITOR, OWNER, VIEWER, Base, Invite
from server.routers import admin as admin_routes
from server.routers import members as member_routes
from server.routers.admin import FeatureBody
from server.routers.auth import _me
from server.routers.members import InvitesBody, RoleBody


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(identity, "now", datetime.now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    yield session
    session.close()


@pytest.fixture(autouse=True)
def forget_the_attempts():
    rate_limit.limiter._hits.clear()
    yield
    rate_limit.limiter._hits.clear()


@pytest.fixture
def aula(db):
    """A subject with its owner, a second teacher and a student, and another subject."""
    workspace = repository.ensure_workspace(db, "aula", "Programación I")
    otra = repository.ensure_workspace(db, "otra", "Otra")
    people = {}
    for username, role, profile in (
        ("ana", OWNER, "teacher"),
        ("bruno", EDITOR, "teacher"),
        ("sara", VIEWER, "student"),
    ):
        user = identity.create_user(
            db, username=username, name=username.title(), password_hash="x", evaluator_profile=profile
        )
        identity.grant(db, workspace.id, user.id, role)
        people[username] = user
    identity.grant(db, otra.id, people["sara"].id, VIEWER)
    admin = identity.create_user(db, username="admin", name="Admin", password_hash="x", is_admin=True)
    db.flush()
    return SimpleNamespace(workspace=workspace, otra=otra, admin=admin, **people)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"host", b"localhost"), (b"origin", b"http://localhost")],
            "client": ("10.0.0.9", 1234),
            "scheme": "http",
            "server": ("localhost", 8000),
            "query_string": b"",
        }
    )


def _as(aula, user, role, workspace=None):
    workspace = workspace or aula.workspace
    return SimpleNamespace(user=user, workspace=workspace, role=role, ws=SimpleNamespace(slug=workspace.slug))


# THE TEACHERS OF A SUBJECT -------------------------------------------------------------------


def test_handing_over_the_ownership_leaves_one_owner_and_never_none(db, aula):
    owner = _as(aula, aula.ana, OWNER)

    with pytest.raises(HTTPException) as refused:
        member_routes.change_role(aula.ana.id, RoleBody(role=EDITOR), access=owner, db=db)
    assert refused.value.status_code == 409

    member_routes.change_role(aula.bruno.id, RoleBody(role=OWNER), access=owner, db=db)
    member_routes.change_role(aula.ana.id, RoleBody(role=EDITOR), access=owner, db=db)

    roles = {u.username: m.role for m, u in identity.members_of(db, aula.workspace.id)}
    assert roles == {"ana": EDITOR, "bruno": OWNER, "sara": VIEWER}


def test_a_teacher_changes_no_role(db, aula):
    from server.auth import at_least

    assert not at_least(_as(aula, aula.bruno, EDITOR), OWNER)


# THE TUTOR FOR A SUBJECT --------------------------------------------------------------------


def test_a_listed_subject_opens_the_tutor_to_everybody_in_it_and_only_there(db, aula):
    admin_routes.set_feature(
        "tutor", FeatureBody(mode="selected", workspaces=["aula"]), admin=aula.admin, db=db
    )

    assert features.enabled(db, aula.sara, features.TUTOR, aula.workspace)
    assert features.enabled(db, aula.bruno, features.TUTOR, aula.workspace)
    assert not features.enabled(db, aula.sara, features.TUTOR, aula.otra)
    assert not features.enabled(db, aula.sara, features.TUTOR)
    assert features.offered_to_students(db, aula.workspace)


def test_the_session_says_the_tutor_of_the_subject_the_account_is_in(db, aula):
    admin_routes.set_feature(
        "tutor", FeatureBody(mode="selected", workspaces=["aula"]), admin=aula.admin, db=db
    )

    aula.sara.active_workspace_id = aula.workspace.id
    db.flush()
    assert _me(db, aula.sara)["features"]["tutor"] is True
    aula.sara.active_workspace_id = aula.otra.id
    db.flush()
    assert _me(db, aula.sara)["features"]["tutor"] is False


def test_the_subjects_are_replaced_only_when_sent_and_named_by_slug(db, aula):
    admin_routes.set_feature(
        "tutor", FeatureBody(mode="selected", workspaces=["aula", "otra"]), admin=aula.admin, db=db
    )
    answer = admin_routes.set_feature("tutor", FeatureBody(mode="all"), admin=aula.admin, db=db)

    assert answer["features"]["tutor"]["workspaces"] == ["aula", "otra"]
    assert "workspaces" not in answer["features"]["evaluation"]


@pytest.mark.parametrize(
    ("feature", "workspaces"),
    [("evaluation", ["aula"]), ("tutor", ["no-existe"])],
)
def test_the_evaluation_lists_no_subject_and_an_unknown_one_is_refused(db, aula, feature, workspaces):
    with pytest.raises(HTTPException) as refused:
        admin_routes.set_feature(
            feature, FeatureBody(mode="selected", workspaces=workspaces), admin=aula.admin, db=db
        )

    assert refused.value.status_code == 422


# INVITATIONS BY MAIL -----------------------------------------------------------------------


def test_an_address_needs_an_installation_that_sends_mail(db, aula, monkeypatch):
    monkeypatch.setattr(mail, "configured", lambda: False)

    with pytest.raises(HTTPException) as refused:
        member_routes.mint_invites(
            InvitesBody(names=["Ana Gil"], emails=["ana@colegio.es"]),
            _request(),
            access=_as(aula, aula.bruno, EDITOR),
            db=db,
        )

    assert refused.value.status_code == 422


def test_each_invitation_with_an_address_is_sent_and_the_address_kept_nowhere(db, aula, monkeypatch):
    monkeypatch.setattr(mail, "configured", lambda: True)
    delivered = []

    def deliver(message):
        if message["To"] == "falla@colegio.es":
            raise OSError("buzón lleno")
        delivered.append((message["To"], message.get_content()))

    monkeypatch.setattr(mail, "_deliver", deliver)

    answer = member_routes.mint_invites(
        InvitesBody(
            names=["Ana Gil", "Pablo Ruiz", "Sin Correo"],
            emails=["ana@colegio.es", "falla@colegio.es", None],
        ),
        _request(),
        access=_as(aula, aula.bruno, EDITOR),
        db=db,
    )

    assert [row.get("sent") for row in answer["invites"]] == [True, False, None]
    assert delivered[0][0] == "ana@colegio.es"
    assert answer["invites"][0]["link"] in delivered[0][1]
    stored = " ".join(
        f"{row.label} {row.token_sealed} {row.features}" for row in db.query(Invite).all()
    )
    assert "colegio.es" not in stored


@pytest.mark.parametrize("emails", [["no es un correo"], ["a@b.es", "c@d.es"]])
def test_a_wrong_address_or_a_wrong_count_is_refused(db, aula, monkeypatch, emails):
    monkeypatch.setattr(mail, "configured", lambda: True)

    with pytest.raises(HTTPException) as refused:
        member_routes.mint_invites(
            InvitesBody(names=["Ana Gil"], emails=emails),
            _request(),
            access=_as(aula, aula.bruno, EDITOR),
            db=db,
        )

    assert refused.value.status_code == 422

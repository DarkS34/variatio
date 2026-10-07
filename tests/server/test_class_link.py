"""A teacher brings their class in with links, and nobody else has to.

The class link is one link for a whole class: as many registrations as it has seats, an
expiry, a pause, and a renewal that retires it. A seat is taken by ONE conditional statement,
so two students racing for the last one get one account between them. Every account it
creates is a student's, whatever the request says. A personal invitation of a subject is the
administrator's table scoped to it: a teacher mints students' and an owner teachers' too.
"""

import threading
from argparse import Namespace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from server import auth, installation
from server.auth import links, passwords, rate_limit
from server.db import identity, repository
from server.db import session as db_session
from server.db.models import EDITOR, OWNER, VIEWER, Base, ClassLink, Invite
from server.routers import admin as admin_routes
from server.routers import auth as auth_routes
from server.routers import members as member_routes
from server.routers.auth import AcceptBody, JoinBody

PASSWORD = "una-contraseña-larga"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    # SQLite drops the offset Postgres keeps; every moment below is compared naive.
    monkeypatch.setattr(identity, "now", datetime.now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    yield session
    session.close()


@pytest.fixture(autouse=True)
def forget_the_address():
    for bucket in ("accept", "accept_class", "join", "teacher_invite", "invite"):
        rate_limit.unlock(bucket, "10.0.0.1")
    yield
    rate_limit.limiter._hits.clear()


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


@pytest.fixture
def aula(db):
    """A subject with its owner and a second teacher."""
    workspace = repository.ensure_workspace(db, "aula", "Programación I")
    ana = identity.create_user(db, username="ana", name="Ana Pérez", password_hash="x", evaluator_profile="teacher")
    bruno = identity.create_user(db, username="bruno", name="Bruno", password_hash="x", evaluator_profile="teacher")
    identity.grant(db, workspace.id, ana.id, OWNER)
    identity.grant(db, workspace.id, bruno.id, EDITOR)
    db.flush()
    return SimpleNamespace(workspace=workspace, ana=ana, bruno=bruno)


def _access(db, user, workspace):
    return auth.access_for(db, user, workspace, VIEWER)


def _mint(db, aula, teacher=None, **terms) -> str:
    answer = member_routes.mint_class_link(
        member_routes.ClassLinkBody(**terms),
        _request(),
        access=_access(db, teacher or aula.bruno, aula.workspace),
        db=db,
    )
    return answer["link"].split("token=")[1]


def _register(db, token: str, username: str, **sent):
    auth_routes.accept_invite(
        AcceptBody(token=token, username=username, name=username, password=PASSWORD, **sent),
        _request(),
        Response(),
        session=db,
    )
    return identity.get_user(db, username)


def _refused(call) -> HTTPException:
    with pytest.raises(HTTPException) as refused:
        call()
    return refused.value


# REGISTERING THROUGH IT -------------------------------------------------------------------------


def test_three_registrations_fill_three_seats_and_the_fourth_is_told(db, aula):
    token = _mint(db, aula, max_uses=3)

    accounts = [_register(db, token, f"alumno{n}") for n in range(3)]
    refused = _refused(lambda: _register(db, token, "alumno3"))

    assert refused.status_code == 409
    assert refused.headers == {"X-Error-Code": auth_routes.CLASS_LINK_FULL}
    for account in accounts:
        row = identity.membership(db, aula.workspace.id, account.id)
        assert (row.role, row.via, row.invited_by) == (VIEWER, "class_link", aula.bruno.id)
        assert account.evaluator_profile == "student"
        assert account.active_workspace_id == aula.workspace.id


def test_a_paused_link_says_so(db, aula):
    token = _mint(db, aula)
    member_routes.edit_class_link(
        member_routes.ClassLinkEditBody(paused=True), access=_access(db, aula.bruno, aula.workspace), db=db
    )

    refused = _refused(lambda: _register(db, token, "alumno"))

    assert refused.status_code == 409
    assert refused.headers == {"X-Error-Code": auth_routes.CLASS_LINK_PAUSED}


def test_a_renewed_link_retires_the_old_one(db, aula):
    old = _mint(db, aula)
    new = _mint(db, aula)

    assert _refused(lambda: _register(db, old, "tarde")).status_code == 404
    assert _register(db, new, "pronto").evaluator_profile == "student"


def test_the_account_is_a_students_whatever_the_request_says(db, aula):
    token = _mint(db, aula)

    assert _register(db, token, "lista", evaluator_profile="teacher").evaluator_profile == "student"


def test_an_account_that_cannot_be_created_gives_its_seat_back(db, aula, monkeypatch):
    token = _mint(db, aula, max_uses=1)
    db.commit()  # the link was minted by an earlier request

    def taken(*args, **kwargs):
        raise IntegrityError("INSERT", {}, Exception("unique"))

    monkeypatch.setattr(identity, "create_user", taken)
    refused = _refused(lambda: _register(db, token, "carrera"))

    assert refused.status_code == 409
    link = identity.live_class_link(db, aula.workspace.id)
    db.refresh(link)
    assert link.uses == 0


def test_the_preview_names_the_subject_and_who_invites_and_no_seats(db, aula):
    token = _mint(db, aula)

    preview = auth_routes.preview_invite(token, session=db)

    assert preview["kind"] == "class"
    assert preview["workspace"] == "Programación I"
    assert preview["inviter"] == "Bruno"
    assert preview["profile"] == "student"
    assert preview["role"] == VIEWER
    assert "asks_profile" not in preview
    assert not {"uses", "max_uses", "seats"} & set(preview)


def test_a_whole_class_registers_through_one_link_in_an_hour(db, aula):
    token = _mint(db, aula, max_uses=40)

    for n in range(15):
        _register(db, token, f"clase{n:02d}")

    assert identity.live_class_link(db, aula.workspace.id).uses == 15


def test_a_personal_link_still_stops_at_the_tenth_attempt_of_the_hour(db, aula):
    invite, token = links.mint(db, expires_at=identity.now() + timedelta(days=1), workspace_id=aula.workspace.id)
    _register(db, token, "primera")
    answers = []
    for n in range(10):
        try:
            _register(db, token, f"otro{n}")
        except HTTPException as refused:
            answers.append(refused.status_code)

    assert answers[-1] == 429
    assert set(answers[:-1]) == {404}


def test_two_registrations_racing_for_the_last_seat_make_one_account(monkeypatch):
    """Two threads, two connections, one statement deciding: never two students in one seat."""
    monkeypatch.setattr(identity, "now", datetime.now)
    engine = db_session.engine()
    Base.metadata.create_all(engine)
    with db_session.session_scope() as session:
        workspace = repository.ensure_workspace(session, "carrera", "Carrera")
        _, token = links.mint_class_link(
            session,
            workspace_id=workspace.id,
            expires_at=identity.now() + timedelta(days=1),
            max_uses=1,
        )
    start = threading.Barrier(2)
    outcomes: list[object] = []

    def register(username: str):
        start.wait()
        try:
            with db_session.session_scope() as session:
                auth_routes.accept_invite(
                    AcceptBody(token=token, username=username, name=username, password=PASSWORD),
                    _request(),
                    Response(),
                    session=session,
                )
            outcomes.append("in")
        except HTTPException as refused:
            outcomes.append(refused.status_code)
        except Exception as other:  # noqa: BLE001 - reported by the assertion below
            outcomes.append(repr(other))

    original = passwords.hash_password
    passwords.hash_password = lambda password: "hashed"
    try:
        threads = [threading.Thread(target=register, args=(name,)) for name in ("uno", "dos")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
    finally:
        passwords.hash_password = original

    assert sorted(outcomes, key=str) == [409, "in"]
    with db_session.session_scope() as session:
        link = session.query(ClassLink).one()
        assert link.uses == 1
        assert {identity.get_user(session, "uno") is None, identity.get_user(session, "dos") is None} == {True, False}


# AN ACCOUNT THAT EXISTS -------------------------------------------------------------------------


def _join(db, user, token: str) -> dict:
    return auth_routes.join(JoinBody(token=token), _request(), user=user, session=db)


@pytest.fixture
def luis(db):
    """A student of another subject, landed there."""
    otra = repository.ensure_workspace(db, "otra", "Otra")
    user = identity.create_user(db, username="luis", name="Luis", password_hash="x", evaluator_profile="student")
    identity.grant(db, otra.id, user.id, VIEWER)
    user.active_workspace_id = otra.id
    db.flush()
    return user


def test_an_account_of_another_subject_joins_with_the_class_link(db, aula, luis):
    token = _mint(db, aula)

    me = _join(db, luis, token)

    assert me["already"] is False
    assert me["active_workspace"] == "aula"
    assert sorted(row["slug"] for row in me["workspaces"]) == ["aula", "otra"]
    row = identity.membership(db, aula.workspace.id, luis.id)
    assert (row.role, row.via) == (VIEWER, "class_link")
    assert identity.live_class_link(db, aula.workspace.id).uses == 1


def test_a_link_never_lowers_anybody(db, aula):
    token = _mint(db, aula)

    me = _join(db, aula.bruno, token)

    assert me["already"] is True
    assert identity.membership(db, aula.workspace.id, aula.bruno.id).role == EDITOR
    assert identity.live_class_link(db, aula.workspace.id).uses == 0


def test_a_personal_link_used_to_join_is_spent(db, aula, luis):
    answer = member_routes.mint_invites(
        member_routes.InvitesBody(names=["Luis"]), _request(), access=_access(db, aula.bruno, aula.workspace), db=db
    )
    token = answer["invites"][0]["link"].split("token=")[1]

    _join(db, luis, token)

    assert identity.live_invite(db, auth.digest(token)) is None
    assert identity.membership(db, aula.workspace.id, luis.id).via == "invite"


def test_a_false_token_is_the_same_404_everywhere(db, aula, luis):
    fake = "x" * 43

    joined = _refused(lambda: _join(db, luis, fake))
    accepted = _refused(lambda: _register(db, fake, "nadie"))

    assert joined.status_code == accepted.status_code == 404
    assert joined.detail == accepted.detail


def test_a_paused_member_does_not_come_back_with_the_link(db, aula, luis):
    from server import members

    token = _mint(db, aula)
    _join(db, luis, token)
    members.disable_member(db, aula.workspace, luis, aula.bruno)

    refused = _refused(lambda: _join(db, luis, token))

    assert refused.status_code == 409
    assert refused.headers == {"X-Error-Code": auth.MEMBERSHIP_DISABLED}
    assert identity.live_class_link(db, aula.workspace.id).uses == 1
    assert identity.membership(db, aula.workspace.id, luis.id).disabled_at is not None


# A TEACHER'S PERSONAL INVITATIONS ---------------------------------------------------------------


def test_a_teacher_invites_students_and_not_teachers(db, aula):
    access = _access(db, aula.bruno, aula.workspace)

    answer = member_routes.mint_invites(
        member_routes.InvitesBody(names=["Ana Gil", "  Pablo  Ruiz "]), _request(), access=access, db=db
    )
    refused = _refused(lambda: member_routes.mint_invites(
        member_routes.InvitesBody(names=["Otra Docente"], role="editor"), _request(), access=access, db=db
    ))

    assert [row["invite"]["label"] for row in answer["invites"]] == ["Ana Gil", "Pablo Ruiz"]
    assert {row["invite"]["role"] for row in answer["invites"]} == {VIEWER}
    assert {row["invite"]["profile"] for row in answer["invites"]} == {"student"}
    assert refused.status_code == 403


def test_an_owner_invites_a_teacher_whose_account_is_a_teachers(db, aula):
    answer = member_routes.mint_invites(
        member_routes.InvitesBody(names=["Nueva Docente"], role="editor"),
        _request(),
        access=_access(db, aula.ana, aula.workspace),
        db=db,
    )
    token = answer["invites"][0]["link"].split("token=")[1]

    nueva = _register(db, token, "nueva")

    assert nueva.evaluator_profile == "teacher"
    assert identity.membership(db, aula.workspace.id, nueva.id).role == EDITOR


def test_another_subjects_invitations_are_unknown_here(db, aula):
    otra = repository.ensure_workspace(db, "ajena", "Ajena")
    invite, _ = links.mint(db, expires_at=identity.now() + timedelta(days=1), workspace_id=otra.id)
    access = _access(db, aula.bruno, aula.workspace)

    listed = member_routes.invites(access=access, db=db)["invites"]
    read = _refused(lambda: member_routes.invite_link(invite.id, _request(), access=access, db=db))
    deleted = _refused(lambda: member_routes.revoke_invite(invite.id, access=access, db=db))

    assert listed == []
    assert read.status_code == deleted.status_code == 404
    assert db.get(Invite, invite.id) is not None


def test_a_teacher_reads_their_invitations_link_again_and_deletes_one(db, aula):
    access = _access(db, aula.bruno, aula.workspace)
    minted = member_routes.mint_invites(member_routes.InvitesBody(names=["Una"]), _request(), access=access, db=db)
    invite_id = minted["invites"][0]["invite"]["id"]

    again = member_routes.invite_link(invite_id, _request(), access=access, db=db)
    member_routes.revoke_invite(invite_id, access=access, db=db)

    assert again["link"] == minted["invites"][0]["link"]
    assert member_routes.invites(access=access, db=db)["invites"] == []


# THE LINK'S TERMS -------------------------------------------------------------------------------


def test_a_new_link_has_forty_seats_and_a_month_unless_told(db, aula):
    access = _access(db, aula.bruno, aula.workspace)
    member_routes.mint_class_link(member_routes.ClassLinkBody(), _request(), access=access, db=db)

    view = member_routes.class_link(access=access, db=db)["class_link"]

    assert (view["uses"], view["max_uses"], view["paused"]) == (0, 40, False)
    expires = datetime.fromisoformat(view["expires_at"])
    assert timedelta(days=29) < expires - datetime.now() <= timedelta(days=30)
    assert "token" not in str(view)


@pytest.mark.parametrize(
    "terms",
    [
        {"max_uses": 0},
        {"max_uses": installation.CLASS_LINK_MAX_SEATS + 1},
        {"expires_at": datetime.now() + timedelta(days=installation.TEACHER_LINK_MAX_DAYS + 2)},
        {"expires_at": datetime.now() - timedelta(days=1)},
    ],
)
def test_a_link_out_of_bounds_is_refused(db, aula, terms):
    refused = _refused(lambda: _mint(db, aula, **terms))

    assert refused.status_code == 422


def test_its_seats_never_go_below_the_ones_taken(db, aula):
    token = _mint(db, aula, max_uses=5)
    _register(db, token, "una")
    _register(db, token, "otra")
    access = _access(db, aula.bruno, aula.workspace)

    refused = _refused(lambda: member_routes.edit_class_link(
        member_routes.ClassLinkEditBody(max_uses=1), access=access, db=db
    ))
    member_routes.edit_class_link(member_routes.ClassLinkEditBody(max_uses=2), access=access, db=db)

    assert refused.status_code == 422
    assert member_routes.class_link(access=access, db=db)["class_link"]["max_uses"] == 2


def test_the_live_link_is_read_again_and_revoked(db, aula):
    access = _access(db, aula.bruno, aula.workspace)
    token = _mint(db, aula)

    again = member_routes.class_link_url(_request(), access=access, db=db)["link"]
    member_routes.revoke_class_link(access=access, db=db)

    assert again.endswith(token)
    assert member_routes.class_link(access=access, db=db)["class_link"] is None
    assert _refused(lambda: _register(db, token, "tarde")).status_code == 404


# THE ADMINISTRATOR AND THE COMMAND LINE ---------------------------------------------------------


def test_the_administrator_sees_pauses_and_retires_a_subjects_link(db, aula):
    admin = identity.create_user(db, username="root", name="Root", password_hash="x", is_admin=True)
    token = _mint(db, aula)

    [row] = admin_routes.class_links(db=db)["class_links"]
    admin_routes.pause_class_link(row["id"], admin_routes.ClassLinkEditBody(paused=True), admin=admin, db=db)
    paused = _refused(lambda: _register(db, token, "pausa"))
    admin_routes.revoke_class_link(row["id"], admin=admin, db=db)

    assert (row["workspace"], row["created_by"]) == ("aula", "bruno")
    assert paused.headers == {"X-Error-Code": auth_routes.CLASS_LINK_PAUSED}
    assert admin_routes.class_links(db=db)["class_links"] == []


def test_the_command_line_prints_the_link_and_renews_it(capsys, monkeypatch):
    from server.cli import accounts

    Base.metadata.create_all(db_session.engine())
    monkeypatch.setattr(installation, "public_base_url", lambda: "https://variatio.app")
    with db_session.session_scope() as session:
        repository.ensure_workspace(session, "linea", "Línea")

    def run(**flags) -> str:
        options = {"workspace": "linea", "seats": None, "days": None, "renew": False, **flags}
        assert accounts.class_link(Namespace(**options)) == 0
        return capsys.readouterr().out.splitlines()[0]

    first = run(seats=12)
    same = run()
    renewed = run(renew=True)

    assert first.startswith("https://variatio.app/invite?token=")
    assert same == first
    assert renewed != first

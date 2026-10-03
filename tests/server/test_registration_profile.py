"""Who answers "docente o alumno", and where the answer has to arrive.

The invitation carries nothing about it: the link binds the access and the person
registering says whether they teach or study, which is the one moment they are in front of
a form. So the hop worth watching is `/accept` — nothing after it re-asks, and the only
other way in is `create-user`, where the administrator answers because there is no form.

NULL stays reachable on purpose (`create-user` with no `--profile`, and every account older
than the question), so what makes registration different is that it REFUSES to leave it
unanswered rather than the validator having changed.
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
from server.db import identity
from server.db.models import Base
from server.routers.admin import InviteBody, create_invite
from server.routers.auth import AcceptBody, accept_invite


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    # SQLite drops the offset Postgres keeps, so an expiry read back from this engine is
    # naive and `live_invite` would raise comparing it against an aware clock. The clock is
    # what moves here, not the code under test: every link below is far from expiring.
    monkeypatch.setattr(identity, "now", datetime.now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    yield session
    session.close()


@pytest.fixture
def admin(db):
    return identity.create_user(
        db, username="admin", name="admin", password_hash="x", is_admin=True
    )


# `/accept` is throttled by IP and by invitation, and the limiter is one object for the
# whole process: every request below comes from the same fake address, so without this the
# run itself trips the `accept` bucket and a test reads 429 where it asserted 422.
@pytest.fixture(autouse=True)
def forget_the_address():
    rate_limit.unlock("accept", "10.0.0.1")


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


def _link(db, admin) -> str:
    created = create_invite(
        InviteBody(workspace=None, role="editor"), _request(), admin=admin, db=db
    )
    # The link says who may enter and nothing about who they are.
    assert "evaluator_profile" not in created["invite"]
    return created["link"]


def _register(db, link: str, username: str, profile: str | None):
    accept_invite(
        AcceptBody(
            token=link.split("token=")[1],
            username=username,
            name=username,
            password="una-contraseña-larga",
            evaluator_profile=profile,
        ),
        _request(),
        Response(),
        session=db,
    )
    return identity.get_user(db, username)


def test_the_profile_chosen_while_registering_is_the_accounts(db, admin):
    assert _register(db, _link(db, admin), "ana", "teacher").evaluator_profile == "teacher"


def test_the_other_one_too(db, admin):
    assert _register(db, _link(db, admin), "bruno", "student").evaluator_profile == "student"


def test_registering_without_answering_is_refused(db, admin):
    with pytest.raises(HTTPException) as refused:
        _register(db, _link(db, admin), "nadie", None)
    assert refused.value.status_code == 422

    # And the refusal costs nothing: the invitation is still there to be redeemed.
    assert identity.get_user(db, "nadie") is None


def test_an_unknown_profile_is_refused(db, admin):
    with pytest.raises(HTTPException) as refused:
        _register(db, _link(db, admin), "otra", "profesora")
    assert refused.value.status_code == 422
    assert "profesora" in refused.value.detail

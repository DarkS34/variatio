from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request
from starlette.responses import Response

from server.auth import passwords, rate_limit, tokens
from server.db import identity
from server.db.models import Base, Invite
from server.routers.auth import AcceptBody, accept_invite

TOKEN = "un-enlace-de-invitacion"
DIGEST = tokens.digest(TOKEN)
IP = "10.0.0.9"


# A file rather than the usual in-memory database: the race needs two sessions that really
# are two, and a shared-cache memory engine hands both of them the same connection.
@pytest.fixture
def sessions(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'identity.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(identity, "now", datetime.now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    opened = []

    def open_session():
        session = factory()
        opened.append(session)
        return session

    yield open_session

    for session in opened:
        session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def forget_the_attempts():
    for key in (IP, DIGEST, "203.0.113.7"):
        rate_limit.limiter.clear("accept", key)
    yield
    for key in (IP, DIGEST, "203.0.113.7"):
        rate_limit.limiter.clear("accept", key)


def _request(ip: str = IP) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"host", b"localhost"), (b"origin", b"http://localhost")],
            "client": (ip, 1234),
            "scheme": "http",
            "server": ("localhost", 8000),
            "query_string": b"",
        }
    )


def _accept(session, username: str, ip: str = IP):
    return accept_invite(
        AcceptBody(
            token=TOKEN,
            username=username,
            name=username,
            password="una-contraseña-larga",
        ),
        _request(ip),
        Response(),
        session=session,
    )


def _invite(session) -> None:
    identity.create_invite(session, token_hash=DIGEST, ttl=timedelta(days=1))
    session.commit()


def test_only_one_of_two_sessions_racing_on_one_invitation_claims_it(sessions):
    one, two = sessions(), sessions()
    _invite(one)

    # Both read the row while it is still live, which is the window the Argon2 hash sat in.
    first = identity.live_invite(one, DIGEST)
    second = identity.live_invite(two, DIGEST)
    assert first is not None and second is not None

    assert identity.claim_invite(one, first) is True
    one.commit()

    assert identity.claim_invite(two, second) is False


def test_the_registration_that_loses_the_race_is_refused_and_creates_nothing(
    sessions, monkeypatch
):
    one, two = sessions(), sessions()
    _invite(one)

    stale = identity.live_invite(two, DIGEST)
    assert identity.claim_invite(one, identity.live_invite(one, DIGEST)) is True
    one.commit()

    # What the loser of the race sees: the read that happened before the other side wrote.
    monkeypatch.setattr(identity, "live_invite", lambda *_: stale)

    with pytest.raises(HTTPException) as refused:
        _accept(two, "beto")

    assert refused.value.status_code == 404
    assert "invitación" in refused.value.detail
    assert identity.get_user(two, "beto") is None


def test_the_first_registration_still_goes_through_and_is_attributed(sessions):
    session = sessions()
    _invite(session)

    _accept(session, "ana")

    user = identity.get_user(session, "ana")
    assert user is not None
    invite = session.get(identity.Invite, 1)
    assert invite.used_at is not None
    assert invite.used_by == user.id
    assert identity.live_invite(session, DIGEST) is None


def test_a_username_that_is_taken_still_says_which_one(sessions):
    session = sessions()
    identity.create_user(session, username="ana", name="ana", password_hash="x")
    _invite(session)

    with pytest.raises(HTTPException) as refused:
        _accept(session, "ana")

    assert refused.value.status_code == 409
    assert "ana" in refused.value.detail


def test_registering_is_throttled_by_address(sessions):
    session = sessions()
    limit, window = rate_limit.limits("accept")
    for _ in range(limit):
        rate_limit.limiter.check("accept", IP, limit, window)

    with pytest.raises(HTTPException) as refused:
        _accept(session, "ana")

    assert refused.value.status_code == 429


def test_and_by_the_invitation_it_is_redeeming(sessions):
    session = sessions()
    limit, window = rate_limit.limits("accept")
    for _ in range(limit):
        rate_limit.limiter.check("accept", DIGEST, limit, window)

    # Another address entirely: what bounds the enumeration is the link, not the machine.
    with pytest.raises(HTTPException) as refused:
        _accept(session, "ana", ip="203.0.113.7")

    assert refused.value.status_code == 429


# WHAT MAKES CLAIMING FIRST SAFE ---------------------------------------------------------
#
# The claim happens before the username check and the password policy, so a legitimate
# invitee who picks a taken name would burn their only link if the request did not roll
# back. It does: FastAPI throws the route's exception into the yield-dependency, and
# `session_scope` rolls back on `BaseException`. Nothing pinned that, and moving the commit
# or swallowing the exception in the dependency would silently start eating invitations.
def test_a_refusal_after_the_claim_gives_the_invitation_back(tmp_path):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import update

    from server.db.session import session_scope

    engine = create_engine(f"sqlite:///{tmp_path / 'rollback.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def scope():
        with session_scope() as session:
            yield session

    app = FastAPI()

    @app.post("/claim-then-refuse")
    def claim_then_refuse(db=Depends(scope)):
        db.execute(
            update(Invite).where(Invite.id == 1, Invite.used_at.is_(None)).values(used_at=datetime.now())
        )
        db.flush()
        raise HTTPException(409, "el nombre ya está cogido")

    with factory() as session:
        session.add(
            Invite(
                id=1,
                token_hash=DIGEST,
                role="editor",
                expires_at=datetime.now() + timedelta(days=7),
            )
        )
        session.commit()

    with patch("server.db.session.factory", lambda: factory):
        response = TestClient(app, raise_server_exceptions=False).post("/claim-then-refuse")

    assert response.status_code == 409
    with factory() as session:
        assert session.scalar(select(Invite).where(Invite.id == 1)).used_at is None

    engine.dispose()

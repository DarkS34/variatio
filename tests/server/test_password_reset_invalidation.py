from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from server import settings
from server.auth import passwords, rate_limit, tokens
from server.db import identity
from server.db.models import Base
from server.routers.auth import (
    Credentials,
    PasswordBody,
    ResetBody,
    change_password,
    login,
    reset,
)

IP = "10.0.0.11"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(identity, "now", datetime.now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    monkeypatch.setattr(passwords, "verify_password", lambda stored, given: True)
    yield session
    session.close()


@pytest.fixture(autouse=True)
def forget_the_attempts():
    for bucket in ("login", "password", "reset"):
        rate_limit.limiter.clear(bucket, IP)
        rate_limit.limiter.clear(bucket, "ana")
    yield


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"host", b"localhost"), (b"origin", b"http://localhost")],
            "client": (IP, 1234),
            "scheme": "http",
            "server": ("localhost", 8000),
            "query_string": b"",
        }
    )


def _account(db, username: str = "ana"):
    return identity.create_user(db, username=username, name=username, password_hash="viejo")


def _link(db, user, token: str) -> str:
    identity.create_reset(db, user.id, tokens.digest(token), settings.RESET_TTL)
    return token


def test_changing_the_password_retires_every_pending_reset_link(db):
    user = _account(db)
    _link(db, user, "uno")
    _link(db, user, "dos")

    change_password(
        PasswordBody(current="lo-que-sea", new="una-contraseña-larga"),
        _request(),
        Response(),
        user=user,
        session=db,
    )

    assert identity.live_reset(db, tokens.digest("uno")) is None
    assert identity.live_reset(db, tokens.digest("dos")) is None


def test_using_one_reset_link_retires_the_others(db):
    user = _account(db)
    _link(db, user, "uno")
    _link(db, user, "dos")

    reset(
        ResetBody(token="uno", password="una-contraseña-larga"),
        _request(),
        Response(),
        session=db,
    )

    assert identity.live_reset(db, tokens.digest("uno")) is None
    assert identity.live_reset(db, tokens.digest("dos")) is None


def test_a_login_that_rehashes_retires_them_too(db, monkeypatch):
    user = _account(db)
    _link(db, user, "uno")
    monkeypatch.setattr(passwords, "needs_rehash", lambda stored: True)

    login(
        Credentials(username="ana", password="una-contraseña-larga"),
        _request(),
        Response(),
        session=db,
    )

    assert identity.live_reset(db, tokens.digest("uno")) is None


def test_another_accounts_links_are_left_alone(db):
    user = _account(db)
    other = _account(db, "bruno")
    _link(db, user, "uno")
    _link(db, other, "dos")

    change_password(
        PasswordBody(current="lo-que-sea", new="una-contraseña-larga"),
        _request(),
        Response(),
        user=user,
        session=db,
    )

    assert identity.live_reset(db, tokens.digest("uno")) is None
    assert identity.live_reset(db, tokens.digest("dos")) is not None


def test_a_link_that_had_already_expired_is_not_recorded_as_used(db):
    user = _account(db)
    identity.create_reset(db, user.id, tokens.digest("caducado"), timedelta(minutes=-5))

    change_password(
        PasswordBody(current="lo-que-sea", new="una-contraseña-larga"),
        _request(),
        Response(),
        user=user,
        session=db,
    )

    stored = db.query(identity.PasswordReset).filter_by(token_hash=tokens.digest("caducado")).one()
    assert stored.used_at is None

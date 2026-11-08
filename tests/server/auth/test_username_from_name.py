"""The username a registration makes from the name (D-243).

The form asks for the name alone since 2026-11-04, so the server makes the identifier the
person signs in with: folded, dotted, and numbered when somebody has it already.
"""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from server.auth import passwords, queries, rate_limit, tokens
from server.auth.routes.auth import AcceptBody, accept_invite
from server.db.models import Base

TOKEN = "un-enlace-para-el-nombre"
IP = "10.0.0.21"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(queries, "now", datetime.now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    rate_limit.limiter.clear("accept", tokens.digest(TOKEN))
    yield session
    session.close()
    rate_limit.limiter.clear("accept", tokens.digest(TOKEN))


def _user(db, username: str) -> None:
    queries.create_user(db, username=username, name=username, password_hash="x")


@pytest.mark.parametrize(
    ("name", "username"),
    [
        ("Ana Pérez García", "ana.perez"),
        ("  María José  ", "maria.jose"),
        ("Ana de la Peña", "ana.pena"),
        ("Luis", "luis"),
        ("Ñoño D'Alembert", "nono.alembert"),
        ("Ana M. Pérez", "ana.perez"),
        ("Al", "al1"),
        ("李华", "usuario"),
    ],
)
def test_a_name_becomes_a_valid_username(db, name, username):
    made = queries.username_from_name(db, name)

    assert made == username
    assert queries.username_error(made) is None


def test_a_taken_username_gets_the_first_free_number(db):
    _user(db, "ana.perez")
    _user(db, "ana.perez2")
    _user(db, "ana.perez.lopez")

    assert queries.username_from_name(db, "Ana Pérez") == "ana.perez3"


def test_a_long_name_still_fits_with_its_number(db):
    long = "A" * 120 + " " + "B" * 120
    _user(db, queries.username_from_name(db, long))

    made = queries.username_from_name(db, long)
    assert queries.username_error(made) is None
    assert made.endswith("2")


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


def _accept(db, **body):
    queries.create_invite(db, token_hash=tokens.digest(TOKEN), ttl=timedelta(days=1))
    return accept_invite(
        AcceptBody(token=TOKEN, password="una-contraseña-larga", **body), _request(), Response(), session=db
    )


def test_a_registration_with_a_name_alone_signs_in_with_the_name_made_username(db):
    _user(db, "ana.perez")

    me = _accept(db, name="Ana Pérez")

    assert me["user"]["username"] == "ana.perez2"
    assert me["user"]["name"] == "Ana Pérez"


def test_a_registration_with_no_name_and_no_username_is_refused(db):
    with pytest.raises(HTTPException) as refused:
        _accept(db, name="   ")

    assert refused.value.status_code == 422

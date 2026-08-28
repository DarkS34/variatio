"""Whether the installation can deliver mail, said once and on the session payload.

The optional address on «Mi perfil» has exactly one use — receiving the password-reset
link — and with no SMTP configured `mail.send` writes that link to the log and the API
hands it back in the response instead. A field promising a delivery that cannot happen is
worse than no field, so the client hides it; what it needs in order to decide is this
boolean, and it travels on `/api/auth/me` because that is the query every screen already
reads and the only one that exists before a workspace does.

It is an INSTALLATION fact and not a property of the account, which is why it sits beside
`active_workspace` and not inside `user`.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server import settings
from server.auth import mail
from server.db import identity
from server.db.models import Base
from server.routers.auth import _me


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(identity, "now", datetime.now)
    yield session
    session.close()


@pytest.fixture
def user(db):
    return identity.create_user(db, username="ana", name="Ana", password_hash="x")


def test_no_smtp_is_reported_as_no_mail(db, user, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", lambda: "")
    assert _me(db, user)["mail_configured"] is False


def test_a_configured_host_is_reported(db, user, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", lambda: "smtp.example.org")
    assert _me(db, user)["mail_configured"] is True


def test_it_is_an_installation_fact_and_not_the_account_s(db, user, monkeypatch):
    """The client hides a FIELD with it; putting it on `user` would invite the opposite
    reading — that this account has mail — which is never what it means."""
    monkeypatch.setattr(settings, "smtp_host", lambda: "smtp.example.org")
    payload = _me(db, user)
    assert "mail_configured" not in payload["user"]


def test_the_flag_is_the_one_mail_itself_reads(db, user, monkeypatch):
    """Two readings of «is there mail here?» that could disagree would put the field on
    screen exactly where `send` then refuses to deliver, so the payload asks
    `mail.configured` rather than testing the setting a second time of its own."""
    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(settings, "smtp_host", lambda: "")
    assert _me(db, user)["mail_configured"] is True


def test_a_host_of_whitespace_is_no_host(monkeypatch):
    """`.env` files carry trailing spaces, and a host of blanks would put the field back
    on screen while every send failed."""
    monkeypatch.setenv("SMTP_HOST", "   ")
    assert mail.configured() is False

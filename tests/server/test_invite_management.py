"""Everything the administrator controls about an invitation, before and after handing it over.

Four things were asked for (2026-09-16): choosing when a new one expires, pasting back the
link of one deleted by mistake, reading its link and moving its date once it exists, and an
alias only the panel reads — plus minting several at once. What holds them together is
that the LINK stays the invitation: the token is still looked up by digest, the copy the
panel reads back is sealed with a key the database does not hold, and a link serves once
whatever is done to its row.
"""

import json
import stat
from argparse import Namespace
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from server import installation
from server.auth import links, passwords, rate_limit, tokens
from server.auth.rate_limit import RateLimiter
from server.db import identity, repository
from server.db.models import Base, Invite
from server.routers import admin as admin_routes
from server.routers.admin import InviteBody, InviteEditBody, InviteImportBody
from server.routers.auth import AcceptBody, accept_invite, preview_invite

IP = "10.0.0.2"


def _utc_now() -> datetime:
    """The clock SQLite can compare: UTC, with the offset it would drop anyway."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ahead(**delta) -> datetime:
    """A moment still to come, as the browser sends it: with its zone."""
    return datetime.now(timezone.utc) + timedelta(**delta)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    monkeypatch.setattr(identity, "now", _utc_now)
    monkeypatch.setattr(passwords, "hash_password", lambda password: "hashed")
    yield session
    session.close()


@pytest.fixture
def admin(db):
    return identity.create_user(
        db, username="admin", name="admin", password_hash="x", is_admin=True
    )


@pytest.fixture
def workspace(db):
    return repository.ensure_workspace(db, "enfermeria", "Enfermería")


# The limiter is one object for the whole process, and a batch spends one attempt per link:
# without this, the run itself would trip the `invite` bucket a few files in.
@pytest.fixture(autouse=True)
def forget_the_attempts():
    for bucket in ("invite", "accept"):
        for key in (IP, "admin"):
            rate_limit.limiter.clear(bucket, key)
    yield
    for bucket in ("invite", "accept"):
        for key in (IP, "admin"):
            rate_limit.limiter.clear(bucket, key)


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


def _create(db, admin, **terms) -> dict:
    return admin_routes.create_invite(InviteBody(**terms), _request(), admin=admin, db=db)


def _import(db, admin, link: str, **terms) -> dict:
    return admin_routes.import_invite(
        InviteImportBody(link=link, **terms), _request(), admin=admin, db=db
    )


def _read_link(db, admin, invite_id: int) -> str:
    return admin_routes.invite_link(invite_id, _request(), admin=admin, db=db)["link"]


def _edit(db, admin, invite_id: int, **changes) -> dict:
    return admin_routes.edit_invite(invite_id, InviteEditBody(**changes), admin=admin, db=db)


def _token(link: str) -> str:
    return link.split("token=")[1]


def _redeem(db, link: str, username: str = "ana"):
    accept_invite(
        AcceptBody(
            token=_token(link),
            username=username,
            name=username,
            password="una-contraseña-larga",
        ),
        _request(),
        Response(),
        session=db,
    )
    # The claim is a bare UPDATE, so this session's copy of the row is stale; every request
    # in production opens a session of its own and never sees it.
    db.expire_all()
    return identity.get_user(db, username)


def _legacy(db, **terms) -> tuple[Invite, str]:
    """An invitation as every one minted before this change: a digest and nothing else."""
    token = tokens.new_token()
    invite = identity.create_invite(
        db, token_hash=tokens.digest(token), ttl=timedelta(days=1), **terms
    )
    return invite, token


# THE SEALED COPY -------------------------------------------------------------------------


def test_a_sealed_link_opens_again_and_only_for_its_own_row():
    token = tokens.new_token()
    sealed = links.seal(token)

    assert sealed and token not in sealed
    assert links.unseal(sealed, tokens.digest(token)) == token
    # A ciphertext moved onto another row is not that row's link.
    assert links.unseal(sealed, tokens.digest(tokens.new_token())) is None
    assert links.unseal(None, tokens.digest(token)) is None


def test_the_key_file_is_made_by_the_first_seal_and_only_its_owner_reads_it():
    path = links.key_path()
    token = tokens.new_token()

    # Opening never creates: with no key there is nothing to open with.
    assert links.unseal("gAAAA-no-es-nada", tokens.digest(token)) is None
    assert not path.exists()

    sealed = links.seal(token)
    assert path.exists()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    key = path.read_text()

    links.seal(tokens.new_token())
    assert path.read_text() == key
    assert links.unseal(sealed, tokens.digest(token)) == token


def test_the_environment_key_wins_and_a_lost_key_leaves_nothing_to_show(monkeypatch):
    token = tokens.new_token()
    with_file = links.seal(token)

    monkeypatch.setenv(links.KEY_ENV, Fernet.generate_key().decode())
    assert links.unseal(with_file, tokens.digest(token)) is None
    with_env = links.seal(token)
    assert links.unseal(with_env, tokens.digest(token)) == token

    monkeypatch.setenv(links.KEY_ENV, "no-es-una-clave")
    assert links.seal(token) is None


def test_the_token_is_read_out_of_whatever_was_pasted():
    token = tokens.new_token()
    for pasted in (
        f"https://variatio.app/invite?token={token}",
        f"http://127.0.0.1:5173/invite?token={token}&utm=x",
        f"  {token}\n",
        f"token={token}",
        f"Aquí tienes tu enlace: https://variatio.app/invite?token={token}",
    ):
        assert links.token_from(pasted) == token


@pytest.mark.parametrize(
    "pasted",
    ["hola", "https://variatio.app/invite?token=corto", "a" * 43, "ab" * 21 + "a", "á" * 43],
)
def test_what_this_system_did_not_mint_is_refused_before_anything_is_looked_up(
    db, admin, pasted
):
    with pytest.raises(HTTPException) as refused:
        _import(db, admin, pasted)

    assert refused.value.status_code == 422
    assert db.query(Invite).count() == 0


# CHOOSING THE TERMS ----------------------------------------------------------------------


def test_the_chosen_expiry_is_kept_and_has_no_upper_bound(db, admin):
    far = datetime(2031, 1, 1, 9, 30, tzinfo=timezone.utc)

    created = _create(db, admin, expires_at=far)

    row = db.get(Invite, created["invite"]["id"])
    assert row.expires_at == far.replace(tzinfo=None)
    assert created["invite"]["state"] == "pending"
    assert created["invites"][0]["stored"] is True


def test_without_a_date_an_invitation_lasts_the_default_week(db, admin):
    created = _create(db, admin)

    row = db.get(Invite, created["invite"]["id"])
    assert abs(row.expires_at - (_utc_now() + installation.INVITE_TTL)) < timedelta(minutes=1)


def test_a_date_already_past_is_refused(db, admin):
    with pytest.raises(HTTPException) as refused:
        _create(db, admin, expires_at=_ahead(minutes=-1))

    assert refused.value.status_code == 422
    assert db.query(Invite).count() == 0


def test_the_alias_is_kept_and_never_reaches_whoever_holds_the_link(db, admin, workspace):
    created = _create(db, admin, workspace="enfermeria", label="  Profesora   de Enfermería ")

    assert created["invite"]["label"] == "Profesora de Enfermería"
    preview = preview_invite(_token(created["link"]), session=db)
    assert "label" not in preview
    assert "Profesora" not in json.dumps(preview, ensure_ascii=False)
    assert preview["workspace"] == "Enfermería"


def test_the_listing_never_carries_a_link_sealed_or_not(db, admin):
    created = _create(db, admin, label="Ana")

    listing = json.dumps(admin_routes.invites(db=db))

    assert _token(created["link"]) not in listing
    assert db.get(Invite, created["invite"]["id"]).token_sealed not in listing
    assert '"link_stored": true' in listing


def test_an_alias_that_does_not_fit_is_refused(db, admin):
    with pytest.raises(HTTPException) as refused:
        _create(db, admin, label="x" * (identity.INVITE_LABEL_MAX + 1))

    assert refused.value.status_code == 422


# SEVERAL AT ONCE -------------------------------------------------------------------------


def test_a_batch_numbers_its_aliases_and_carries_on_where_the_last_one_stopped(db, admin):
    first = _create(db, admin, label="Alumno", count=3)

    assert [m["invite"]["label"] for m in first["invites"]] == [
        "Alumno 1",
        "Alumno 2",
        "Alumno 3",
    ]
    assert len({m["link"] for m in first["invites"]}) == 3
    assert first["link"] == first["invites"][0]["link"]

    # A used one still holds its number: a second batch never repeats a name.
    _redeem(db, first["invites"][2]["link"])
    second = _create(db, admin, label="Alumno", count=2)
    assert [m["invite"]["label"] for m in second["invites"]] == ["Alumno 4", "Alumno 5"]


def test_one_invitation_keeps_its_alias_as_written_and_a_batch_without_one_stays_unnamed(
    db, admin
):
    assert _create(db, admin, label="Alumno")["invite"]["label"] == "Alumno"
    batch = _create(db, admin, count=2)
    assert [m["invite"]["label"] for m in batch["invites"]] == [None, None]


@pytest.mark.parametrize("count", [0, installation.INVITE_BATCH_MAX + 1])
def test_a_batch_is_bounded(db, admin, count):
    with pytest.raises(HTTPException) as refused:
        _create(db, admin, count=count)

    assert refused.value.status_code == 422
    assert db.query(Invite).count() == 0


def test_a_batch_pays_the_throttle_link_by_link(db, admin, monkeypatch):
    monkeypatch.setitem(installation.RATE_LIMITS, "invite", (5, 3600.0))

    _create(db, admin, count=5)
    with pytest.raises(HTTPException) as refused:
        _create(db, admin)

    assert refused.value.status_code == 429


def test_the_limiter_charges_a_cost_and_waits_for_room_for_all_of_it():
    limiter = RateLimiter()
    assert limiter.check("invite", "admin", limit=5, window=60.0, cost=3) == 0.0
    assert limiter.check("invite", "admin", limit=5, window=60.0, cost=3) > 0.0
    assert limiter.check("invite", "admin", limit=5, window=60.0, cost=2) == 0.0
    assert limiter.check("invite", "admin", limit=5, window=60.0) > 0.0
    # More than the whole window holds never fits, whatever is waited.
    assert limiter.check("invite", "otra", limit=5, window=60.0, cost=6) == 60.0


def test_the_ordering_puts_the_newest_batch_first_and_keeps_each_batch_in_order(db, admin):
    older = _create(db, admin, label="Viejo", count=2)
    newer = _create(db, admin, label="Nuevo", count=2)
    for minted, when in ((older, datetime(2026, 1, 1)), (newer, datetime(2026, 2, 1))):
        for item in minted["invites"]:
            db.get(Invite, item["invite"]["id"]).created_at = when
    db.flush()

    labels = [row["label"] for row in admin_routes.invites(db=db)["invites"]]

    assert labels == ["Nuevo 1", "Nuevo 2", "Viejo 1", "Viejo 2"]


# READING THE LINK AGAIN ------------------------------------------------------------------


def test_the_link_read_again_is_the_one_handed_over(db, admin):
    created = _create(db, admin)

    assert _read_link(db, admin, created["invite"]["id"]) == created["link"]


def test_an_invitation_minted_before_links_were_kept_says_so(db, admin):
    legacy, _ = _legacy(db)

    listed = admin_routes.invites(db=db)["invites"]
    assert listed[0]["link_stored"] is False
    with pytest.raises(HTTPException) as refused:
        _read_link(db, admin, legacy.id)
    assert refused.value.status_code == 409


def test_a_link_whose_key_is_gone_is_refused_and_still_works(db, admin, monkeypatch):
    created = _create(db, admin)
    monkeypatch.setenv(links.KEY_ENV, Fernet.generate_key().decode())

    with pytest.raises(HTTPException) as refused:
        _read_link(db, admin, created["invite"]["id"])

    assert refused.value.status_code == 409
    assert "clave" in refused.value.detail
    assert _redeem(db, created["link"]) is not None


# PASTING A LINK BACK ---------------------------------------------------------------------


def test_the_link_of_a_deleted_invitation_comes_back_under_the_terms_given(
    db, admin, workspace
):
    created = _create(db, admin)
    admin_routes.revoke_invite(created["invite"]["id"], admin=admin, db=db)
    with pytest.raises(HTTPException):
        preview_invite(_token(created["link"]), session=db)

    pasted = f"https://antes.variatio.app/invite?token={_token(created['link'])}"
    revived = _import(
        db, admin, pasted, workspace="enfermeria", role="viewer", label="Recuperada",
        expires_at=_ahead(days=2),
    )

    assert revived["outcome"] == "created"
    assert revived["link"] == created["link"]
    assert revived["invite"]["label"] == "Recuperada"
    assert _read_link(db, admin, revived["invite"]["id"]) == created["link"]
    user = _redeem(db, created["link"])
    assert [(w.slug, m.role) for m, w in identity.memberships_for(db, user.id)] == [
        ("enfermeria", "viewer")
    ]


def test_pasting_the_link_of_a_legacy_invitation_only_makes_it_showable(
    db, admin, workspace
):
    legacy, token = _legacy(db, role="viewer")

    result = _import(
        db, admin, f"http://localhost/invite?token={token}", workspace="enfermeria",
        role="owner", label="Otra cosa",
    )

    assert result["outcome"] == "recovered"
    row = db.get(Invite, legacy.id)
    assert (row.role, row.workspace_id, row.label) == ("viewer", None, None)
    assert _token(_read_link(db, admin, legacy.id)) == token
    assert _import(db, admin, token)["outcome"] == "unchanged"
    assert db.query(Invite).count() == 1


def test_pasting_a_link_already_used_is_refused(db, admin):
    created = _create(db, admin)
    _redeem(db, created["link"])

    with pytest.raises(HTTPException) as refused:
        _import(db, admin, created["link"])

    assert refused.value.status_code == 409
    assert db.query(Invite).count() == 1


# CHANGING THE TERMS ----------------------------------------------------------------------


def test_moving_the_date_brings_an_expired_invitation_back(db, admin):
    created = _create(db, admin)
    invite_id, digest = created["invite"]["id"], tokens.digest(_token(created["link"]))
    db.get(Invite, invite_id).expires_at = _utc_now() - timedelta(hours=1)
    db.flush()

    assert identity.live_invite(db, digest) is None
    assert admin_routes.invites(db=db)["invites"][0]["state"] == "expired"
    # An expired link is still worth reading: it is about to be sent again.
    assert _read_link(db, admin, invite_id) == created["link"]

    edited = _edit(db, admin, invite_id, expires_at=_ahead(days=3))

    assert edited["invite"]["state"] == "pending"
    assert identity.live_invite(db, digest) is not None


def test_an_edit_changes_only_what_it_sends(db, admin, workspace):
    created = _create(db, admin, workspace="enfermeria", role="owner", label="A")
    invite_id = created["invite"]["id"]

    renamed = _edit(db, admin, invite_id, label="B")["invite"]
    assert (renamed["label"], renamed["workspace_slug"], renamed["role"]) == (
        "B",
        "enfermeria",
        "owner",
    )

    # `null` sent is «ninguna», not «sin cambios».
    unbound = _edit(db, admin, invite_id, workspace=None)["invite"]
    assert unbound["workspace_slug"] is None and unbound["label"] == "B"

    rebound = _edit(db, admin, invite_id, workspace="enfermeria", role="viewer")["invite"]
    preview = preview_invite(_token(created["link"]), session=db)
    assert (preview["workspace"], preview["role"]) == ("Enfermería", "viewer")
    assert rebound["label"] == "B"

    cleared = _edit(db, admin, invite_id, label="   ")["invite"]
    assert cleared["label"] is None


@pytest.mark.parametrize(
    "changes, status",
    [
        ({"expires_at": None}, 422),
        ({"role": "rey"}, 422),
        ({"workspace": "no-existe"}, 404),
    ],
)
def test_an_edit_refuses_what_an_invitation_cannot_be(db, admin, changes, status):
    created = _create(db, admin)

    with pytest.raises(HTTPException) as refused:
        _edit(db, admin, created["invite"]["id"], **changes)

    assert refused.value.status_code == status


def test_an_edit_refuses_a_date_already_past(db, admin):
    created = _create(db, admin)

    with pytest.raises(HTTPException) as refused:
        _edit(db, admin, created["invite"]["id"], expires_at=_ahead(seconds=-5))

    assert refused.value.status_code == 422


# ONCE USED -------------------------------------------------------------------------------


def test_redeeming_forgets_the_sealed_copy_and_closes_the_row(db, admin):
    created = _create(db, admin, label="Ana")
    invite_id = created["invite"]["id"]

    _redeem(db, created["link"])

    row = db.get(Invite, invite_id)
    assert row.token_sealed is None and row.label == "Ana"
    assert admin_routes.invites(db=db)["invites"] == []
    for attempt in (
        lambda: _read_link(db, admin, invite_id),
        lambda: _edit(db, admin, invite_id, expires_at=_ahead(days=1)),
    ):
        with pytest.raises(HTTPException) as refused:
            attempt()
        assert refused.value.status_code == 409


def test_a_claim_refuses_an_invitation_whose_date_moved_into_the_past(db):
    invite, token = _legacy(db)
    read = identity.live_invite(db, tokens.digest(token))
    invite.expires_at = _utc_now() - timedelta(seconds=1)
    db.flush()

    assert identity.claim_invite(db, read) is False


# THE COMMAND LINE ------------------------------------------------------------------------


def test_the_command_line_mints_a_numbered_batch_with_its_alias(capsys, monkeypatch):
    from server.cli import accounts
    from server.db import session as db_session

    Base.metadata.create_all(db_session.engine())
    monkeypatch.setattr(installation, "public_base_url", lambda: "https://variatio.app")

    code = accounts.invite(
        Namespace(workspace="", role="editor", alias="Clase", days=3, count=2)
    )

    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    assert lines[0].startswith("Clase 1\thttps://variatio.app/invite?token=")
    assert lines[1].startswith("Clase 2\thttps://variatio.app/invite?token=")
    with db_session.session_scope() as session:
        rows = session.query(Invite).order_by(Invite.id).all()
        assert [row.label for row in rows] == ["Clase 1", "Clase 2"]
        assert all(row.token_sealed for row in rows)

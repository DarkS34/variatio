"""Login, your own account, and password recovery.

THERE IS NO REGISTRATION ENDPOINT HERE AND THERE MUST NEVER BE ONE. An account exists
because somebody redeemed a single-use invitation, or because the installation's first
account was created from the command line. That is what removes the largest attack
surface a web login has, and with it the captcha and the anti-spam quotas.

«DOES THIS USERNAME HAVE AN ACCOUNT?» IS REFUSED IN THREE PLACES AT ONCE, and weakening
any one of them re-opens enumeration on its own: `/login` answers the same sentence for a
wrong password and a missing account, the missing-account path pays for a decoy Argon2
hash so the two also take the same time, and `/forgot` always answers 202.

Authorisation is per route rather than on the router: `/login`, `/forgot`, `/reset` and
the two halves of an invitation are reached without an account and cannot live behind
one, while everything else depends on `deps.current_user`. Handing out invitations and
moving people between workspaces is not here at all — that is `routers/admin.py`, behind
`require_admin`. What is left is what an account does to itself.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from .. import settings
from ..auth import deps, mail, passwords, tokens
from ..auth.rate_limit import forgive, throttle
from ..db import identity
from ..db.models import OWNER, Invite, User, Workspace

router = APIRouter(prefix="/api/auth", tags=["auth"])

# The same sentence for «no such account» and «wrong password». Either half alone still
# answers «does this name have an account here?».
BAD_CREDENTIALS = "Usuario o contraseña incorrectos."


# Deliberately not `EmailStr`: an address here is a delivery detail, never an identity and
# never a login, so the only thing worth refusing is what cannot be a mailbox at all.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+\.[^@\s]+$")


class Credentials(BaseModel):
    """A username and a password, as the login form sends them."""

    username: str
    password: str


class ProfileBody(BaseModel):
    """The two things about an account that are its own to change."""

    name: str = Field(max_length=200)
    email: str | None = None


class AcceptBody(BaseModel):
    """An invitation being redeemed: the link, and who the holder says they are."""

    token: str
    username: str
    name: str = ""
    password: str
    evaluator_profile: str | None = None
    # Absent is allowed here and nowhere else: a browser that never asked can still register,
    # and the form seeds this from `navigator.language`. `create_user` resolves it.
    ui_language: str | None = None


class LanguageBody(BaseModel):
    """The language the interface is to be drawn in."""

    language: str


class PasswordBody(BaseModel):
    """The password in force and the one replacing it."""

    current: str
    next: str = Field(alias="new")

    model_config = {"populate_by_name": True}


class ForgotBody(BaseModel):
    """Whose password is being recovered."""

    username: str


class ResetBody(BaseModel):
    """A reset link's token and the password replacing the old one."""

    token: str
    password: str


# SESSION ---------------------------------------------------------------------------


@router.post("/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    session: DbSession = Depends(deps.db),
) -> dict:
    """Take a session cookie, answering identically whether the account exists or not.

    The decoy hash is not defensive tidiness: without it the missing-account path returns
    in microseconds and the wrong-password one in ~200 ms, which answers the question the
    shared sentence exists to refuse.
    """
    username = identity.normalise_username(body.username)
    throttle("login", request, username)

    user = identity.get_user(session, username)
    if user is None or not user.active:
        passwords.waste_time()
        raise HTTPException(401, BAD_CREDENTIALS)
    if not passwords.verify_password(user.password_hash, body.password):
        raise HTTPException(401, BAD_CREDENTIALS)

    # The Argon2 parameters live inside the hash, so raising them upgrades every account
    # one login at a time, with no migration.
    if passwords.needs_rehash(user.password_hash):
        identity.set_password(session, user, passwords.hash_password(body.password))

    forgive("login", username)
    _issue_session(session, user, request, response)
    return _me(session, user)


@router.post("/logout")
def logout(request: Request, response: Response, session: DbSession = Depends(deps.db)) -> dict:
    """Revoke this session and clear its cookie."""
    found = deps.resolve(session, deps.session_token(request))
    if found is not None:
        identity.revoke_session(session, found[0])
    _clear_cookie(response)
    return {"ok": True}


@router.post("/logout-all")
def logout_all(
    request: Request,
    response: Response,
    user: User = Depends(deps.current_user),
    session: DbSession = Depends(deps.db),
) -> dict:
    """Revoke every session of this account, on every device."""
    revoked = identity.revoke_all_sessions(session, user.id)
    _clear_cookie(response)
    return {"ok": True, "revoked": revoked}


@router.get("/me")
def me(user: User = Depends(deps.current_user), session: DbSession = Depends(deps.db)) -> dict:
    """Answer who is logged in, where they land and what the installation can do."""
    return _me(session, user)


@router.patch("/me")
def update_me(
    body: ProfileBody,
    user: User = Depends(deps.current_user),
    session: DbSession = Depends(deps.db),
) -> dict:
    """Change this account's display name and optional address.

    The username is deliberately not among them: it is the identity every other row points
    at by id and every message prints, so renaming it would rewrite who wrote what.
    Changing the address un-verifies it — what was proven was control of the previous
    mailbox and of nothing else.
    """
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "El nombre no puede quedar vacío.")

    email = identity.normalise_email(body.email) if body.email else None
    if email:
        if not EMAIL_PATTERN.fullmatch(email):
            raise HTTPException(422, "Eso no parece una dirección de correo.")
        other = identity.get_user_by_email(session, email)
        if other is not None and other.id != user.id:
            raise HTTPException(409, "Ese correo ya está en otra cuenta.")

    if email != user.email:
        user.email_verified_at = None
    user.name = name
    user.email = email
    session.flush()
    return _me(session, user)


# There is deliberately no route listing this account's open sessions. In a closed group
# with hand-issued accounts the list has no reader, and a password change already revokes
# every other session in the same transaction.


# LANGUAGE --------------------------------------------------------------------------


@router.post("/language")
def change_language(
    body: LanguageBody,
    user: User = Depends(deps.current_user),
    session: DbSession = Depends(deps.db),
) -> dict:
    """Set the language this account reads the interface in, and nothing else.

    The account's own and only the account's: an administrator corrects an evaluator
    profile because it is a variable of the evaluation, but what somebody reads the interface
    in is nobody else's decision. It touches no workspace — what a person reads and what
    an instance's prompts are written in are separate axes.
    """
    error = identity.language_error(body.language)
    if error:
        raise HTTPException(422, error)
    identity.set_ui_language(session, user, body.language)
    return {"ui_language": user.ui_language}


# PASSWORD --------------------------------------------------------------------------


@router.post("/password")
def change_password(
    body: PasswordBody,
    request: Request,
    response: Response,
    user: User = Depends(deps.current_user),
    session: DbSession = Depends(deps.db),
) -> dict:
    """Change this account's password, revoking every other session as it goes."""
    throttle("password", request, user.username)
    if not passwords.verify_password(user.password_hash, body.current):
        raise HTTPException(403, "La contraseña actual no es correcta.")

    error = passwords.policy_error(body.next, account=user.username, name=user.name)
    if error:
        raise HTTPException(422, error)

    identity.set_password(session, user, passwords.hash_password(body.next))
    # This session gets a brand-new identifier too: if the change was prompted by a
    # suspicion, leaving the old one usable defeats it.
    identity.revoke_all_sessions(session, user.id)
    _issue_session(session, user, request, response)
    return {"ok": True}


@router.post("/forgot", status_code=202)
def forgot(body: ForgotBody, request: Request, session: DbSession = Depends(deps.db)) -> dict:
    """Issue a reset link, answering 202 whether or not the account exists.

    This is the easiest place in the API to enumerate accounts, so the answer must not
    depend on what was found. With no address on the account — the normal case here — the
    link goes to the log, where whoever administers the installation is already looking.
    """
    username = identity.normalise_username(body.username)
    throttle("forgot", request, username)

    user = identity.get_user(session, username)
    if user is not None and user.active:
        token = tokens.new_token()
        identity.create_reset(session, user.id, tokens.digest(token), settings.RESET_TTL)
        link = f"{deps.base_url(request)}/reset?token={token}"
        minutes = int(settings.RESET_TTL.total_seconds() // 60)
        if user.email:
            mail.send(
                user.email,
                "Restablece tu contraseña",
                "Has pedido restablecer tu contraseña de Variatio.\n\n"
                f"Abre este enlace en menos de {minutes} minutos:\n{link}\n\n"
                "Si no has sido tú, ignora este mensaje: la contraseña actual sigue valiendo.",
            )
        else:
            logger.info(
                f"Restablecimiento pedido por «{user.username}», sin correo en la cuenta. "
                f"Enlace válido {minutes} min: {link}"
            )

    return {"sent": True}


@router.post("/reset")
def reset(
    body: ResetBody,
    request: Request,
    response: Response,
    session: DbSession = Depends(deps.db),
) -> dict:
    """Spend a reset link, set the password and log the account straight in."""
    throttle("reset", request, "")
    row = identity.live_reset(session, tokens.digest(body.token))
    if row is None:
        raise HTTPException(404, "Ese enlace ya no vale. Pide otro.")

    user = identity.get_user_by_id(session, row.user_id)
    if user is None or not user.active:
        raise HTTPException(404, "Ese enlace ya no vale. Pide otro.")

    error = passwords.policy_error(body.password, account=user.username, name=user.name)
    if error:
        raise HTTPException(422, error)

    identity.set_password(session, user, passwords.hash_password(body.password))
    identity.consume_reset(session, row)
    identity.revoke_all_sessions(session, user.id)
    # A link that arrived by mail proves control of that mailbox; one handed over by the
    # administrator proves nothing about an address, so only the first case verifies one.
    if user.email and user.email_verified_at is None:
        user.email_verified_at = identity.now()
    _issue_session(session, user, request, response)
    return _me(session, user)


# INVITATIONS -----------------------------------------------------------------------


@router.get("/invites/{token}")
def preview_invite(token: str, session: DbSession = Depends(deps.db)) -> dict:
    """Answer what an invitation grants, so its holder sees it before registering."""
    invite = identity.live_invite(session, tokens.digest(token))
    if invite is None:
        raise HTTPException(404, "Esa invitación no existe, ya se usó o ha caducado.")
    workspace = invite.workspace
    return {
        "role": invite.role,
        "workspace": workspace.name if workspace else None,
        "expires_at": invite.expires_at.isoformat(),
    }


@router.post("/accept")
def accept_invite(
    body: AcceptBody,
    request: Request,
    response: Response,
    session: DbSession = Depends(deps.db),
) -> dict:
    """Redeem an invitation, creating the account it grants and logging it in.

    The order of the guards below is load-bearing. Throttling is keyed on the INVITATION
    and not on the username, because the name is what an attacker varies to read the 409
    off a link they got hold of. The invitation is CLAIMED before the ~200 ms of Argon2,
    because `live_invite` is a read and two people redeeming the same link both raced
    through it and both got an account.

    A username already taken is refused outright: an invitation is not a way to set
    somebody else's credentials. An evaluator profile is required here and required
    nowhere else — this is the one moment the person is in front of the form, and NULL
    («nobody said») has to stay reachable for the accounts the command line creates and
    for every account older than the question. It is not a permission and never becomes
    one. An unknown UI language, unlike an absent profile, is refused rather than ignored:
    the account reads everything through it, so silently seating somebody in Spanish
    because they typed `fr` is worse than saying the installation does not speak it.
    """
    token_hash = tokens.digest(body.token)
    throttle("accept", request, token_hash)

    invite = identity.live_invite(session, token_hash)
    if invite is None:
        raise HTTPException(404, "Esa invitación no existe, ya se usó o ha caducado.")

    # Losing the claim is the same answer as a spent invitation.
    if not identity.claim_invite(session, invite):
        raise HTTPException(404, "Esa invitación no existe, ya se usó o ha caducado.")

    username = identity.normalise_username(body.username)
    error = identity.username_error(username)
    if error:
        raise HTTPException(422, error)

    if identity.get_user(session, username) is not None:
        raise HTTPException(409, f"El usuario «{username}» ya está cogido. Elige otro.")

    error = passwords.policy_error(body.password, account=username, name=body.name)
    if error:
        raise HTTPException(422, error)

    error = identity.profile_error(body.evaluator_profile)
    if error:
        raise HTTPException(422, error)
    if body.evaluator_profile is None:
        raise HTTPException(422, "Di si das clase o si estudias: decide qué se te preguntará.")

    if body.ui_language is not None:
        error = identity.language_error(body.ui_language)
        if error:
            raise HTTPException(422, error)

    user = identity.create_user(
        session,
        username=username,
        name=body.name.strip() or username,
        password_hash=passwords.hash_password(body.password),
        evaluator_profile=body.evaluator_profile,
        ui_language=body.ui_language,
    )
    _apply_membership(session, invite, user)
    identity.attribute_invite(session, invite, user.id)
    _issue_session(session, user, request, response)
    return _me(session, user)


# HELPERS ---------------------------------------------------------------------------


def _me(session: DbSession, user: User) -> dict:
    """Render the session query every screen is built on.

    `active` is the workspace this account lands in, which the browser then repeats back
    on every request as `X-Workspace`, and `role` is the role THERE, so the UI knows what
    to offer before it has asked for anything.
    """
    rows = identity.memberships_for(session, user.id)
    current = deps.current_workspace_for(session, user)
    active = current.slug if current else None
    mine = {w.id: m.role for m, w in rows}

    workspaces = [
        {"slug": w.slug, "name": w.name, "role": m.role, "active": w.slug == active}
        for m, w in rows
    ]
    if current is not None and current.id not in mine:
        # An administrator whose last choice was somebody else's instance still lands
        # there, and the switcher has to list it or the app opens on a workspace it does
        # not show. Nothing PICKS a workspace for an account that belongs to none.
        workspaces.append(
            {"slug": current.slug, "name": current.name, "role": OWNER, "active": True}
        )

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin,
            # The evaluation screen asks a teacher and a student different things, and it
            # has to know which before it draws the first card.
            "evaluator_profile": user.evaluator_profile,
            # Travels here rather than on a screen of its own because every screen needs
            # it before the first render, the same reason `active_workspace` does.
            "ui_language": user.ui_language,
        },
        "workspaces": workspaces,
        "active_workspace": active,
        # AN INSTALLATION FACT, deliberately outside `user`. It stops «Mi perfil» offering
        # an address when nothing could ever deliver to it: with no SMTP the reset link is
        # logged and handed back in the response. Behind a session anyway, because the
        # public half of that flow must answer identically whatever is configured.
        "mail_configured": mail.configured(),
        # Matches what `access_for` will decide on the next request, administrator bypass
        # included: a `null` here is what makes the panel offer «crea tu workspace», so it
        # must not say that to somebody every route is about to let through.
        "role": _role_here(user, current, mine),
    }


def _role_here(user: User, current: Workspace | None, mine: dict[int, str]) -> str | None:
    """Say what this account may do where it lands, administrator bypass included."""
    if current is None:
        return None
    return mine.get(current.id) or (OWNER if user.is_admin else None)


def _issue_session(session: DbSession, user: User, request: Request, response: Response) -> None:
    """Mint a fresh opaque session and set its cookie.

    The identifier rotates on login and on password change: a sliding session that never
    rotates renews a stolen cookie for ever.
    """
    token = tokens.new_token()
    identity.create_session(
        session,
        user_id=user.id,
        token_hash=tokens.digest(token),
        sliding=settings.SESSION_SLIDING,
        absolute=settings.SESSION_ABSOLUTE,
        ip=deps.client_ip(request) or None,
        user_agent=request.headers.get("user-agent"),
    )
    response.set_cookie(
        settings.session_cookie(),
        token,
        max_age=int(settings.SESSION_ABSOLUTE.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure(),
        samesite="lax",
        path="/",
    )


def _clear_cookie(response: Response) -> None:
    """Delete the session cookie with the same attributes it was set with.

    `Secure` included: a `Set-Cookie` that does not meet the `__Host-` rules is discarded
    whole by the browser, so a logout written without them leaves the cookie in the jar.
    """
    response.delete_cookie(
        settings.session_cookie(),
        path="/",
        httponly=True,
        secure=settings.cookie_secure(),
        samesite="lax",
    )


def _apply_membership(session: DbSession, invite: Invite, user: User) -> None:
    """Grant the membership an invitation carried, if it carried one at all."""
    if invite.workspace_id is None:
        return
    identity.grant(session, invite.workspace_id, user.id, invite.role)

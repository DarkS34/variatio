"""Login, invitations, membership and password recovery.

There is no open registration endpoint anywhere in here on purpose: an account exists
because someone issued a single-use invitation, or because the installation's first
account was created from the command line. That is what removes the largest attack
surface a web login has, and with it the captcha and the anti-spam quotas.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from .. import settings
from ..auth import deps, mail, passwords, tokens
from ..auth.rate_limit import limiter
from ..db import identity
from ..db.models import EDITOR, OWNER, ROLES, VIEWER, Invite, User, Workspace

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Deliberately the same sentence for "no such account" and "wrong password", and the
# failing path pays for a decoy hash so that the two also take the same time. Either
# half alone still answers "does this name have an account here?".
BAD_CREDENTIALS = "Usuario o contraseña incorrectos."


class Credentials(BaseModel):
    username: str
    password: str


class InviteBody(BaseModel):
    role: str = EDITOR
    workspace: bool = True


class AcceptBody(BaseModel):
    token: str
    username: str
    name: str = ""
    password: str


class PasswordBody(BaseModel):
    current: str
    next: str = Field(alias="new")

    model_config = {"populate_by_name": True}


class ForgotBody(BaseModel):
    username: str


class ResetBody(BaseModel):
    token: str
    password: str


class RoleBody(BaseModel):
    role: str


# SESSION ---------------------------------------------------------------------------


@router.post("/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    session: DbSession = Depends(deps.db),
) -> dict:
    username = identity.normalise_username(body.username)
    _throttle("login", request, username)

    user = identity.get_user(session, username)
    if user is None or not user.active:
        passwords.waste_time()
        raise HTTPException(401, BAD_CREDENTIALS)
    if not passwords.verify_password(user.password_hash, body.password):
        raise HTTPException(401, BAD_CREDENTIALS)

    # The parameters live inside the hash, so raising them later upgrades every account
    # silently, one login at a time, with no migration.
    if passwords.needs_rehash(user.password_hash):
        identity.set_password(session, user, passwords.hash_password(body.password))

    limiter.clear("login", username)
    limiter.clear("login", deps.client_ip(request))
    _issue_session(session, user, request, response)
    return _me(session, user)


@router.post("/logout")
def logout(request: Request, response: Response, session: DbSession = Depends(deps.db)) -> dict:
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
    revoked = identity.revoke_all_sessions(session, user.id)
    _clear_cookie(response)
    return {"ok": True, "revoked": revoked}


@router.get("/me")
def me(user: User = Depends(deps.current_user), session: DbSession = Depends(deps.db)) -> dict:
    return _me(session, user)


@router.get("/sessions")
def sessions(
    request: Request,
    user: User = Depends(deps.current_user),
    session: DbSession = Depends(deps.db),
) -> dict:
    current = getattr(request.state, "session_row", None)
    return {
        "sessions": [
            {
                "id": row.id,
                "created_at": row.created_at.isoformat(),
                "last_seen_at": row.last_seen_at.isoformat(),
                "ip": row.ip,
                "user_agent": row.user_agent,
                "current": current is not None and row.id == current.id,
            }
            for row in identity.active_sessions(session, user.id)
        ]
    }


# PASSWORD --------------------------------------------------------------------------


@router.post("/password")
def change_password(
    body: PasswordBody,
    request: Request,
    response: Response,
    user: User = Depends(deps.current_user),
    session: DbSession = Depends(deps.db),
) -> dict:
    _throttle("password", request, user.username)
    if not passwords.verify_password(user.password_hash, body.current):
        raise HTTPException(403, "La contraseña actual no es correcta.")

    error = passwords.policy_error(body.next, account=user.username, name=user.name)
    if error:
        raise HTTPException(422, error)

    identity.set_password(session, user, passwords.hash_password(body.next))
    # Every other device is logged out and this one gets a brand-new identifier: if the
    # change was prompted by a suspicion, leaving the old session usable defeats it.
    identity.revoke_all_sessions(session, user.id)
    _issue_session(session, user, request, response)
    return {"ok": True}


@router.post("/forgot", status_code=202)
def forgot(body: ForgotBody, request: Request, session: DbSession = Depends(deps.db)) -> dict:
    username = identity.normalise_username(body.username)
    _throttle("forgot", request, username)

    user = identity.get_user(session, username)
    if user is not None and user.active:
        token = tokens.new_token()
        identity.create_reset(session, user.id, tokens.digest(token), settings.RESET_TTL)
        link = f"{_base_url(request)}/restablecer?token={token}"
        minutes = int(settings.RESET_TTL.total_seconds() // 60)
        if user.email:
            mail.send(
                user.email,
                "Restablece tu contraseña",
                "Has pedido restablecer la contraseña del generador de variantes.\n\n"
                f"Abre este enlace en menos de {minutes} minutos:\n{link}\n\n"
                "Si no has sido tú, ignora este mensaje: la contraseña actual sigue valiendo.",
            )
        else:
            # No address on the account, which is the normal case here. The link still
            # exists and still expires; the only route to its owner is by hand, so it goes
            # where whoever administers the installation is already looking.
            logger.info(
                f"Restablecimiento pedido por «{user.username}», sin correo en la cuenta. "
                f"Enlace válido {minutes} min: {link}"
            )

    # Always the same answer, whether or not the account exists: this endpoint is the
    # easiest place to enumerate accounts and it must not answer that question.
    return {"sent": True}


@router.post("/reset")
def reset(
    body: ResetBody,
    request: Request,
    response: Response,
    session: DbSession = Depends(deps.db),
) -> dict:
    _throttle("reset", request, "")
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
    invite = identity.live_invite(session, tokens.digest(body.token))
    if invite is None:
        raise HTTPException(404, "Esa invitación no existe, ya se usó o ha caducado.")

    username = identity.normalise_username(body.username)
    error = identity.username_error(username)
    if error:
        raise HTTPException(422, error)

    # An invitation is not a way to set somebody else's credentials, so a name that is
    # already taken is refused outright rather than quietly granting the membership to
    # whoever happens to be holding the link.
    if identity.get_user(session, username) is not None:
        raise HTTPException(409, f"El usuario «{username}» ya está cogido. Elige otro.")

    error = passwords.policy_error(body.password, account=username, name=body.name)
    if error:
        raise HTTPException(422, error)

    user = identity.create_user(
        session,
        username=username,
        name=body.name.strip() or username,
        password_hash=passwords.hash_password(body.password),
    )
    _apply_membership(session, invite, user)
    identity.consume_invite(session, invite, user.id)
    _issue_session(session, user, request, response)
    return _me(session, user)


@router.get("/invites")
def list_invites(
    access: deps.Access = Depends(deps.require_member(OWNER)),
    session: DbSession = Depends(deps.db),
) -> dict:
    return {
        "invites": [
            _invite_view(invite, session)
            for invite in identity.pending_invites(session, access.workspace.id)
        ]
    }


@router.post("/invites", status_code=201)
def create_invite(
    body: InviteBody,
    request: Request,
    access: deps.Access = Depends(deps.require_member(OWNER)),
    session: DbSession = Depends(deps.db),
) -> dict:
    _throttle("invite", request, access.user.username)
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'. Usa uno de {', '.join(ROLES)}.")

    token = tokens.new_token()
    invite = identity.create_invite(
        session,
        token_hash=tokens.digest(token),
        ttl=settings.INVITE_TTL,
        workspace_id=access.workspace.id if body.workspace else None,
        role=body.role,
        created_by=access.user.id,
    )

    # The link IS the invitation: it is single-use, it expires, and whoever issued it hands
    # it over themselves. There is no address to bind it to any more, so the person
    # redeeming it chooses their own username — which is why the link must not be posted
    # anywhere its holder was not meant to be.
    return {"invite": _invite_view(invite, session), "link": f"{_base_url(request)}/invitacion?token={token}"}


@router.delete("/invites/{invite_id}")
def delete_invite(
    invite_id: int,
    access: deps.Access = Depends(deps.require_member(OWNER)),
    session: DbSession = Depends(deps.db),
) -> dict:
    invite = session.get(Invite, invite_id)
    if invite is None or invite.workspace_id != access.workspace.id:
        raise HTTPException(404, "Esa invitación no existe.")
    return {"revoked": identity.revoke_invite(session, invite_id)}


# MEMBERS ---------------------------------------------------------------------------


@router.get("/members")
def members(
    access: deps.Access = Depends(deps.require_member(VIEWER)),
    session: DbSession = Depends(deps.db),
) -> dict:
    return {
        "members": [
            {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "role": membership.role,
                "disabled": not user.active,
            }
            for membership, user in identity.members_of(session, access.workspace.id)
        ],
        "role": access.role,
    }


@router.patch("/members/{user_id}")
def set_role(
    user_id: int,
    body: RoleBody,
    access: deps.Access = Depends(deps.require_member(OWNER)),
    session: DbSession = Depends(deps.db),
) -> dict:
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'.")
    if user_id == access.user.id:
        raise HTTPException(409, "No puedes cambiar tu propio rol.")
    if identity.membership(session, access.workspace.id, user_id) is None:
        raise HTTPException(404, "Esa persona no es miembro de este workspace.")
    identity.grant(session, access.workspace.id, user_id, body.role)
    return {"ok": True}


@router.delete("/members/{user_id}")
def remove_member(
    user_id: int,
    access: deps.Access = Depends(deps.require_member(OWNER)),
    session: DbSession = Depends(deps.db),
) -> dict:
    if user_id == access.user.id:
        raise HTTPException(409, "No puedes quitarte a ti mismo del workspace.")
    identity.revoke_membership(session, access.workspace.id, user_id)
    return {"ok": True}


# HELPERS ---------------------------------------------------------------------------


# `active` is no longer "the workspace this process serves" — there is no such thing since
# phase 3 — but the one this account lands in, which the browser then repeats back on every
# request as `X-Workspace`. `role` is the role *there*, so the UI knows what to offer
# before it has asked for anything.
def _me(session: DbSession, user: User) -> dict:
    rows = identity.memberships_for(session, user.id)
    current = deps.default_workspace_for(session, user)
    active = current.slug if current else None
    mine = {w.id: m.role for m, w in rows}

    workspaces = [
        {"slug": w.slug, "name": w.name, "role": m.role, "active": w.slug == active}
        for m, w in rows
    ]
    if current is not None and current.id not in mine:
        # An administrator with no membership still lands somewhere, and the switcher has
        # to list it or the app would open on a workspace it does not show.
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
        },
        "workspaces": workspaces,
        "active_workspace": active,
        # Matches what `access_for` will decide on the next request, administrator bypass
        # included: a `null` here makes the gate show «todavía no tienes acceso», so it
        # must not say that to someone every route is about to let through.
        "role": _role_here(user, current, mine),
    }


def _role_here(user: User, current: Workspace | None, mine: dict[int, str]) -> str | None:
    if current is None:
        return None
    return mine.get(current.id) or (OWNER if user.is_admin else None)


def _issue_session(session: DbSession, user: User, request: Request, response: Response) -> None:
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
        settings.SESSION_COOKIE,
        token,
        max_age=int(settings.SESSION_ABSOLUTE.total_seconds()),
        httponly=True,
        secure=settings.cookie_secure(),
        samesite="lax",
        path="/",
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(settings.SESSION_COOKIE, path="/")


# Where the links in an invitation or a reset mail point. `PUBLIC_BASE_URL` wins; failing
# that the caller's own `Origin`, which is right for development, where the browser is on
# Vite's port and the API's `base_url` would send it to the wrong one. Reading `Origin` is
# safe because a state-changing request only gets here after `OriginCheck` accepted it.
def _base_url(request: Request) -> str:
    configured = settings.public_base_url()
    if configured:
        return configured
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    return str(request.base_url).rstrip("/")


def _apply_membership(session: DbSession, invite: Invite, user: User) -> None:
    if invite.workspace_id is None:
        return
    identity.grant(session, invite.workspace_id, user.id, invite.role)


def _invite_view(invite: Invite, session: DbSession) -> dict:
    workspace = session.get(Workspace, invite.workspace_id) if invite.workspace_id else None
    return {
        "id": invite.id,
        "role": invite.role,
        "workspace": workspace.name if workspace else None,
        "created_at": invite.created_at.isoformat(),
        "expires_at": invite.expires_at.isoformat(),
    }


def _throttle(bucket: str, request: Request, account: str) -> None:
    limit, window = settings.RATE_LIMITS[bucket]
    limiter.sweep()
    for key in (deps.client_ip(request), account):
        wait = limiter.check(bucket, key, limit, window)
        if wait > 0:
            raise HTTPException(
                429,
                f"Demasiados intentos. Vuelve a probar en {int(wait) + 1} segundos.",
                headers={"Retry-After": str(int(wait) + 1)},
            )

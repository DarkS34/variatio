"""Login, invitations, membership and password recovery.

There is no open registration endpoint anywhere in here on purpose: an account exists
because someone issued a single-use invitation, or because the installation's first
account was created from the command line. That is what removes the largest attack
surface a web login has, and with it the captcha and the anti-spam quotas.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session as DbSession

from .. import settings
from ..auth import deps, mail, passwords, tokens
from ..auth.rate_limit import limiter
from ..db import identity
from ..db.models import EDITOR, OWNER, ROLES, VIEWER, Invite, User, Workspace

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Deliberately the same sentence for "no such account" and "wrong password", and the
# failing path pays for a decoy hash so that the two also take the same time. Either
# half alone still answers "does this address have an account here?".
BAD_CREDENTIALS = "Correo o contraseña incorrectos."


class Credentials(BaseModel):
    email: EmailStr
    password: str


class InviteBody(BaseModel):
    email: EmailStr | None = None
    role: str = EDITOR
    workspace: bool = True


class AcceptBody(BaseModel):
    token: str
    name: str = ""
    email: EmailStr | None = None
    password: str


class PasswordBody(BaseModel):
    current: str
    next: str = Field(alias="new")

    model_config = {"populate_by_name": True}


class ForgotBody(BaseModel):
    email: EmailStr


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
    email = identity.normalise_email(body.email)
    _throttle("login", request, email)

    user = identity.get_user(session, email)
    if user is None or not user.active:
        passwords.waste_time()
        raise HTTPException(401, BAD_CREDENTIALS)
    if not passwords.verify_password(user.password_hash, body.password):
        raise HTTPException(401, BAD_CREDENTIALS)

    # The parameters live inside the hash, so raising them later upgrades every account
    # silently, one login at a time, with no migration.
    if passwords.needs_rehash(user.password_hash):
        identity.set_password(session, user, passwords.hash_password(body.password))

    limiter.clear("login", email)
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
    _throttle("password", request, user.email)
    if not passwords.verify_password(user.password_hash, body.current):
        raise HTTPException(403, "La contraseña actual no es correcta.")

    error = passwords.policy_error(body.next, email=user.email, name=user.name)
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
    email = identity.normalise_email(body.email)
    _throttle("forgot", request, email)

    user = identity.get_user(session, email)
    if user is not None and user.active:
        token = tokens.new_token()
        identity.create_reset(session, user.id, tokens.digest(token), settings.RESET_TTL)
        link = f"{_base_url(request)}/restablecer?token={token}"
        mail.send(
            user.email,
            "Restablece tu contraseña",
            "Has pedido restablecer la contraseña del generador de variantes.\n\n"
            f"Abre este enlace en menos de {int(settings.RESET_TTL.total_seconds() // 60)} "
            f"minutos:\n{link}\n\n"
            "Si no has sido tú, ignora este mensaje: la contraseña actual sigue valiendo.",
        )

    # Always the same answer, whether or not the address exists: this endpoint is the
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

    error = passwords.policy_error(body.password, email=user.email, name=user.name)
    if error:
        raise HTTPException(422, error)

    identity.set_password(session, user, passwords.hash_password(body.password))
    identity.consume_reset(session, row)
    identity.revoke_all_sessions(session, user.id)
    # Following the link proved control of the mailbox, which is the same evidence the
    # invitation flow accepts, so the reset also verifies the address.
    if user.email_verified_at is None:
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
        "email": invite.email,
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

    # A bound invitation fixes the address: the token was mailed there, so redeeming it is
    # the proof of control that replaces a separate verification round.
    email = identity.normalise_email(invite.email or (body.email or ""))
    if not email:
        raise HTTPException(422, "Falta el correo.")
    if invite.email and body.email and identity.normalise_email(body.email) != invite.email:
        raise HTTPException(422, "Esta invitación es para otra dirección de correo.")

    existing = identity.get_user(session, email)
    if existing is not None:
        if not invite.email:
            raise HTTPException(
                409, "Ese correo ya tiene cuenta. Pide una invitación dirigida a esa dirección."
            )
        # The account is already there and the password stays untouched — an invitation is
        # not a way to set somebody else's credentials. It only adds the membership.
        _apply_membership(session, invite, existing)
        identity.consume_invite(session, invite, existing.id)
        return {"created": False, "email": existing.email}

    error = passwords.policy_error(body.password, email=email, name=body.name)
    if error:
        raise HTTPException(422, error)

    user = identity.create_user(
        session,
        email=email,
        name=body.name.strip() or email.split("@")[0],
        password_hash=passwords.hash_password(body.password),
        email_verified=bool(invite.email),
    )
    _apply_membership(session, invite, user)
    identity.consume_invite(session, invite, user.id)
    _issue_session(session, user, request, response)
    return {"created": True, **_me(session, user)}


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
    _throttle("invite", request, access.user.email)
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'. Usa uno de {', '.join(ROLES)}.")

    token = tokens.new_token()
    invite = identity.create_invite(
        session,
        token_hash=tokens.digest(token),
        ttl=settings.INVITE_TTL,
        email=body.email,
        workspace_id=access.workspace.id if body.workspace else None,
        role=body.role,
        created_by=access.user.id,
    )

    link = f"{_base_url(request)}/invitacion?token={token}"
    delivered = False
    if body.email:
        delivered = mail.send(
            str(body.email),
            "Te han invitado al generador de variantes",
            f"{access.user.name} te invita a «{access.workspace.name}» como {body.role}.\n\n"
            f"Crea tu cuenta con este enlace, válido {settings.INVITE_TTL.days} días:\n{link}\n",
        )

    # The link comes back in the response whether or not the mail went out: with no SMTP
    # configured, handing it to whoever issued it is the honest behaviour, and it is also
    # how a closed group of colleagues actually passes an invitation around.
    return {"invite": _invite_view(invite, session), "link": link, "mailed": delivered}


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
                "email": user.email,
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


def _me(session: DbSession, user: User) -> dict:
    rows = identity.memberships_for(session, user.id)
    active = settings.workspace().slug
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin,
            "email_verified": user.email_verified_at is not None,
        },
        "workspaces": [
            {"slug": w.slug, "name": w.name, "role": m.role, "active": w.slug == active}
            for m, w in rows
        ],
        "role": next((m.role for m, w in rows if w.slug == active), None),
    }


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
        "email": invite.email,
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

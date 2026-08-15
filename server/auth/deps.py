"""The dependencies every route hangs from.

Two questions, deliberately separate. `current_user` answers *who is this*, and needs
only a session cookie. `require_member` answers *may they touch this workspace, at this
level*, and is a membership row — there is no bypass for administrators, because the
classic hole here is not the login, it is a read of somebody else's instance that nobody
checked. An admin flag governs running the installation, not access to its data.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, WebSocket
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session as DbSession

from .. import settings
from ..db import identity, repository, session_scope
from ..db.models import ROLE_RANK, VIEWER, User, UserSession, Workspace
from .tokens import digest

DB_UNREACHABLE = (
    "La base de datos no responde. Arráncala con `docker compose up -d postgres` "
    "y aplica las migraciones con `uv run alembic upgrade head`."
)


@dataclass(frozen=True)
class Access:
    user: User
    workspace: Workspace
    role: str


# Only the connection-level failures become "the database is not responding". Catching
# every `SQLAlchemyError` here would turn a duplicate-key violation raised by the route
# into that same message, which is a lie that sends whoever reads it to check Docker.
def db() -> Iterator[DbSession]:
    try:
        with session_scope() as session:
            yield session
    except (OperationalError, InterfaceError) as exc:
        raise HTTPException(503, DB_UNREACHABLE) from exc


def session_token(request: Request | WebSocket) -> str | None:
    return request.cookies.get(settings.SESSION_COOKIE)


def client_ip(request: Request | WebSocket) -> str:
    if settings.trust_proxy():
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


# Resolving a cookie to a user is the same work over HTTP and over the WebSocket
# handshake, and it must stay that way: the socket is the one place where forgetting it
# leaks another user's tokens rather than merely their metadata.
def resolve(session: DbSession, token: str | None) -> tuple[UserSession, User] | None:
    if not token:
        return None
    found = identity.live_session(session, digest(token))
    if found is None:
        return None
    row, user = found
    identity.touch_session(
        session, row, settings.SESSION_SLIDING, settings.SESSION_TOUCH_INTERVAL
    )
    return row, user


def current_user(request: Request, session: DbSession = Depends(db)) -> User:
    found = resolve(session, session_token(request))
    if found is None:
        raise HTTPException(401, "Inicia sesión para continuar.")
    row, user = found
    request.state.session_row = row
    return user


def optional_user(request: Request, session: DbSession = Depends(db)) -> User | None:
    found = resolve(session, session_token(request))
    if found is None:
        return None
    row, user = found
    request.state.session_row = row
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Hace falta ser administrador de la instalación.")
    return user


# The workspace the process serves. One per process today, so this is a lookup and not a
# path parameter; when `settings.workspace()` becomes per-request, this is the only place
# that has to learn about it.
def active_workspace(session: DbSession) -> Workspace:
    slug = settings.workspace().slug
    workspace = repository.get_workspace(session, slug)
    if workspace is None:
        raise HTTPException(
            503,
            f"El workspace '{slug}' no está en la base de datos. "
            "Cárgalo con `uv run variant-generator-server import-instance`.",
        )
    return workspace


def require_member(minimum: str = VIEWER):
    def dependency(
        user: User = Depends(current_user), session: DbSession = Depends(db)
    ) -> Access:
        workspace = active_workspace(session)
        membership = identity.membership(session, workspace.id, user.id)
        if membership is None:
            raise HTTPException(403, f"No tienes acceso al workspace '{workspace.slug}'.")
        if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
            raise HTTPException(
                403, f"Tu rol ({membership.role}) no permite esta acción; hace falta {minimum}."
            )
        return Access(user=user, workspace=workspace, role=membership.role)

    return dependency


# WEBSOCKET -----------------------------------------------------------------------------


# Authentication happens *before* `accept()`, which is why this cannot reuse the HTTP
# dependency: a socket that has been accepted has already been told it is welcome.
def authenticate_socket(websocket: WebSocket) -> Access | None:
    try:
        with session_scope() as session:
            found = resolve(session, session_token(websocket))
            if found is None:
                return None
            _, user = found
            workspace = repository.get_workspace(session, settings.workspace().slug)
            if workspace is None:
                return None
            membership = identity.membership(session, workspace.id, user.id)
            if membership is None:
                return None
            return Access(user=user, workspace=workspace, role=membership.role)
    except (OperationalError, InterfaceError):
        # No database means no way to prove the socket belongs to anyone, and the only
        # safe answer to that is the same as an invalid cookie.
        return None

"""The dependencies every route hangs from.

Three questions, deliberately separate. `current_user` answers *who is this*, and needs
only a session cookie. `resolve_workspace` answers *which instance is this request
about*. `require_member` answers *may they touch it, at this level*, and is a membership
row.

Which workspace a request means comes from, in order: the `X-Workspace` header (so two
browser tabs can sit in two different instances), then the account's `active_workspace`,
then its first membership. The header is a *request* for a workspace, never a permission
to enter one — the membership lookup below is what decides, and it runs identically
whichever way the slug arrived. When none of the three answers there is no fourth: an
account with no workspace is a normal account, and every route that reads instance data
tells it so with `NO_WORKSPACE` instead of picking an instance on its behalf.

The installation's administrator passes `require_member` for any workspace. That bypass
is written in `access_for` and nowhere else, so the exception is one `if` in a diff and
not a habit spread over forty routes, and `Access.as_admin` is how the UI is told it was
used.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, WebSocket
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session as DbSession

from variatio.core.workspace import Workspace as PathWorkspace

from .. import maintenance, settings
from ..db import identity, repository, session_scope
from ..db.models import OWNER, ROLE_RANK, VIEWER, User, UserSession, Workspace
from .tokens import digest

DB_UNREACHABLE = (
    "La base de datos no responde. Arráncala con `docker compose up -d postgres` "
    "y aplica las migraciones con `uv run alembic upgrade head`."
)

WORKSPACE_HEADER = "x-workspace"

NO_WORKSPACE = (
    "Todavía no tienes ningún espacio de trabajo. Crea el tuyo desde el panel, o pide acceso a "
    "uno existente a quien administra la instalación."
)


@dataclass(frozen=True)
class Access:
    """One request's answer to who, where, and at what level.

    `ws` is the same workspace as a set of paths, resolved here so no route has to know
    that a slug maps to a directory and so the mapping happens once per request.
    `as_admin` is true when the request only got through because the account administers
    the installation: routes do not branch on it, it is what the UI is told so an
    administrator can see they are looking at somebody else's instance.
    """

    user: User
    workspace: Workspace
    role: str
    ws: PathWorkspace
    as_admin: bool = False


def db() -> Iterator[DbSession]:
    """Yield a session, turning an unreachable database into a 503 with a hint.

    Only the connection-level failures become «la base de datos no responde». Catching
    every `SQLAlchemyError` here would give a duplicate-key violation raised by the route
    that same message, which is a lie that sends whoever reads it to check Docker.
    """
    try:
        with session_scope() as session:
            yield session
    except (OperationalError, InterfaceError) as exc:
        raise HTTPException(503, DB_UNREACHABLE) from exc


def session_token(request: Request | WebSocket) -> str | None:
    """Return the session cookie of this request or handshake, if it carries one."""
    return request.cookies.get(settings.session_cookie())


_UNCONFIGURED_BASE_URL_REPORTED = False


def base_url(request: Request) -> str:
    """Return the origin the links in an invitation or a reset mail point at.

    `PUBLIC_BASE_URL` is the answer, and the reflected `Origin` is deliberately not the
    fallback: `POST /forgot` is public and passes the origin check when the request
    carries neither header, so a mail could be minted pointing wherever the caller asked.
    The warning fires once, and only in production — deriving the address from the
    request is exactly what is wanted in development.
    """
    global _UNCONFIGURED_BASE_URL_REPORTED

    configured = settings.public_base_url()
    if configured:
        return configured
    if settings.is_production() and not _UNCONFIGURED_BASE_URL_REPORTED:
        _UNCONFIGURED_BASE_URL_REPORTED = True
        logger.warning(
            "PUBLIC_BASE_URL no está configurado: los enlaces de invitación y de "
            "restablecimiento se deducen de la petición. Fíjalo en '.env'"
        )
    return str(request.base_url).rstrip("/")


def client_ip(request: Request | WebSocket) -> str:
    """Return the address the per-IP half of the rate limit is keyed on.

    `X-Forwarded-For` is a list the proxies append to, so the entry written by the one
    proxy we trust is the LAST one and everything to its left is whatever the client
    sent. Reading the leftmost is reading the client: behind nginx's
    `$proxy_add_x_forwarded_for` or a CDN it lets anyone choose their own key, which is
    the same as not having one. Caddy overwrites the header rather than appending, so
    both readings agree there.
    """
    if settings.trust_proxy():
        forwarded = [
            part.strip()
            for part in request.headers.get("x-forwarded-for", "").split(",")
            if part.strip()
        ]
        if forwarded:
            return forwarded[-1]
    return request.client.host if request.client else ""


def requested_slug(request: Request | WebSocket) -> str | None:
    """Return the workspace this request asks for, from the header or the query string.

    The socket carries no header a browser can set, so it asks with `?workspace=`. Same
    string either way, and it goes through the same membership check.
    """
    header = request.headers.get(WORKSPACE_HEADER, "").strip()
    if header:
        return header
    return (request.query_params.get("workspace") or "").strip() or None


def resolve(session: DbSession, token: str | None) -> tuple[UserSession, User] | None:
    """Turn a session cookie into its row and its account, sliding the expiry.

    The same work over HTTP and over the WebSocket handshake, and it must stay that way:
    the socket is the one place where forgetting it leaks another user's tokens rather
    than merely their metadata.
    """
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
    """Return the account behind the session cookie, or raise 401."""
    found = resolve(session, session_token(request))
    if found is None:
        raise HTTPException(401, "Inicia sesión para continuar.")
    row, user = found
    request.state.session_row = row
    return user


def optional_user(request: Request, session: DbSession = Depends(db)) -> User | None:
    """Return the account behind the session cookie, or None when there is not one."""
    found = resolve(session, session_token(request))
    if found is None:
        return None
    row, user = found
    request.state.session_row = row
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    """Require that the account administers the installation, or raise 403."""
    if not user.is_admin:
        raise HTTPException(403, "Hace falta ser administrador de la instalación.")
    return user


def require_open(user: User = Depends(current_user)) -> User:
    """Refuse a non-administrator while the installation is closed for maintenance.

    The two routes that write without resolving a membership — creating a workspace and
    activating one — are the only ones the door in `access_for` cannot see, because there
    is no instance yet to be a member of. They declare this instead, so «the installation
    is closed» is true rather than nearly true.
    """
    if not user.is_admin and maintenance.active():
        raise HTTPException(503, maintenance.CLOSED)
    return user


# WORKSPACE -----------------------------------------------------------------------------


def first_membership(
    session: DbSession, user: User, excluding: int | None = None
) -> Workspace | None:
    """Return the first workspace this account belongs to, skipping `excluding`."""
    for _, workspace in identity.memberships_for(session, user.id):
        if workspace.id != excluding:
            return workspace
    return None


def current_workspace_for(session: DbSession, user: User) -> Workspace | None:
    """Return which instance this account lands in when the request does not name one.

    Its own last choice, then its first membership, and nothing else: «the default
    workspace» does not exist, so an account that belongs nowhere lands nowhere and the
    panel says so and offers to create one. An administrator with no membership is NOT
    dropped into the first workspace of the installation — entering somebody else's
    instance because it happened to be first is not landing anywhere on purpose, and the
    switcher already lists every one of them to open by hand.
    """
    if user.active_workspace_id is not None:
        workspace = session.get(Workspace, user.active_workspace_id)
        # The preference only counts while the access behind it does: the administrator
        # can revoke a membership, and landing on a revoked one is a 403 on every route
        # with no way back, even for someone who is a member of two others.
        if workspace is not None and workspace.deleted_at is None:
            if user.is_admin or identity.membership(session, workspace.id, user.id):
                return workspace
    return first_membership(session, user)


def rehome_accounts(session: DbSession, workspace: Workspace) -> dict[str, str | None]:
    """Move every account sitting in this workspace to wherever it lands next.

    The criterion is the one `current_workspace_for` applies with the last choice gone.
    Run BEFORE the row is deleted and told which workspace is leaving, because the two
    backends disagree about when a `SET NULL` lands and `memberships_for` would otherwise
    still offer the instance being removed.
    """
    stranded = (
        session.execute(select(User).where(User.active_workspace_id == workspace.id))
        .scalars()
        .all()
    )
    moved: dict[str, str | None] = {}
    for user in stranded:
        landing = first_membership(session, user, excluding=workspace.id)
        user.active_workspace_id = landing.id if landing is not None else None
        moved[user.username] = landing.slug if landing is not None else None
    return moved


def resolve_workspace(session: DbSession, user: User, slug: str | None) -> Workspace:
    """Return the workspace this request means, without deciding anything about access.

    Raises 404 for a slug that names none, and 403 `NO_WORKSPACE` when the request named
    none and the account belongs to none.
    """
    if slug:
        workspace = repository.get_workspace(session, slug)
        if workspace is None:
            raise HTTPException(404, f"No existe el espacio de trabajo '{slug}'.")
        return workspace

    workspace = current_workspace_for(session, user)
    if workspace is None:
        raise HTTPException(403, NO_WORKSPACE)
    return workspace


def access_for(session: DbSession, user: User, workspace: Workspace, minimum: str) -> Access:
    """Resolve this account's membership of this workspace, at least at `minimum`.

    The administrator bypass lives here and nowhere else: an account that administers the
    installation gets in as the owner with `as_admin` set, whether the membership is
    missing or merely too junior. The installation's maintenance door is here for the
    same reason — this is the one place every route that touches an instance goes through
    — and the administrator gets through that too, since a door that shuts on them has
    nothing left to reopen it from.

    Raises 403 without a membership and without the flag, and 503 while it is closed.
    """
    if not user.is_admin and maintenance.active():
        raise HTTPException(503, maintenance.CLOSED)

    row = identity.membership(session, workspace.id, user.id)
    as_admin = False

    if row is None:
        if not user.is_admin:
            raise HTTPException(403, f"No tienes acceso al espacio de trabajo '{workspace.slug}'.")
        as_admin, role = True, OWNER
    else:
        role = row.role
        if ROLE_RANK[role] < ROLE_RANK[minimum]:
            if not user.is_admin:
                raise HTTPException(
                    403, f"Tu rol ({role}) no permite esta acción; hace falta {minimum}."
                )
            as_admin, role = True, OWNER

    return Access(
        user=user,
        workspace=workspace,
        role=role,
        ws=settings.workspace_for(workspace.slug),
        as_admin=as_admin,
    )


def require_member(minimum: str = VIEWER):
    """Build the dependency demanding at least `minimum` in the requested workspace."""

    def dependency(
        request: Request,
        user: User = Depends(current_user),
        session: DbSession = Depends(db),
    ) -> Access:
        """Resolve the workspace this request names and the access the account has to it."""
        workspace = resolve_workspace(session, user, requested_slug(request))
        return access_for(session, user, workspace, minimum)

    return dependency


# WEBSOCKET -----------------------------------------------------------------------------


def authenticate_socket(websocket: WebSocket) -> Access | None:
    """Resolve a socket's access before `accept()`, returning None to refuse it.

    This cannot reuse the HTTP dependency: a socket that has been accepted has already
    been told it is welcome. No database means no way to prove the socket belongs to
    anyone, and the only safe answer to that is the same as an invalid cookie.
    """
    try:
        with session_scope() as session:
            found = resolve(session, session_token(websocket))
            if found is None:
                return None
            _, user = found
            slug = requested_slug(websocket)
            workspace = (
                repository.get_workspace(session, slug)
                if slug
                else current_workspace_for(session, user)
            )
            if workspace is None:
                return None
            try:
                return access_for(session, user, workspace, VIEWER)
            except HTTPException:
                return None
    except (OperationalError, InterfaceError):
        return None

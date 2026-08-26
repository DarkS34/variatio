"""The dependencies every route hangs from.

Three questions, deliberately separate. `current_user` answers *who is this*, and needs
only a session cookie. `resolve_workspace` answers *which instance is this request about*,
which since phase 3 is a per-request question and not a process constant. `require_member`
answers *may they touch it, at this level*, and is a membership row.

Which workspace a request means comes from, in order: the `X-Workspace` header (so two
browser tabs can sit in two different instances), then the account's `active_workspace`,
then its first membership. The header is a *request* for a workspace, never a permission
to enter one — the membership lookup below is what decides, and it runs identically
whichever way the slug arrived. When none of the three answers there is no fourth: an
account with no workspace is a normal account, and every route that reads instance data
tells it so with `NO_WORKSPACE` instead of picking an instance on its behalf.

The one exception is the installation's administrator, who since phase 3 passes through
`require_member` for any workspace. That is a deliberate departure from phase 2's «no
admin bypass», taken by explicit user request so that one account can operate the whole
installation and read the study's data across accounts. It is written here, in one place,
so the exception is one `if` in a diff and not a habit spread over forty routes.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, WebSocket
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
    "Todavía no tienes ningún workspace. Crea el tuyo desde el panel, o pide acceso a "
    "uno existente a quien administra la instalación."
)


@dataclass(frozen=True)
class Access:
    user: User
    workspace: Workspace
    role: str
    # The same workspace as a set of paths. Resolved here so no route has to know that a
    # slug maps to a directory, and so the mapping happens exactly once per request.
    ws: PathWorkspace
    # True when this request only got through because the account administers the
    # installation. Routes do not branch on it; it is what the UI is told, so an admin
    # can see that they are looking at somebody else's instance.
    as_admin: bool = False


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


# Where the links in an invitation or a reset mail point. `PUBLIC_BASE_URL` wins; failing
# that the caller's own `Origin`, which is right for development, where the browser is on
# Vite's port and the API's `base_url` would send it to the wrong one. Reading `Origin` is
# safe because a state-changing request only gets here after `OriginCheck` accepted it.
def base_url(request: Request) -> str:
    configured = settings.public_base_url()
    if configured:
        return configured
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    return str(request.base_url).rstrip("/")


def client_ip(request: Request | WebSocket) -> str:
    if settings.trust_proxy():
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


# The socket carries no headers a browser can set, so it asks with a query parameter.
# Same string either way, and it goes through the same membership check.
def requested_slug(request: Request | WebSocket) -> str | None:
    header = request.headers.get(WORKSPACE_HEADER, "").strip()
    if header:
        return header
    return (request.query_params.get("workspace") or "").strip() or None


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


# The two routes that write without resolving a membership — creating a workspace and
# activating one — are the only ones the door in `access_for` cannot see, because there is
# no instance yet to be a member of. They declare this instead, so «the installation is
# closed» is true rather than nearly true.
def require_open(user: User = Depends(current_user)) -> User:
    if not user.is_admin and maintenance.active():
        raise HTTPException(503, maintenance.CLOSED)
    return user


# WORKSPACE -----------------------------------------------------------------------------


# Which instance this account lands in when the request does not name one. It is the
# account's own last choice, or the first workspace it belongs to, and nothing else:
# «the default workspace» stopped existing on 2026-08-26, so an account that belongs
# nowhere lands nowhere, and the panel says so and offers to create one. That used to
# have one exception — an administrator with no membership was dropped into the first
# workspace of the installation — and it went with the rest: entering somebody else's
# instance because it happened to be first is not landing anywhere on purpose, and the
# switcher already lists every one of them for an administrator to open by hand.
def current_workspace_for(session: DbSession, user: User) -> Workspace | None:
    if user.active_workspace_id is not None:
        workspace = session.get(Workspace, user.active_workspace_id)
        # The preference only counts while the access behind it does. Since the
        # administrator can revoke a membership from the panel, the workspace an account
        # last used may be one it can no longer open — and landing there means a 403 on
        # every route with no way back, even for someone who is a member of two others.
        if workspace is not None and workspace.deleted_at is None:
            if user.is_admin or identity.membership(session, workspace.id, user.id):
                return workspace
    rows = identity.memberships_for(session, user.id)
    if rows:
        return rows[0][1]
    return None


def resolve_workspace(session: DbSession, user: User, slug: str | None) -> Workspace:
    if slug:
        workspace = repository.get_workspace(session, slug)
        if workspace is None:
            raise HTTPException(404, f"No existe el workspace '{slug}'.")
        return workspace

    workspace = current_workspace_for(session, user)
    if workspace is None:
        raise HTTPException(403, NO_WORKSPACE)
    return workspace


def access_for(session: DbSession, user: User, workspace: Workspace, minimum: str) -> Access:
    # The installation's door, here for the same reason the administrator bypass is: this
    # is the one place every route that touches an instance goes through, so closing it is
    # one `if` in a diff and not a habit spread over forty routes. The administrator gets
    # in anyway — they are the one applying the change, and a door that shuts on them too
    # has nothing left to reopen it from.
    if not user.is_admin and maintenance.active():
        raise HTTPException(503, maintenance.CLOSED)

    row = identity.membership(session, workspace.id, user.id)
    as_admin = False

    if row is None:
        if not user.is_admin:
            raise HTTPException(403, f"No tienes acceso al workspace '{workspace.slug}'.")
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
    def dependency(
        request: Request,
        user: User = Depends(current_user),
        session: DbSession = Depends(db),
    ) -> Access:
        workspace = resolve_workspace(session, user, requested_slug(request))
        return access_for(session, user, workspace, minimum)

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
        # No database means no way to prove the socket belongs to anyone, and the only
        # safe answer to that is the same as an invalid cookie.
        return None

from fastapi import Depends

from ..db.models import EDITOR, OWNER, VIEWER
from .deps import (
    Access,
    access_for,
    authenticate_socket,
    client_ip,
    current_user,
    db,
    default_workspace_for,
    optional_user,
    require_admin,
    require_member,
    requested_slug,
    resolve_workspace,
)
from .rate_limit import limiter
from .tokens import digest, new_token

# The three levels, ready to hang off a router. Routers declare VIEW once and the routes
# that write declare EDIT; a route with neither would be public, which is the mistake
# these exist to make visible in a diff.
#
# Built once, at import, and NOT rebuilt per use: FastAPI caches a dependency by the
# callable it wraps, so a handler that also writes `access: Access = auth.VIEW` to read
# the workspace reuses the router-level resolution instead of repeating the membership
# query. `Depends(require_member(VIEWER))` written inline would be a different callable
# each time and would run twice.
VIEW = Depends(require_member(VIEWER))
EDIT = Depends(require_member(EDITOR))
MANAGE = Depends(require_member(OWNER))

__all__ = [
    "EDIT",
    "MANAGE",
    "VIEW",
    "Access",
    "access_for",
    "authenticate_socket",
    "client_ip",
    "current_user",
    "db",
    "default_workspace_for",
    "digest",
    "limiter",
    "new_token",
    "optional_user",
    "require_admin",
    "require_member",
    "requested_slug",
    "resolve_workspace",
]

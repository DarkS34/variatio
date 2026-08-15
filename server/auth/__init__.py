from fastapi import Depends

from ..db.models import EDITOR, OWNER, VIEWER
from .deps import (
    Access,
    active_workspace,
    authenticate_socket,
    client_ip,
    current_user,
    db,
    optional_user,
    require_admin,
    require_member,
)
from .rate_limit import limiter
from .tokens import digest, new_token

# The three levels, ready to hang off a router. Routers declare VIEW once and the routes
# that write declare EDIT; a route with neither would be public, which is the mistake
# these exist to make visible in a diff.
VIEW = Depends(require_member(VIEWER))
EDIT = Depends(require_member(EDITOR))
MANAGE = Depends(require_member(OWNER))

__all__ = [
    "EDIT",
    "MANAGE",
    "VIEW",
    "Access",
    "active_workspace",
    "authenticate_socket",
    "client_ip",
    "current_user",
    "db",
    "digest",
    "limiter",
    "new_token",
    "optional_user",
    "require_admin",
    "require_member",
]

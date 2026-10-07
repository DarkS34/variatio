"""What a router imports to protect itself.

`VIEW`, `EDIT` and `MANAGE` are the three membership levels as FastAPI dependencies, and
`EVALUATION` and `TUTOR` the two optional functions (`server/features.py`); the rest is
re-exported from `deps`, `rate_limit` and `tokens`.
"""

from fastapi import Depends

from .. import features
from ..db.models import EDITOR, OWNER, VIEWER
from .deps import (
    NOT_MEMBER,
    ROLE_TOO_LOW,
    Access,
    access_for,
    at_least,
    authenticate_socket,
    base_url,
    client_ip,
    current_user,
    current_workspace_for,
    db,
    optional_user,
    require_admin,
    require_feature,
    require_member,
    require_open,
    requested_slug,
    resolve_workspace,
)
from .rate_limit import limiter
from .tokens import digest, new_token

# Routers declare VIEW once and the routes that write declare EDIT; a route with neither
# would be public, which is the mistake these exist to make visible in a diff. Built once
# at import and NOT rebuilt per use: FastAPI caches a dependency by the callable it wraps,
# so `Depends(require_member(VIEWER))` written inline would be a different callable each
# time and would run the membership query twice.
VIEW = Depends(require_member(VIEWER))
EDIT = Depends(require_member(EDITOR))
MANAGE = Depends(require_member(OWNER))

# The two optional functions, declared by their routers beside VIEW: the membership says
# whether the account may enter the workspace, these whether the function is open to it.
EVALUATION = Depends(require_feature(features.EVALUATION))
TUTOR = Depends(require_feature(features.TUTOR))

__all__ = [
    "EDIT",
    "EVALUATION",
    "MANAGE",
    "NOT_MEMBER",
    "ROLE_TOO_LOW",
    "TUTOR",
    "VIEW",
    "Access",
    "access_for",
    "at_least",
    "authenticate_socket",
    "base_url",
    "client_ip",
    "current_user",
    "current_workspace_for",
    "db",
    "digest",
    "limiter",
    "new_token",
    "optional_user",
    "require_admin",
    "require_feature",
    "require_member",
    "require_open",
    "requested_slug",
    "resolve_workspace",
]

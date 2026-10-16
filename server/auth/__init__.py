"""Identity and permissions, and what a router imports to protect itself.

The area holds the sessions and the route guards (`deps.py`), the queries over accounts,
invitations and memberships (`queries.py`), who may use each optional function
(`features.py`), passwords, tokens, sealed links, mail and rate limits, and the routes of
login, one's own account and password recovery (`router.py`). Who belongs to a subject and
its groups is `members.py` and `groups.py`, at the server's root.

`VIEW`, `EDIT` and `MANAGE` are the three membership levels as FastAPI dependencies, and
`EVALUATION` and `TUTOR` the two optional functions, and `CHAT` the free chat, which a
subject opens to its students; the rest is re-exported from `deps`, `rate_limit` and
`tokens`.
"""

from fastapi import Depends

from ..db.models import EDITOR, OWNER, VIEWER
from . import features
from .deps import (
    MEMBERSHIP_DISABLED,
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
    require_viewer,
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
VIEW = Depends(require_viewer)
EDIT = Depends(require_member(EDITOR))
MANAGE = Depends(require_member(OWNER))

# The two optional functions, declared by their routers beside VIEW: the membership says
# whether the account may enter the workspace, these whether the function is open to it.
EVALUATION = Depends(require_feature(features.EVALUATION))
TUTOR = Depends(require_feature(features.TUTOR))
# The free chat is no optional function of the administrator's, but the same dependency reads
# what the subject's teachers decided (`features.refusal`).
CHAT = Depends(require_feature(features.CHAT))

__all__ = [
    "CHAT",
    "EDIT",
    "EVALUATION",
    "MANAGE",
    "MEMBERSHIP_DISABLED",
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

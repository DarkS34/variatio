"""The database: the tables, and the session factory that reaches them.

All of it lives under the `server` extra — the runtime pipeline imports none of it, and
`import server` works with no database reachable.
"""

from .models import (
    CURATED,
    DRAFT,
    EDITOR,
    OWNER,
    ROLE_RANK,
    ROLES,
    SLOT_CORPUS,
    SLOT_EXEMPLARS,
    VIEWER,
    Approval,
    Artifact,
    Base,
    EvalSession,
    Generation,
    Invite,
    Membership,
    PasswordReset,
    RawDocument,
    User,
    UserSession,
    Workspace,
)
from .session import database_url, engine, get_session, is_available, session_scope

__all__ = [
    "CURATED",
    "DRAFT",
    "EDITOR",
    "OWNER",
    "ROLES",
    "ROLE_RANK",
    "SLOT_CORPUS",
    "SLOT_EXEMPLARS",
    "VIEWER",
    "Approval",
    "Artifact",
    "Base",
    "EvalSession",
    "Generation",
    "Invite",
    "Membership",
    "PasswordReset",
    "RawDocument",
    "User",
    "UserSession",
    "Workspace",
    "database_url",
    "engine",
    "get_session",
    "is_available",
    "session_scope",
]

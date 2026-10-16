"""What the class's four route modules share: a refused gesture as the client reads it, the
group a request scopes to, the groups as listed, a person's name and a moment.

A route module imports no other (an import contract), so what two of them answer alike lives
here, beside them.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session as DbSession

from .. import auth
from ..auth import queries
from . import groups
from .members import Refusal


def _group(db: DbSession, access: auth.Access, group_id: int | None):
    """Return the group of this subject a request scopes to, None for the class, or 404."""
    if group_id is None:
        return None
    try:
        return groups.get(db, access.workspace, group_id)
    except Refusal as refusal:
        raise _http(refusal) from None


def _groups_view(db: DbSession, access: auth.Access) -> list[dict]:
    """Render the subject's groups: name, how many active students, and what they use."""
    counts = groups.sizes(db, access.workspace)
    return [
        {"id": group.id, "name": group.name, "students": counts.get(group.id, 0), **groups.tools(group)}
        for group in groups.all_of(db, access.workspace)
    ]


def _http(refusal: Refusal) -> HTTPException:
    """Turn a refused gesture into the answer the client reads by its code."""
    return HTTPException(refusal.status, refusal.message, headers={"X-Error-Code": refusal.code})


def _display(db: DbSession, user_id: int) -> str | None:
    """Name the account that let somebody in, by its display name; None when it is gone."""
    user = queries.get_user_by_id(db, user_id)
    return user.name if user is not None else None


def _iso(moment: datetime | None) -> str | None:
    """Render a moment as ISO 8601, or None."""
    return moment.isoformat() if moment is not None else None

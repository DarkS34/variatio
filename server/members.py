"""The people of a subject: what a teacher does to a membership, and what that sets off.

Three gestures — pause, open again, remove — each one function, because every door that
performs one must do the same things in the same order: the class's own routes, the
administrator's panel, leaving a subject and ending a course. Closing a membership refuses
what would take the last owner from the subject's people (`identity.would_orphan`), moves the
account's active subject elsewhere, stops its jobs there, writes the row, and announces it on
the bus as `membership.closed` — an event no browser receives, on which an open socket of that
account closes (`routers/ws.py`).

PAUSING IS REVERSIBLE AND REMOVING IS NOT. A paused membership keeps its role, its origin and
its date, and a teacher opens it again; a removed one is gone, and only a new link brings the
person back, as somebody new. Neither touches what the person produced: their exercises and
their conversations are files of their own directory and stay where they are.
"""

from dataclasses import dataclass

from loguru import logger
from sqlalchemy.orm import Session

from . import singletons
from .auth.deps import first_membership
from .db import identity
from .db.models import OWNER, Membership, User, Workspace

CLOSED_EVENT = "membership.closed"
DISABLED = "disabled"
REMOVED = "removed"

# What a refusal carries in `X-Error-Code`.
LAST_OWNER = "last_owner"
OWNER_PAUSED = "owner_disabled"


@dataclass
class Refusal(Exception):
    """A gesture refused, with the status, the stable code and the sentence it answers with."""

    status: int
    code: str
    message: str

    def __str__(self) -> str:
        """Say the sentence, which is what a log line or a bulk answer shows."""
        return self.message


def disable_member(session: Session, workspace: Workspace, member: User, by: User | None) -> Membership:
    """Pause this account's membership: it keeps everything and opens nothing.

    An owner is never paused — they lower themselves to teacher first — so the subject keeps
    whoever answers for it.
    """
    row = _row(session, workspace, member)
    if not row.active:
        return row
    if row.role == OWNER:
        raise Refusal(
            409, OWNER_PAUSED, "Un propietario no se desactiva: antes hay que pasarlo a docente."
        )
    _guard(session, workspace, member, None)
    _close(session, workspace, member, row, by, DISABLED)
    return row


def enable_member(session: Session, workspace: Workspace, member: User, by: User | None) -> Membership:
    """Open a paused membership again, as it was. The account's active subject stays put."""
    row = _row(session, workspace, member)
    if row.active:
        return row
    row.disabled_at = None
    row.disabled_by = None
    session.flush()
    logger.info(
        "[asignatura] «{}» activó a «{}» en «{}»", _name(by), member.username, workspace.slug
    )
    return row


def remove_member(session: Session, workspace: Workspace, member: User, by: User | None) -> None:
    """Take this account out of the subject, paused or not. Its files stay."""
    row = _row(session, workspace, member)
    if row.active:
        _guard(session, workspace, member, None)
    _close(session, workspace, member, row, by, REMOVED)


def change_role(session: Session, workspace: Workspace, member: User, role: str) -> Membership:
    """Give an active member another role, refusing to take the last owner from the subject."""
    row = _row(session, workspace, member)
    if row.role != role:
        if row.active:
            _guard(session, workspace, member, role)
        row.role = role
        session.flush()
    return row


def _row(session: Session, workspace: Workspace, member: User) -> Membership:
    """Return the account's membership of this subject, or refuse: it is not one of its people."""
    row = identity.membership(session, workspace.id, member.id)
    if row is None:
        raise Refusal(404, "not_found", "Esa persona no está en esta asignatura.")
    return row


def _guard(session: Session, workspace: Workspace, member: User, role: str | None) -> None:
    """Refuse a change that would leave the subject's people with no active owner."""
    if identity.would_orphan(session, workspace.id, member.id, role):
        raise Refusal(
            409,
            LAST_OWNER,
            "La asignatura se quedaría sin propietario: haz propietario a otro docente antes.",
        )


def _close(
    session: Session,
    workspace: Workspace,
    member: User,
    row: Membership,
    by: User | None,
    gesture: str,
) -> None:
    """Close one membership: move the account out, stop its jobs, write the row, announce it.

    Committed before it is announced: a socket that closes on the event makes its client read
    the session at once, and the change has to be there to be read.
    """
    if member.active_workspace_id == workspace.id:
        landing = first_membership(session, member, excluding=workspace.id)
        member.active_workspace_id = landing.id if landing is not None else None
    runner = singletons.runner
    for job in [*runner.running(workspace.slug), *runner.pending(workspace.slug)]:
        if job.user_id == member.id:
            runner.cancel(job.id)
    if gesture == DISABLED:
        row.disabled_at = identity.now()
        row.disabled_by = by.id if by is not None else None
    else:
        session.delete(row)
    session.commit()
    singletons.bus.publish_internal(
        workspace.slug, CLOSED_EVENT, {"user_id": member.id, "gesture": gesture}
    )
    verb = "desactivó" if gesture == DISABLED else "quitó"
    logger.info(
        "[asignatura] «{}» {} a «{}» en «{}»", _name(by), verb, member.username, workspace.slug
    )


def _name(user: User | None) -> str:
    """Name who did it in a log line; a gesture with no author is the command line's."""
    return user.username if user is not None else "la línea de órdenes"

"""The groups of a subject's class: what a teacher does to them, and who is in each.

A group is a part of the class with which its teachers do what they do with the whole class
(the user's decision, 2026-10-14): open or close each tool to it, follow its own progress,
invite into it, read its activity, choose what of the bank it sees. A student is in one group
at most, for now; a teacher is in none. Pausing a student keeps their group; removing them
takes it with the membership.

The gestures are functions here for `members.py`'s reason: every door that does one — the
class's routes, a link that brings a student in — must do the same things in the same order.
"""

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .db import identity
from .db.models import VIEWER, ClassGroup, ClassGroupMember, Membership, User, Workspace
from .members import Refusal

# The tools a group may open or close, beside the subject's switches (`features.py`).
TOOLS: tuple[str, ...] = ("generate", "tutor", "chat")

NAME_MAX = 80

# What a refusal carries in `X-Error-Code`.
NAME_TAKEN = "group_name_taken"
NOT_A_STUDENT = "not_a_student"


def all_of(session: Session, workspace: Workspace) -> list[ClassGroup]:
    """Return the subject's groups, by name."""
    return list(
        session.scalars(
            select(ClassGroup)
            .where(ClassGroup.workspace_id == workspace.id)
            .order_by(func.lower(ClassGroup.name), ClassGroup.id)
        )
    )


def get(session: Session, workspace: Workspace, group_id: int) -> ClassGroup:
    """Return one group of this subject, or refuse: another subject's is unknown here."""
    group = session.get(ClassGroup, group_id)
    if group is None or group.workspace_id != workspace.id:
        raise Refusal(404, "not_found", "Ese grupo no existe en esta asignatura.")
    return group


def sizes(session: Session, workspace: Workspace) -> dict[int, int]:
    """Count the active students of each group of the subject."""
    rows = session.execute(
        select(ClassGroupMember.group_id, func.count())
        .join(Membership, Membership.id == ClassGroupMember.membership_id)
        .join(ClassGroup, ClassGroup.id == ClassGroupMember.group_id)
        .where(
            ClassGroup.workspace_id == workspace.id,
            Membership.disabled_at.is_(None),
        )
        .group_by(ClassGroupMember.group_id)
    )
    return {group_id: count for group_id, count in rows}


def placed(session: Session, workspace: Workspace) -> dict[int, ClassGroup]:
    """Return the group of every student of the subject who is in one, by account id."""
    rows = session.execute(
        select(Membership.user_id, ClassGroup)
        .join(ClassGroupMember, ClassGroupMember.membership_id == Membership.id)
        .join(ClassGroup, ClassGroup.id == ClassGroupMember.group_id)
        .where(Membership.workspace_id == workspace.id)
    )
    return {user_id: group for user_id, group in rows}


def member_ids(session: Session, group: ClassGroup) -> set[int]:
    """Return the accounts of a group's students, paused ones included."""
    return set(
        session.scalars(
            select(Membership.user_id)
            .join(ClassGroupMember, ClassGroupMember.membership_id == Membership.id)
            .where(ClassGroupMember.group_id == group.id)
        )
    )


def create(session: Session, workspace: Workspace, name: str, by: User | None) -> ClassGroup:
    """Make a new group of the class, with no student and every tool as the subject says."""
    clean = _name(session, workspace, name)
    group = ClassGroup(workspace_id=workspace.id, name=clean, created_by=by.id if by else None)
    session.add(group)
    session.flush()
    logger.info("[asignatura] «{}» creó el grupo «{}» en «{}»", _who(by), clean, workspace.slug)
    return group


def rename(session: Session, workspace: Workspace, group: ClassGroup, name: str) -> ClassGroup:
    """Give a group another name, unique in its subject."""
    group.name = _name(session, workspace, name, keep=group.id)
    session.flush()
    return group


def delete_group(session: Session, workspace: Workspace, group: ClassGroup, by: User | None) -> None:
    """Delete a group: its students stay in the class with no group, and its live link dies."""
    link = identity.live_class_link(session, workspace.id, group.id)
    if link is not None:
        identity.revoke_class_link(session, link)
    name = group.name
    session.delete(group)
    session.flush()
    logger.info("[asignatura] «{}» borró el grupo «{}» de «{}»", _who(by), name, workspace.slug)


def place(
    session: Session, workspace: Workspace, member: User, group: ClassGroup | None
) -> None:
    """Put a student in a group, moving them from the one they were in; None takes them out.

    Students only: a teacher is in no group.
    """
    row = identity.membership(session, workspace.id, member.id)
    if row is None:
        raise Refusal(404, "not_found", "Esa persona no está en esta asignatura.")
    if row.role != VIEWER:
        raise Refusal(409, NOT_A_STUDENT, "Los grupos son de alumnos: un docente no está en ninguno.")
    session.execute(delete(ClassGroupMember).where(ClassGroupMember.membership_id == row.id))
    if group is not None:
        session.add(ClassGroupMember(group_id=group.id, membership_id=row.id))
    session.flush()


def place_on_entry(session: Session, workspace_id: int, user_id: int, group_id: int | None) -> None:
    """Put a student who came in through a group's link or invitation in that group.

    A link of a group that no longer exists, or that is another subject's, places nobody; a
    teacher's membership is never placed.
    """
    if group_id is None:
        return
    group = session.get(ClassGroup, group_id)
    row = identity.membership(session, workspace_id, user_id)
    if group is None or group.workspace_id != workspace_id or row is None or row.role != VIEWER:
        return
    session.execute(delete(ClassGroupMember).where(ClassGroupMember.membership_id == row.id))
    session.add(ClassGroupMember(group_id=group.id, membership_id=row.id))
    session.flush()


def set_tools(session: Session, group: ClassGroup, changes: dict[str, bool | None]) -> None:
    """Open, close or hand back to the subject each tool named in `changes`."""
    for tool, value in changes.items():
        if tool in TOOLS:
            setattr(group, tool, value)
    session.flush()


def tools(group: ClassGroup) -> dict[str, bool | None]:
    """Answer what a group's students may use: True, False, or None for «as the subject»."""
    return {tool: getattr(group, tool) for tool in TOOLS}


def _name(session: Session, workspace: Workspace, name: str, keep: int | None = None) -> str:
    """Return a group's name tidied, refusing an empty one or one the subject already has."""
    clean = " ".join(name.split())
    if not clean:
        raise Refusal(422, "empty_name", "Un grupo necesita un nombre.")
    if len(clean) > NAME_MAX:
        raise Refusal(422, "long_name", f"El nombre de un grupo tiene {NAME_MAX} caracteres como mucho.")
    taken = session.scalar(
        select(ClassGroup.id).where(
            ClassGroup.workspace_id == workspace.id,
            func.lower(ClassGroup.name) == clean.lower(),
            ClassGroup.id != (keep or 0),
        )
    )
    if taken is not None:
        raise Refusal(409, NAME_TAKEN, f"Ya hay un grupo «{clean}» en esta asignatura.")
    return clean


def _who(user: User | None) -> str:
    """Name who did it in a log line."""
    return user.username if user is not None else "la línea de órdenes"

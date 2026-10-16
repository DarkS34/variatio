"""What a subject's students use, for its teachers: generating, the tutor and the free chat.

Declares `auth.EDIT` for the whole router, as the class list does. WHAT THE STUDENTS USE is
the teachers' too: whether the subject's students generate exercises and use the tutor (`/uses`,
the two switches `server/auth/features.py` reads), closed during an exam, say. The tutor's
switch matters only where the administrator opened the tutor to one of them, and the answer
says whether that is so.
"""

from fastapi import APIRouter, Depends
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ... import auth
from ...auth import features
from .. import activity, groups
from ..shared import _group

router = APIRouter(prefix="/api/members", tags=["members"], dependencies=[auth.EDIT])


class UsesBody(BaseModel):
    """What the subject's students may use; only the fields sent change.

    For a group (`?group=<id>`) a field sent as null hands the tool back to the subject's switch.
    """

    generate: bool | None = None
    tutor: bool | None = None
    chat: bool | None = None


# A fixed path, a different shape from `/{user_id:int}`, which no word matches.


@router.get("/uses")
def uses(
    group: int | None = None, access: auth.Access = auth.EDIT, db: DbSession = Depends(auth.db)
) -> dict:
    """Answer what the subject's students may use, or one group's, and whether the tutor is
    theirs to use at all."""
    return _uses_view(db, access, _group(db, access, group))


@router.patch("/uses")
def change_uses(
    body: UsesBody,
    group: int | None = None,
    access: auth.Access = auth.EDIT,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Open or close each tool to the subject's students, or to one group; teachers keep all.

    For a group a tool sent as null goes back to what the subject says.
    """
    scoped = _group(db, access, group)
    if scoped is not None:
        changes = {name: getattr(body, name) for name in body.model_fields_set if name in groups.TOOLS}
        groups.set_tools(db, scoped, changes)
    else:
        changes = {
            name: value
            for name, value in body.model_dump(exclude_none=True).items()
            if name in features.SUBJECT_SWITCHES
        }
        features.set_subject_uses(db, access.workspace, changes)
    for feature, value in changes.items():
        logger.info(
            "[asignatura] «{}» {} {} a {} de «{}»",
            access.user.username,
            "abrió" if value else ("cerró" if value is False else "devolvió a la asignatura"),
            _TOOL_NAMES.get(feature, feature),
            f"el grupo «{scoped.name}»" if scoped is not None else "los alumnos",
            access.ws.slug,
        )
    return _uses_view(db, access, scoped)


# What a log line calls each tool.
_TOOL_NAMES = {"generate": "la generación", "tutor": "el tutor", "chat": "el chat libre"}


def _uses_view(db: DbSession, access: auth.Access, group=None) -> dict:
    """Render the switches, whether the tutor is installed, and whether it is offered here.

    A teacher reads the tutor's switch wherever the tutor is installed; it switches something
    only once the administrator opened the tutor to one of the subject's students. For a group,
    `group` says its own three values (None is «as the subject») beside the subject's.
    """
    return {
        **features.subject_uses(access.workspace),
        "tutor_installed": activity.tutor_installed(),
        "tutor_offered": features.offered_to_students(db, access.workspace),
        **({"group": {"id": group.id, "name": group.name, **groups.tools(group)}} if group else {}),
    }

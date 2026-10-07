"""Who the installation's optional functions are for: the evaluation and the Socratic tutor.

Each function is in one of three modes — nobody, every account, or a list of accounts — and
the administrator sets it from the panel. A function with no row is off, so an installation
opens neither until somebody decides to.

NOT A MEMBERSHIP, AND CHECKED BESIDE ONE. `auth.VIEW` still decides whether an account may
enter the workspace a request names; `auth.EVALUATION` and `auth.TUTOR` decide whether the
function exists for that account at all. The administrator gets no bypass here: an
installation's administrator who wants the tutor lists their own account, like anybody's.
The administrator's own READ routes (`/api/admin/...`) are not behind this, so what a function
recorded stays readable while it is off.

The list of a function is kept whatever its mode: switching to everybody and back to the list
finds the list as it was, and an invitation can list its holder before the mode is `selected`.

WHAT A SUBJECT LETS ITS STUDENTS USE (2026-10-06). Inside a subject its teachers decide two
more things for its students alone: whether they generate exercises and whether they use the
tutor (`workspaces.student_generate`, `student_tutor`; «Clase → Qué usan los alumnos»).
`refusal` is the one reading of all of it — the administrator's mode, the role and the
subject's switch — and `for_user` answers it for the subject an account is in.

A FUNCTION FOR A WHOLE SUBJECT (the class plan's phase 15): under `selected`, beside the
accounts on its list, a function may list subjects (`SUBJECT_LISTED`: the tutor alone), and then
everybody in a listed subject uses it there — not in their other subjects.
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db.models import (
    VIEWER,
    FeatureAccess,
    FeatureGrant,
    FeatureSubject,
    Membership,
    User,
    Workspace,
)

EVALUATION = "evaluation"
TUTOR = "tutor"
FEATURES: tuple[str, ...] = (EVALUATION, TUTOR)

# The functions a whole subject may be listed for (the class plan's phase 15): under `selected`
# everybody in a listed subject uses the function there. The evaluation stays account by
# account (decided 2026-10-06), so only the tutor.
SUBJECT_LISTED: tuple[str, ...] = (TUTOR,)

# Generating is everybody's, but a subject's teachers may close it to its students. It is not
# an optional function: it has no mode and no row in `feature_access`.
GENERATE = "generate"

# What a subject's teachers may close to its students, and the column that says it is open.
SUBJECT_SWITCHES: dict[str, str] = {GENERATE: "student_generate", TUTOR: "student_tutor"}

OFF = "off"
ALL = "all"
SELECTED = "selected"
MODES: tuple[str, ...] = (OFF, ALL, SELECTED)

# What a refused request carries in `X-Error-Code`: the client recognises the refusal by it,
# never by the sentence.
OFF_CODE = "feature_off"

REFUSALS = {
    EVALUATION: "La evaluación del sistema no está activada para tu cuenta.",
    TUTOR: "El tutor socrático no está activado para tu cuenta.",
}

# What a student hears when the subject's teachers closed the function to its students.
CLOSED_HERE = {
    GENERATE: "Tu docente ha cerrado la generación de ejercicios en esta asignatura.",
    TUTOR: "Tu docente ha cerrado el tutor en esta asignatura.",
}


def for_user(
    session: Session, user: User, workspace: Workspace | None = None, role: str | None = None
) -> dict[str, bool]:
    """Answer, for generating and every function, whether it is open to this account here.

    `workspace` and `role` are the subject the account is in and its role there; without
    them only the administrator's modes are read, which is what an account in no subject has.
    """
    return {
        feature: refusal(session, user, feature, workspace, role) is None
        for feature in (GENERATE, *FEATURES)
    }


def refusal(
    session: Session,
    user: User,
    feature: str,
    workspace: Workspace | None = None,
    role: str | None = None,
) -> str | None:
    """Return why `feature` is closed to this account in this subject, or None when it is open.

    The administrator's mode first, for the optional functions; then, for a student of the
    subject, the switch its teachers set. A teacher, and an administrator entering through the
    bypass (who holds the owner's role), never meets a subject's switch.
    """
    if feature in FEATURES and not enabled(session, user, feature, workspace):
        return REFUSALS[feature]
    column = SUBJECT_SWITCHES.get(feature)
    if column and workspace is not None and role == VIEWER and not getattr(workspace, column, True):
        return CLOSED_HERE[feature]
    return None


def subject_uses(workspace: Workspace) -> dict[str, bool]:
    """Answer what a subject's teachers let its students use."""
    return {feature: bool(getattr(workspace, column)) for feature, column in SUBJECT_SWITCHES.items()}


def set_subject_uses(session: Session, workspace: Workspace, changes: dict[str, bool]) -> None:
    """Open or close to a subject's students the functions named in `changes`."""
    for feature, value in changes.items():
        setattr(workspace, SUBJECT_SWITCHES[feature], bool(value))
    session.flush()


def offered_to_students(session: Session, workspace: Workspace) -> bool:
    """Say whether the administrator opened the tutor to anybody studying in this subject.

    The subject's switch for the tutor means something only then: with the tutor open to
    none of its students, «Qué usan los alumnos» does not draw it.
    """
    current = mode(session, TUTOR)
    if current == ALL:
        return True
    if current != SELECTED:
        return False
    if subject_listed(session, TUTOR, workspace):
        return True
    return (
        session.scalar(
            select(Membership.id)
            .join(FeatureGrant, FeatureGrant.user_id == Membership.user_id)
            .where(
                FeatureGrant.feature == TUTOR,
                Membership.workspace_id == workspace.id,
                Membership.role == VIEWER,
                Membership.disabled_at.is_(None),
            )
            .limit(1)
        )
        is not None
    )


def enabled(
    session: Session, user: User, feature: str, workspace: Workspace | None = None
) -> bool:
    """Say whether `feature` is open to this account, in `workspace` when one is named.

    Under `selected`: the account is on the function's list, or — for a function a subject may
    be listed for — the subject it is working in is.
    """
    current = mode(session, feature)
    if current == ALL:
        return True
    if current != SELECTED:
        return False
    listed_account = session.scalar(
        select(FeatureGrant.id).where(
            FeatureGrant.feature == feature, FeatureGrant.user_id == user.id
        )
    )
    if listed_account is not None:
        return True
    return workspace is not None and subject_listed(session, feature, workspace)


def subject_listed(session: Session, feature: str, workspace: Workspace) -> bool:
    """Say whether a subject is on a function's list."""
    if feature not in SUBJECT_LISTED:
        return False
    return (
        session.scalar(
            select(FeatureSubject.id).where(
                FeatureSubject.feature == feature, FeatureSubject.workspace_id == workspace.id
            )
        )
        is not None
    )


def snapshot(session: Session) -> dict[str, dict]:
    """Render every function for the panel: its mode, its accounts and, where it may, its subjects."""
    return {
        feature: {
            "mode": mode(session, feature),
            "accounts": listed(session, feature),
            **({"workspaces": listed_subjects(session, feature)} if feature in SUBJECT_LISTED else {}),
        }
        for feature in FEATURES
    }


def mode(session: Session, feature: str) -> str:
    """Return the mode `feature` is in; a function nobody has set is off."""
    row = session.get(FeatureAccess, feature)
    return row.mode if row is not None and row.mode in MODES else OFF


def listed(session: Session, feature: str) -> list[int]:
    """Return the ids of the accounts on the list of `feature`, in id order."""
    return list(
        session.scalars(
            select(FeatureGrant.user_id)
            .where(FeatureGrant.feature == feature)
            .order_by(FeatureGrant.user_id)
        )
    )


def set_mode(session: Session, feature: str, new_mode: str) -> None:
    """Put `feature` in `new_mode`; its list is left as it is."""
    row = session.get(FeatureAccess, feature)
    if row is None:
        session.add(FeatureAccess(feature=feature, mode=new_mode))
    else:
        row.mode = new_mode
    session.flush()


def set_listed(session: Session, feature: str, user_ids: list[int]) -> None:
    """Replace the list of `feature` with exactly these accounts."""
    wanted = set(user_ids)
    current = set(listed(session, feature))
    if current - wanted:
        session.execute(
            delete(FeatureGrant).where(
                FeatureGrant.feature == feature, FeatureGrant.user_id.in_(current - wanted)
            )
        )
    for user_id in sorted(wanted - current):
        session.add(FeatureGrant(feature=feature, user_id=user_id))
    session.flush()


def listed_subjects(session: Session, feature: str) -> list[str]:
    """Return the slugs of the subjects on the list of `feature`, in slug order."""
    return list(
        session.scalars(
            select(Workspace.slug)
            .join(FeatureSubject, FeatureSubject.workspace_id == Workspace.id)
            .where(FeatureSubject.feature == feature)
            .order_by(Workspace.slug)
        )
    )


def set_listed_subjects(session: Session, feature: str, workspace_ids: list[int]) -> None:
    """Replace the subjects on the list of `feature` with exactly these."""
    wanted = set(workspace_ids)
    current = set(
        session.scalars(select(FeatureSubject.workspace_id).where(FeatureSubject.feature == feature))
    )
    if current - wanted:
        session.execute(
            delete(FeatureSubject).where(
                FeatureSubject.feature == feature,
                FeatureSubject.workspace_id.in_(current - wanted),
            )
        )
    for workspace_id in sorted(wanted - current):
        session.add(FeatureSubject(feature=feature, workspace_id=workspace_id))
    session.flush()


def list_account(session: Session, feature: str, user_id: int) -> None:
    """Add one account to the list of `feature`; adding it twice changes nothing."""
    if user_id not in listed(session, feature):
        session.add(FeatureGrant(feature=feature, user_id=user_id))
        session.flush()


def unknown(features: list[str]) -> list[str]:
    """Return the names in `features` that are not optional functions of this installation."""
    return [name for name in features if name not in FEATURES]

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
"""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db.models import FeatureAccess, FeatureGrant, User

EVALUATION = "evaluation"
TUTOR = "tutor"
FEATURES: tuple[str, ...] = (EVALUATION, TUTOR)

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


def for_user(session: Session, user: User) -> dict[str, bool]:
    """Answer, for every function, whether it is open to this account."""
    return {feature: enabled(session, user, feature) for feature in FEATURES}


def enabled(session: Session, user: User, feature: str) -> bool:
    """Say whether `feature` is open to this account."""
    current = mode(session, feature)
    if current == ALL:
        return True
    if current == SELECTED:
        return (
            session.scalar(
                select(FeatureGrant.id).where(
                    FeatureGrant.feature == feature, FeatureGrant.user_id == user.id
                )
            )
            is not None
        )
    return False


def snapshot(session: Session) -> dict[str, dict]:
    """Render every function for the panel: its mode and the accounts on its list."""
    return {
        feature: {"mode": mode(session, feature), "accounts": listed(session, feature)}
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


def list_account(session: Session, feature: str, user_id: int) -> None:
    """Add one account to the list of `feature`; adding it twice changes nothing."""
    if user_id not in listed(session, feature):
        session.add(FeatureGrant(feature=feature, user_id=user_id))
        session.flush()


def unknown(features: list[str]) -> list[str]:
    """Return the names in `features` that are not optional functions of this installation."""
    return [name for name in features if name not in FEATURES]

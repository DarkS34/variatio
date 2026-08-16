"""Every query that touches a user, a session, an invite or a membership.

Kept apart from `repository.py` — which is about the instance's artifacts — because
these are the only queries on the request path of *every* endpoint, and because the
normalising boundary for an identifier has to be exactly one place: `normalise_username`
is it, so a duplicate differing in case cannot enter through a second door.
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    EDITOR,
    Invite,
    Membership,
    PasswordReset,
    User,
    UserSession,
    Workspace,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}[a-z0-9]$")


def normalise_username(username: str) -> str:
    return username.strip().lower()


def normalise_email(email: str) -> str:
    return email.strip().lower()


# The one place that says what a username may be, so the web form, the invitation and the
# command line cannot disagree about it. No spaces and no `@`: the first would make two
# accounts indistinguishable on screen, the second would let a username be mistaken for
# an address in every message that prints one.
def username_error(username: str) -> str | None:
    if not USERNAME_PATTERN.fullmatch(normalise_username(username)):
        return (
            "El usuario tiene entre 3 y 64 caracteres: minúsculas, cifras, punto, guion "
            "o guion bajo, y ni empieza ni acaba por un signo."
        )
    return None


# USERS ---------------------------------------------------------------------------------


def get_user(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == normalise_username(username)))


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == normalise_email(email)))


def get_user_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def list_users(session: Session) -> list[User]:
    return list(session.scalars(select(User).order_by(User.username)))


def count_users(session: Session) -> int:
    return session.scalar(select(func.count(User.id))) or 0


def create_user(
    session: Session,
    username: str,
    name: str,
    password_hash: str,
    email: str | None = None,
    is_admin: bool = False,
    email_verified: bool = False,
) -> User:
    username = normalise_username(username)
    user = User(
        username=username,
        email=normalise_email(email) if email else None,
        name=name or username,
        password_hash=password_hash,
        is_admin=is_admin,
        email_verified_at=now() if email_verified and email else None,
    )
    session.add(user)
    session.flush()
    return user


def set_password(session: Session, user: User, password_hash: str) -> None:
    user.password_hash = password_hash
    session.flush()


# MEMBERSHIPS ---------------------------------------------------------------------------


def membership(session: Session, workspace_id: int, user_id: int) -> Membership | None:
    return session.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == user_id
        )
    )


def grant(session: Session, workspace_id: int, user_id: int, role: str) -> Membership:
    existing = membership(session, workspace_id, user_id)
    if existing is None:
        existing = Membership(workspace_id=workspace_id, user_id=user_id)
        session.add(existing)
    existing.role = role
    session.flush()
    return existing


def revoke_membership(session: Session, workspace_id: int, user_id: int) -> None:
    existing = membership(session, workspace_id, user_id)
    if existing is not None:
        session.delete(existing)
        session.flush()


def memberships_for(session: Session, user_id: int) -> list[tuple[Membership, Workspace]]:
    rows = session.execute(
        select(Membership, Workspace)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user_id, Workspace.deleted_at.is_(None))
        .order_by(Workspace.slug)
    )
    return [(m, w) for m, w in rows]


def members_of(session: Session, workspace_id: int) -> list[tuple[Membership, User]]:
    rows = session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(User.username)
    )
    return [(m, u) for m, u in rows]


# SESSIONS ------------------------------------------------------------------------------


def create_session(
    session: Session,
    user_id: int,
    token_hash: str,
    sliding: timedelta,
    absolute: timedelta,
    ip: str | None = None,
    user_agent: str | None = None,
) -> UserSession:
    moment = now()
    row = UserSession(
        token_hash=token_hash,
        user_id=user_id,
        created_at=moment,
        last_seen_at=moment,
        expires_at=moment + sliding,
        absolute_expires_at=moment + absolute,
        ip=ip,
        user_agent=user_agent[:400] if user_agent else None,
    )
    session.add(row)
    session.flush()
    return row


# Returns the row only when it is usable *right now*: expiry, absolute expiry, revocation
# and the user's own `disabled_at` are one question, and answering it anywhere else would
# be a second place to forget one of the four.
def live_session(session: Session, token_hash: str) -> tuple[UserSession, User] | None:
    row = session.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if row is None or row.revoked_at is not None:
        return None
    moment = now()
    if row.expires_at <= moment or row.absolute_expires_at <= moment:
        return None
    user = session.get(User, row.user_id)
    if user is None or not user.active:
        return None
    return row, user


# The sliding half of the expiry. Written at most once per interval so that a page doing
# twenty requests does not do twenty updates of the same row.
def touch_session(session: Session, row: UserSession, sliding: timedelta, interval: timedelta) -> None:
    moment = now()
    if moment - row.last_seen_at < interval:
        return
    row.last_seen_at = moment
    row.expires_at = min(moment + sliding, row.absolute_expires_at)
    session.flush()


def revoke_session(session: Session, row: UserSession) -> None:
    row.revoked_at = now()
    session.flush()


def revoke_all_sessions(session: Session, user_id: int, keep: int | None = None) -> int:
    rows = list(
        session.scalars(
            select(UserSession).where(
                UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
            )
        )
    )
    moment = now()
    revoked = 0
    for row in rows:
        if keep is not None and row.id == keep:
            continue
        row.revoked_at = moment
        revoked += 1
    session.flush()
    return revoked


def active_sessions(session: Session, user_id: int) -> list[UserSession]:
    moment = now()
    return [
        row
        for row in session.scalars(
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .order_by(UserSession.last_seen_at.desc())
        )
        if row.expires_at > moment and row.absolute_expires_at > moment
    ]


# INVITES -------------------------------------------------------------------------------


def create_invite(
    session: Session,
    token_hash: str,
    ttl: timedelta,
    workspace_id: int | None = None,
    role: str = EDITOR,
    created_by: int | None = None,
) -> Invite:
    invite = Invite(
        token_hash=token_hash,
        workspace_id=workspace_id,
        role=role,
        created_by=created_by,
        expires_at=now() + ttl,
    )
    session.add(invite)
    session.flush()
    return invite


def live_invite(session: Session, token_hash: str) -> Invite | None:
    invite = session.scalar(select(Invite).where(Invite.token_hash == token_hash))
    if invite is None or invite.used_at is not None or invite.expires_at <= now():
        return None
    return invite


def consume_invite(session: Session, invite: Invite, user_id: int) -> None:
    invite.used_at = now()
    invite.used_by = user_id
    session.flush()


def pending_invites(session: Session, workspace_id: int | None = None) -> list[Invite]:
    query = select(Invite).where(Invite.used_at.is_(None), Invite.expires_at > now())
    if workspace_id is not None:
        query = query.where(Invite.workspace_id == workspace_id)
    return list(session.scalars(query.order_by(Invite.created_at.desc())))


def revoke_invite(session: Session, invite_id: int) -> bool:
    invite = session.get(Invite, invite_id)
    if invite is None or invite.used_at is not None:
        return False
    session.delete(invite)
    session.flush()
    return True


# PASSWORD RESETS -----------------------------------------------------------------------


def create_reset(session: Session, user_id: int, token_hash: str, ttl: timedelta) -> PasswordReset:
    reset = PasswordReset(token_hash=token_hash, user_id=user_id, expires_at=now() + ttl)
    session.add(reset)
    session.flush()
    return reset


def live_reset(session: Session, token_hash: str) -> PasswordReset | None:
    reset = session.scalar(select(PasswordReset).where(PasswordReset.token_hash == token_hash))
    if reset is None or reset.used_at is not None or reset.expires_at <= now():
        return None
    return reset


def consume_reset(session: Session, reset: PasswordReset) -> None:
    reset.used_at = now()
    session.flush()

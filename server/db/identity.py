"""Every query that touches a user, a session, an invite or a membership.

Kept apart from `repository.py` — which is about the instance's artifacts — because
these are the only queries on the request path of *every* endpoint, and because the
normalising boundary for an identifier has to be exactly one place: `normalise_username`
is it, so a duplicate differing in case cannot enter through a second door.
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from variatio.core import languages

from .models import (
    EDITOR,
    EVALUATOR_PROFILES,
    Invite,
    Membership,
    PasswordReset,
    User,
    UserSession,
    Workspace,
)


def now() -> datetime:
    """Return the current moment, in UTC."""
    return datetime.now(timezone.utc)


USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}[a-z0-9]$")


def normalise_username(username: str) -> str:
    """Fold a username to the one form stored and looked up: trimmed and lowercase.

    The single boundary an identifier enters through, so a duplicate differing in case
    cannot get in by a second door.
    """
    return username.strip().lower()


def normalise_email(email: str) -> str:
    """Fold an address to the one form stored and looked up: trimmed and lowercase."""
    return email.strip().lower()


def username_error(username: str) -> str | None:
    """Return why this username is not acceptable, or None.

    The one place that says what a username may be, so the web form, the invitation and
    the command line cannot disagree about it. No spaces and no `@`: the first would make
    two accounts indistinguishable on screen, the second would let a username be mistaken
    for an address in every message that prints one.
    """
    if not USERNAME_PATTERN.fullmatch(normalise_username(username)):
        return (
            "El usuario tiene entre 3 y 64 caracteres: minúsculas, cifras, punto, guion "
            "o guion bajo, y ni empieza ni acaba por un signo."
        )
    return None


def profile_error(profile: str | None) -> str | None:
    """Return why this evaluator profile is not acceptable, or None; `None` is valid.

    The same single boundary `username_error` is, and for the same reason: the command
    line, the panel and the registration form all set this, and three places deciding
    what a profile may be is three ways for them to drift. `None` means nobody said. The
    profile is not an authorisation — `require_member` never reads it.
    """
    if profile is None or profile in EVALUATOR_PROFILES:
        return None
    return f"Perfil desconocido: «{profile}». Usa uno de {', '.join(EVALUATOR_PROFILES)}."


# Not written out here: the vocabulary is `variatio.core.languages` and the pipeline reads
# it too, so a second copy would be exactly the drift the two functions above prevent.
# Unlike a profile, `None` is NOT valid — the caller resolves it rather than storing it.
language_error = languages.error


# USERS ---------------------------------------------------------------------------------


def get_user(session: Session, username: str) -> User | None:
    """Return the account with this username, or None."""
    return session.scalar(select(User).where(User.username == normalise_username(username)))


def get_user_by_email(session: Session, email: str) -> User | None:
    """Return the account with this address, or None."""
    return session.scalar(select(User).where(User.email == normalise_email(email)))


def get_user_by_id(session: Session, user_id: int) -> User | None:
    """Return the account with this id, or None."""
    return session.get(User, user_id)


def list_users(session: Session) -> list[User]:
    """Return every account, by username."""
    return list(session.scalars(select(User).order_by(User.username)))


def count_users(session: Session) -> int:
    """Return how many accounts exist."""
    return session.scalar(select(func.count(User.id))) or 0


def create_user(
    session: Session,
    username: str,
    name: str,
    password_hash: str,
    email: str | None = None,
    is_admin: bool = False,
    email_verified: bool = False,
    evaluator_profile: str | None = None,
    ui_language: str | None = None,
) -> User:
    """Insert an account and return it."""
    username = normalise_username(username)
    user = User(
        username=username,
        email=normalise_email(email) if email else None,
        name=name or username,
        password_hash=password_hash,
        is_admin=is_admin,
        email_verified_at=now() if email_verified and email else None,
        evaluator_profile=evaluator_profile,
        ui_language=languages.resolve(ui_language),
    )
    session.add(user)
    session.flush()
    return user


def set_evaluator_profile(session: Session, user: User, profile: str | None) -> User:
    """Set the account's evaluator profile, `None` included."""
    user.evaluator_profile = profile
    session.flush()
    return user


def set_ui_language(session: Session, user: User, language: str) -> User:
    """Set what language this account reads the interface in."""
    user.ui_language = languages.resolve(language)
    session.flush()
    return user


def set_password(session: Session, user: User, password_hash: str) -> None:
    """Write a new password hash, retiring every reset link still pending.

    Whoever holds one is a click away from the account, so a change made out of a
    suspicion has to close that door in the same transaction that revokes the sessions.
    The login's `needs_rehash` comes through here too, deliberately: this is the one place
    every password write passes, and the cost of closing early is one "ask for another link".
    """
    user.password_hash = password_hash
    moment = now()
    session.execute(
        update(PasswordReset)
        .where(
            PasswordReset.user_id == user.id,
            PasswordReset.used_at.is_(None),
            PasswordReset.expires_at > moment,
        )
        .values(used_at=moment)
        .execution_options(synchronize_session=False)
    )
    session.flush()


def delete_user(session: Session, user: User) -> None:
    """Delete the account row, and only the account row.

    What the account DID is not the account: `generations.user_id` and
    `evaluation_sessions.user_id` are `SET NULL`, so a course built on somebody's exercises
    survives their leaving and the evaluation keeps the sessions it counted. What cascades
    is what only means anything while the account exists — its memberships, its open
    sessions, its pending reset links and its stage forms, a verdict on a build with nobody
    behind it being impossible to read or withdraw from the panel. Disabling is the
    reversible answer; this is for an account that should not have existed.
    """
    session.delete(user)
    session.flush()


# MEMBERSHIPS ---------------------------------------------------------------------------


def membership(session: Session, workspace_id: int, user_id: int) -> Membership | None:
    """Return this account's membership of this workspace, or None."""
    return session.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == user_id
        )
    )


def grant(session: Session, workspace_id: int, user_id: int, role: str) -> Membership:
    """Give the account this role, creating the membership when it has none."""
    existing = membership(session, workspace_id, user_id)
    if existing is None:
        existing = Membership(workspace_id=workspace_id, user_id=user_id)
        session.add(existing)
    existing.role = role
    session.flush()
    return existing


def revoke_membership(session: Session, workspace_id: int, user_id: int) -> None:
    """Remove this account's membership of this workspace, if it has one."""
    existing = membership(session, workspace_id, user_id)
    if existing is not None:
        session.delete(existing)
        session.flush()


def memberships_for(session: Session, user_id: int) -> list[tuple[Membership, Workspace]]:
    """Return every live workspace this account belongs to, with its membership."""
    rows = session.execute(
        select(Membership, Workspace)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user_id, Workspace.deleted_at.is_(None))
        .order_by(Workspace.slug)
    )
    return [(m, w) for m, w in rows]


def members_of(session: Session, workspace_id: int) -> list[tuple[Membership, User]]:
    """Return every account that belongs to this workspace, with its membership."""
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
    """Open a session row for this token digest, with both of its expiries."""
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


def live_session(session: Session, token_hash: str) -> tuple[UserSession, User] | None:
    """Return the session row and its account, but only while it is usable right now.

    Expiry, absolute expiry, revocation and the account's own `disabled_at` are one
    question, and answering it anywhere else would be a second place to forget one of the
    four.
    """
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


def touch_session(session: Session, row: UserSession, sliding: timedelta, interval: timedelta) -> None:
    """Slide the expiry forward, at most once per `interval`.

    A page doing twenty requests must not do twenty updates of the same row, and the
    slide never passes the absolute expiry.
    """
    moment = now()
    if moment - row.last_seen_at < interval:
        return
    row.last_seen_at = moment
    row.expires_at = min(moment + sliding, row.absolute_expires_at)
    session.flush()


def revoke_session(session: Session, row: UserSession) -> None:
    """Revoke one session."""
    row.revoked_at = now()
    session.flush()


def count_live_sessions(session: Session, user_id: int) -> int:
    """Return how many of this account's sessions are still usable."""
    moment = now()
    return len(
        list(
            session.scalars(
                select(UserSession.id).where(
                    UserSession.user_id == user_id,
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > moment,
                    UserSession.absolute_expires_at > moment,
                )
            )
        )
    )


def revoke_all_sessions(session: Session, user_id: int) -> int:
    """Revoke every session of this account, with no exception for the caller's own.

    Every caller — logging out everywhere, changing the password, disabling an account —
    means all of them, and the one that keeps working afterwards does so because it is
    handed a brand-new session, not because it was spared.
    """
    rows = list(
        session.scalars(
            select(UserSession).where(
                UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
            )
        )
    )
    moment = now()
    for row in rows:
        row.revoked_at = moment
    session.flush()
    return len(rows)


# INVITES -------------------------------------------------------------------------------


def create_invite(
    session: Session,
    token_hash: str,
    ttl: timedelta,
    workspace_id: int | None = None,
    role: str = EDITOR,
    created_by: int | None = None,
) -> Invite:
    """Insert an invitation for this token digest."""
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
    """Return the invitation only while it is unused and unexpired."""
    invite = session.scalar(select(Invite).where(Invite.token_hash == token_hash))
    if invite is None or invite.used_at is not None or invite.expires_at <= now():
        return None
    return invite


def claim_invite(session: Session, invite: Invite) -> bool:
    """Claim the invitation, True only for the caller that actually got it.

    The single use is decided by the database and not by the `live_invite` that read the
    row a moment ago: hashing a password takes a fifth of a second, and two people
    redeeming the same link inside that window both pass the read. The conditional UPDATE
    is the whole claim — the second matches no row, because the first has already written
    `used_at` — so the caller does everything else only after this returns True.
    """
    result = session.execute(
        update(Invite)
        .where(Invite.id == invite.id, Invite.used_at.is_(None))
        .values(used_at=now())
        .execution_options(synchronize_session=False)
    )
    session.flush()
    return result.rowcount == 1


def attribute_invite(session: Session, invite: Invite, user_id: int) -> None:
    """Point a claimed invitation at the account it created.

    The other half of `claim_invite`: `used_by` is a foreign key, and the row had to be
    claimed before the account existed.
    """
    invite.used_by = user_id
    session.flush()


def pending_invites(session: Session, workspace_id: int | None = None) -> list[Invite]:
    """Return the unused, unexpired invitations, newest first."""
    query = select(Invite).where(Invite.used_at.is_(None), Invite.expires_at > now())
    if workspace_id is not None:
        query = query.where(Invite.workspace_id == workspace_id)
    return list(session.scalars(query.order_by(Invite.created_at.desc())))


def revoke_invite(session: Session, invite_id: int) -> bool:
    """Delete an unused invitation; False when it is missing or already redeemed."""
    invite = session.get(Invite, invite_id)
    if invite is None or invite.used_at is not None:
        return False
    session.delete(invite)
    session.flush()
    return True


# PASSWORD RESETS -----------------------------------------------------------------------


def create_reset(session: Session, user_id: int, token_hash: str, ttl: timedelta) -> PasswordReset:
    """Insert a password-reset row for this token digest."""
    reset = PasswordReset(token_hash=token_hash, user_id=user_id, expires_at=now() + ttl)
    session.add(reset)
    session.flush()
    return reset


def live_reset(session: Session, token_hash: str) -> PasswordReset | None:
    """Return the reset only while it is unused and unexpired."""
    reset = session.scalar(select(PasswordReset).where(PasswordReset.token_hash == token_hash))
    if reset is None or reset.used_at is not None or reset.expires_at <= now():
        return None
    return reset


def consume_reset(session: Session, reset: PasswordReset) -> None:
    """Mark the reset used."""
    reset.used_at = now()
    session.flush()

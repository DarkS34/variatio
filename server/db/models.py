from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Postgres is the only supported deployment target and gets JSONB; the plain-JSON variant
# exists so the import/export logic can be exercised against SQLite without a server. It
# does not change a single line of the Postgres DDL.
Json = JSON().with_variant(JSONB(), "postgresql")

DRAFT = "draft"
CURATED = "curated"

SLOT_CORPUS = "corpus"
SLOT_EXEMPLARS = "exemplars"

VIEWER = "viewer"
EDITOR = "editor"
OWNER = "owner"

# Ordered, because every authorisation check is "at least this much": `require_member`
# compares ranks, so a new role only has to be inserted at the right position here.
ROLE_RANK: dict[str, int] = {VIEWER: 0, EDITOR: 1, OWNER: 2}
ROLES: tuple[str, ...] = (VIEWER, EDITOR, OWNER)


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    raw_documents: Mapped[list["RawDocument"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


# One row per saved version, never an update in place: that is what turns the `.history/`
# directory into queryable data and makes undo a select rather than a file copy. `stage`
# keeps the draft/curated split the UI badges — collapsing them was declined explicitly.
class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "kind", "stage", "version", name="uq_artifact_version"),
        Index("ix_artifact_current", "workspace_id", "kind", "stage", "version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    stage: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(Json)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped[Workspace] = relationship(back_populates="artifacts")


# The `.review_state.json` translated one-to-one: `upstream_hashes` is what lets an
# approval go stale when something it was derived from changes, which is the whole
# point of the gate. One approval per (workspace, kind) — approving again replaces it.
class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (UniqueConstraint("workspace_id", "kind", name="uq_approval_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    artifact_id: Mapped[int | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="SET NULL"), default=None
    )
    sha256: Mapped[str] = mapped_column(String(64))
    upstream_hashes: Mapped[dict] = mapped_column(Json, default=dict)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workspace: Mapped[Workspace] = relationship(back_populates="approvals")


# The bytes stay outside the database — disk today, object storage later — and only the
# metadata lives here, because that is what the UI lists and what the quotas count.
class RawDocument(Base):
    __tablename__ = "raw_documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slot", "filename", name="uq_raw_document_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    slot: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(255))
    bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped[Workspace] = relationship(back_populates="raw_documents")


# IDENTITY ------------------------------------------------------------------------------


# The plan asks for `email citext`; a plain string with a single normalising boundary
# (`identity.normalise_email`, the only way an address enters or is looked up) answers the
# same question — no duplicates differing in case — without a Postgres extension, which
# would also be the one line of DDL that SQLite could not run.
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def active(self) -> bool:
        return self.disabled_at is None


# The authorisation question reduced to one row: is there a membership, and what does it
# say? Nothing else in the request path may answer it — an admin flag is about running the
# installation, not about reading someone else's workspace.
class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped[Workspace] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


# Opaque server-side session, stored as the SHA-256 of the token the browser holds: a
# database dump yields no usable session. Two expiries, not one — `expires_at` slides with
# use, `absolute_expires_at` does not, so a stolen cookie cannot be renewed forever.
class UserSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(400), default=None)

    user: Mapped[User] = relationship()


# There is no open registration: an account exists because someone with a workspace or the
# installation's administrator issued one of these. Single use, hashed, with an expiry.
class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), default=None)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), default=None, index=True
    )
    role: Mapped[str] = mapped_column(String(16), default=EDITOR)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    used_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    workspace: Mapped[Workspace | None] = relationship()


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

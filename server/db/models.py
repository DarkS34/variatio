from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
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
    generations: Mapped[list["Generation"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["EvalSession"]] = relationship(
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
# (`identity.normalise_username`, the only way an identifier enters or is looked up) answers
# the same question — no duplicates differing in case — without a Postgres extension, which
# would also be the one line of DDL that SQLite could not run.
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Who you are here, and what you type to enter. Delivery is by hand in this
    # installation, so an address is no longer the identity: it cannot be, because an
    # account that never receives mail would have nothing to be called.
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Optional, and only ever a delivery address for a link. `unique=True` on a nullable
    # column is exactly what is wanted: Postgres lets many rows be NULL and still refuses
    # two accounts with the same address.
    email: Mapped[str | None] = mapped_column(
        String(320), unique=True, index=True, default=None
    )
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Which workspace this account lands in when a browser arrives with no preference of
    # its own. It is a *preference*, never an authorisation: `require_member` looks up the
    # membership regardless of what this says, so a stale pointer costs a 403 and not a
    # read of somebody else's instance. On the account rather than on the session row so
    # it survives a login, while the `X-Workspace` header keeps two tabs independent.
    active_workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), default=None
    )
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


# WHAT THE SYSTEM PRODUCED ----------------------------------------------------------------


# One row per validated item, not one per job: a run of `n=5` is five things to read back,
# and the reason to keep them is that generating one costs a minute of GPU nobody wants to
# pay twice. `item` is `jsonb` rather than columns because its shape is the exemplars
# profile's, which the user edits — a variant has to survive the schema that made it.
#
# `user_id` is `SET NULL` and not `CASCADE`: deleting an account must not silently delete
# the material a course was built on. The workspace is what cascades.
class Generation(Base):
    __tablename__ = "generations"
    __table_args__ = (
        Index("ix_generation_recent", "workspace_id", "created_at"),
        Index("ix_generation_author", "workspace_id", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    item_type: Mapped[str] = mapped_column(String(64), default="")
    concepts: Mapped[list] = mapped_column(Json, default=list)
    curriculum: Mapped[list] = mapped_column(Json, default=list)
    fixed: Mapped[dict] = mapped_column(Json, default=dict)
    instructions: Mapped[str | None] = mapped_column(Text, default=None)
    think: Mapped[bool] = mapped_column(Boolean, default=True)
    item: Mapped[dict] = mapped_column(Json, default=dict)
    thinking: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped[Workspace] = relationship(back_populates="generations")
    user: Mapped[User | None] = relationship()


# The blind comparison, which used to live in `instance/.evaluations/*.json` with no idea
# who ran it. That was tolerable with one user and is the whole question with several:
# the study's unit is a session, and a session without an evaluator cannot be grouped by
# account, which is exactly what the analysis needs.
#
# The header columns are queried (the aggregates group by them); `trace` holds the full
# `EvaluationSession.to_dict()` — three prompts, three raw answers, exemplars, timings —
# and is only read when one session is opened. Same split the two files had, one table.
class EvalSession(Base):
    __tablename__ = "evaluation_sessions"
    __table_args__ = (Index("ix_evaluation_recent", "workspace_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item_type: Mapped[str] = mapped_column(String(64), default="")
    concepts: Mapped[list] = mapped_column(Json, default=list)
    curriculum: Mapped[list] = mapped_column(Json, default=list)
    fixed: Mapped[dict] = mapped_column(Json, default=dict)
    instructions: Mapped[str | None] = mapped_column(Text, default=None)
    seed: Mapped[int] = mapped_column(BigInteger, default=0)
    shuffle: Mapped[list] = mapped_column(Json, default=list)
    think: Mapped[bool] = mapped_column(Boolean, default=True)

    choice: Mapped[int | None] = mapped_column(Integer, default=None)
    choice_arm: Mapped[str | None] = mapped_column(String(16), default=None, index=True)
    chosen_at: Mapped[float | None] = mapped_column(Float, default=None)
    evaluator_note: Mapped[str | None] = mapped_column(Text, default=None)
    rating: Mapped[dict | None] = mapped_column(Json, default=None)

    arm_status: Mapped[dict] = mapped_column(Json, default=dict)
    arm_elapsed_ms: Mapped[dict] = mapped_column(Json, default=dict)
    trace: Mapped[dict] = mapped_column(Json, default=dict)

    workspace: Mapped[Workspace] = relationship(back_populates="evaluations")
    user: Mapped[User | None] = relationship()

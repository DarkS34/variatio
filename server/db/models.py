"""The tables, as SQLAlchemy models.

`Json` is plain `JSON` with a `JSONB` variant for Postgres, which is the only supported
deployment target: the plain half exists so import/export can be exercised against SQLite
without a server, and it changes no line of the Postgres DDL.
"""

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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

# An invitation's alias is a name for a row, not a note.
INVITE_LABEL_MAX = 120


class Base(DeclarativeBase):
    """The declarative base every table hangs from."""


class Workspace(Base):
    """One instance: a slug, and everything that belongs to it.

    `prompt_language` is what this instance's PROMPTS are written in — not what its
    material is written in, which `content_context.json` carries and the corpus decides.
    It is a MIRROR of `instance/locale.json` and never the truth: the pipeline runs from
    the command line with no database, so a build reads the file, and the column is here
    so the panel can list the instances without touching disk.
    """

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    prompt_language: Mapped[str] = mapped_column(String(8), default="es", server_default="es")
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
    stage_evaluations: Mapped[list["StageEvaluation"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Artifact(Base):
    """One saved version of one artifact, keyed `(workspace, kind, stage, version)`.

    A row per saved version and never an update in place: that is what turns the
    `.history/` directory into queryable data and makes undo a select rather than a file
    copy. `stage` keeps the draft/curated split the UI badges.
    """

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


class Approval(Base):
    """`.review_state.json` translated one to one: one approval per (workspace, kind).

    `upstream_hashes` is what lets an approval go stale when something it was derived
    from changes, which is the whole point of the gate. Approving again replaces the row.
    """

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


class RawDocument(Base):
    """The metadata of one raw document; its bytes stay outside the database.

    Disk today, object storage later. What lives here is what the UI lists and what the
    quotas count.
    """

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


class User(Base):
    """One account: what it types to enter, and the preferences hanging off it.

    The identity is the `username` and never an address — delivery is by hand here, so an
    account that never receives mail would otherwise have nothing to be called. `email`
    is optional and only ever a delivery address for a link; `unique=True` on a nullable
    column is exactly what is wanted, since Postgres lets many rows be NULL and still
    refuses two accounts with the same address. A plain string rather than `citext`:
    `identity.normalise_username` is the one door an identifier enters or is looked up
    through, which answers the same question without an extension SQLite could not run.

    `evaluator_profile` is a column the study's migrations built and this branch never
    reads or writes: it stays NULL, and stays declared so the model keeps describing the
    database. `ui_language` is what this person READS — the interface,
    the guide, the errors — and is deliberately a different axis from a workspace's
    `prompt_language`; NOT NULL, because there is no such thing as reading no language.
    `active_workspace_id` is a *preference* and never an authorisation: `require_member`
    looks up the membership whatever it says, so a stale pointer costs a 403 and not a
    read of somebody else's instance. It sits on the account rather than on the session
    so it survives a login, while the `X-Workspace` header keeps two tabs independent.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(
        String(320), unique=True, index=True, default=None
    )
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    evaluator_profile: Mapped[str | None] = mapped_column(String(16), default=None)
    ui_language: Mapped[str] = mapped_column(String(8), default="es", server_default="es")
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    active_workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def active(self) -> bool:
        """True while the account has not been disabled."""
        return self.disabled_at is None


class Membership(Base):
    """The authorisation question as one row: is there a membership, and what does it say?

    Nothing else in the request path may answer it — an admin flag is about running the
    installation, not about reading someone else's workspace.
    """

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


class UserSession(Base):
    """An opaque server-side session, stored as the SHA-256 of the token the browser holds.

    A database dump therefore yields no usable session. Two expiries, not one:
    `expires_at` slides with use and `absolute_expires_at` does not, so a stolen cookie
    cannot be renewed for ever.
    """

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


class Invite(Base):
    """A single-use invitation: looked up by digest, with an expiry.

    There is no open registration — an account exists because the installation's
    administrator issued one of these, or because it was the first and came from the CLI.

    `label` is the administrator's own name for it and never reaches the person holding
    the link. `token_sealed` is the token encrypted with a key kept outside the database
    (`server/auth/links.py`), so the panel can show the link again; it is emptied the
    moment the invitation is used, and it is NULL on every row minted before it existed.
    """

    __tablename__ = "invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_sealed: Mapped[str | None] = mapped_column(String(255), default=None)
    label: Mapped[str | None] = mapped_column(String(INVITE_LABEL_MAX), default=None)
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
    """A single-use password-reset link: hashed, with an expiry."""

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


# WHAT THE SYSTEM PRODUCED ----------------------------------------------------------------


class Generation(Base):
    """One validated item, with the commission that produced it — a row per item, not per job.

    A run of `n=5` is five things to read back, and generating one costs a minute of GPU
    nobody wants to pay twice. `item` is JSON rather than columns because its shape is the
    exemplars profile's, which the user edits: an exercise has to survive the schema that
    made it. `model` is the one that WROTE it and never the one the installation offers
    today — the commission chooses, and two models differ by minutes and by how much they
    deliberate, so a row that does not name one cannot be read beside the next. `user_id` is
    `SET NULL` and not `CASCADE`: deleting an account must not silently delete the material
    a course was built on. The workspace is what cascades.
    """

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
    item_type: Mapped[str] = mapped_column(String(64), default="", server_default="")
    concepts: Mapped[list] = mapped_column(Json, default=list)
    curriculum: Mapped[list] = mapped_column(Json, default=list)
    fixed: Mapped[dict] = mapped_column(Json, default=dict)
    instructions: Mapped[str | None] = mapped_column(Text, default=None)
    think: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    model: Mapped[str | None] = mapped_column(String(128), default=None)
    item: Mapped[dict] = mapped_column(Json, default=dict)
    thinking: Mapped[str | None] = mapped_column(Text, default=None)
    checks: Mapped[dict | None] = mapped_column(Json, default=None)
    promoted_item_id: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped[Workspace] = relationship(back_populates="generations")
    user: Mapped[User | None] = relationship()


class EvalSession(Base):
    """One blind comparison of the study, which this branch neither reads nor writes.

    The table exists because the migrations built it and an installation may hold rows
    written by the branch that runs the study; the model stays so `alembic autogenerate`
    keeps answering zero and a shared database can serve either branch. Nothing under
    `server/` queries it.
    """

    __tablename__ = "evaluation_sessions"
    __table_args__ = (
        Index("ix_evaluation_recent", "workspace_id", "created_at"),
        Index("ix_evaluation_set", "set_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None, index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    set_id: Mapped[str | None] = mapped_column(String(32), default=None)
    assigned_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )

    item_type: Mapped[str] = mapped_column(String(64), default="", server_default="")
    concepts: Mapped[list] = mapped_column(Json, default=list)
    curriculum: Mapped[list] = mapped_column(Json, default=list)
    fixed: Mapped[dict] = mapped_column(Json, default=dict)
    instructions: Mapped[str | None] = mapped_column(Text, default=None)
    seed: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    shuffle: Mapped[list] = mapped_column(Json, default=list)
    think: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    # Nullable in the database since 0007 added it to a table that already had rows.
    triage: Mapped[dict] = mapped_column(Json, default=dict, nullable=True)

    choice: Mapped[int | None] = mapped_column(Integer, default=None)
    choice_arm: Mapped[str | None] = mapped_column(String(16), default=None, index=True)
    chosen_at: Mapped[float | None] = mapped_column(Float, default=None)
    evaluator_note: Mapped[str | None] = mapped_column(Text, default=None)
    rating: Mapped[dict | None] = mapped_column(Json, default=None)

    opened_at: Mapped[float | None] = mapped_column(Float, default=None)
    declined_at: Mapped[float | None] = mapped_column(Float, default=None)

    arm_status: Mapped[dict] = mapped_column(Json, default=dict)
    arm_elapsed_ms: Mapped[dict] = mapped_column(Json, default=dict)
    trace: Mapped[dict] = mapped_column(Json, default=dict)

    workspace: Mapped[Workspace] = relationship(back_populates="evaluations")
    # Spelled out because `assigned_by` is a second path to `users` and SQLAlchemy will
    # not guess: `user` is who judges, `assigner` is who handed it over.
    user: Mapped[User | None] = relationship(foreign_keys=[user_id])
    assigner: Mapped[User | None] = relationship(foreign_keys=[assigned_by])


class StageEvaluation(Base):
    """One stage questionnaire of the study, which this branch neither reads nor writes.

    Kept for the reason `EvalSession` is: the migrations built the table, and the model
    describes the database rather than what this branch uses of it.
    """

    __tablename__ = "stage_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            "artifact",
            "artifact_hash",
            name="uq_stage_evaluation_build",
        ),
        Index("ix_stage_evaluation_recent", "workspace_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), default=None, index=True
    )

    artifact: Mapped[str] = mapped_column(String(32), index=True)
    artifact_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    job_id: Mapped[str | None] = mapped_column(String(32), default=None)
    instrument: Mapped[str] = mapped_column(String(16), default="", server_default="")

    answers: Mapped[dict] = mapped_column(Json, default=dict, server_default="{}")
    overall: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    note: Mapped[str | None] = mapped_column(Text, default=None)

    curated: Mapped[bool | None] = mapped_column(Boolean, default=None)

    opened_at: Mapped[float | None] = mapped_column(Float, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    workspace: Mapped[Workspace] = relationship(back_populates="stage_evaluations")
    user: Mapped[User | None] = relationship()

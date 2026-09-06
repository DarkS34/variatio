"""Every query over a workspace, its artifacts, its approvals and its raw documents.

Artifacts are versioned rows keyed `(workspace, kind, stage, version)` and never updated
in place; approvals are one row per (workspace, kind). The queries over accounts live in
`identity.py`, and those over what the system produced in `generations.py`.
"""

import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from variatio.core import languages

from .models import CURATED, DRAFT, Approval, Artifact, RawDocument, Workspace


def content_sha256(content) -> str:
    """Hash content exactly as the same artifact would be hashed on disk.

    Byte-identical to what `storage.write_json`, `entrypoints.save_bank` and
    `source_docs.save_json` write, verified against all four artifacts of the reference
    instance. Nothing *depends* on that agreement — `instance_io` re-derives hashes
    rather than trusting it — but it is what makes the two storage backends comparable,
    so do not change the separators or the indent casually.
    """
    payload = json.dumps(content, ensure_ascii=False, indent=2)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# WORKSPACES ----------------------------------------------------------------------------


def list_workspaces(session: Session) -> list[Workspace]:
    """Return every workspace that has not been deleted, by slug."""
    return list(
        session.scalars(
            select(Workspace).where(Workspace.deleted_at.is_(None)).order_by(Workspace.slug)
        )
    )


def ensure_workspace(session: Session, slug: str, name: str | None = None) -> Workspace:
    """Return this workspace, creating it when it does not exist yet."""
    return get_workspace(session, slug) or create_workspace(session, slug, name)


def get_workspace(session: Session, slug: str) -> Workspace | None:
    """Return the workspace with this slug, or None when it is missing or deleted."""
    return session.scalar(
        select(Workspace).where(Workspace.slug == slug, Workspace.deleted_at.is_(None))
    )


def create_workspace(
    session: Session, slug: str, name: str | None = None, prompt_language: str | None = None
) -> Workspace:
    """Insert a workspace row and return it."""
    workspace = Workspace(
        slug=slug, name=name or slug, prompt_language=languages.resolve(prompt_language)
    )
    session.add(workspace)
    session.flush()
    return workspace


# ARTIFACTS -----------------------------------------------------------------------------


def current_artifact(session: Session, workspace_id: int, kind: str) -> Artifact | None:
    """Return the curated version of an artifact, or the draft when there is none.

    The same rule `entrypoints._artifacts` applies to files, so both storage backends answer
    identically.
    """
    return latest_artifact(session, workspace_id, kind, CURATED) or latest_artifact(
        session, workspace_id, kind, DRAFT
    )


def save_artifact(
    session: Session, workspace_id: int, kind: str, stage: str, content
) -> Artifact:
    """Save this content as the next version of an artifact, or return the identical one.

    An identical save is not a new version: re-running a build that produced the same
    bytes must not push a row that makes every approval look outdated.
    """
    digest = content_sha256(content)
    previous = latest_artifact(session, workspace_id, kind, stage)

    if previous is not None and previous.sha256 == digest:
        return previous

    next_version = (
        session.scalar(
            select(func.coalesce(func.max(Artifact.version), 0)).where(
                Artifact.workspace_id == workspace_id,
                Artifact.kind == kind,
                Artifact.stage == stage,
            )
        )
        or 0
    ) + 1

    artifact = Artifact(
        workspace_id=workspace_id,
        kind=kind,
        stage=stage,
        version=next_version,
        content=content,
        sha256=digest,
    )
    session.add(artifact)
    session.flush()
    return artifact


def latest_artifact(
    session: Session, workspace_id: int, kind: str, stage: str
) -> Artifact | None:
    """Return the highest version of one artifact at one stage."""
    return session.scalar(
        select(Artifact)
        .where(
            Artifact.workspace_id == workspace_id,
            Artifact.kind == kind,
            Artifact.stage == stage,
        )
        .order_by(Artifact.version.desc())
        .limit(1)
    )


def artifact_versions(session: Session, workspace_id: int, kind: str) -> list[Artifact]:
    """Return every saved version of an artifact, newest first."""
    return list(
        session.scalars(
            select(Artifact)
            .where(Artifact.workspace_id == workspace_id, Artifact.kind == kind)
            .order_by(Artifact.created_at.desc())
        )
    )


# APPROVALS -----------------------------------------------------------------------------


def approve(
    session: Session,
    workspace_id: int,
    kind: str,
    sha256: str,
    upstream_hashes: dict,
    artifact_id: int | None = None,
) -> Approval:
    """Record an approval of this kind, replacing whatever was recorded before."""
    approval = get_approval(session, workspace_id, kind)
    if approval is None:
        approval = Approval(workspace_id=workspace_id, kind=kind)
        session.add(approval)
    approval.sha256 = sha256
    approval.upstream_hashes = upstream_hashes
    approval.artifact_id = artifact_id
    approval.approved_at = func.now()
    session.flush()
    return approval


def reopen(session: Session, workspace_id: int, kind: str) -> None:
    """Delete this kind's approval, which is what reopening a stage means."""
    approval = get_approval(session, workspace_id, kind)
    if approval is not None:
        session.delete(approval)
        session.flush()


def get_approval(session: Session, workspace_id: int, kind: str) -> Approval | None:
    """Return this kind's approval, or None when it is not approved."""
    return session.scalar(
        select(Approval).where(Approval.workspace_id == workspace_id, Approval.kind == kind)
    )


# RAW DOCUMENTS -------------------------------------------------------------------------


def list_raw_documents(session: Session, workspace_id: int, slot: str) -> list[RawDocument]:
    """Return the registered documents of one raw slot, by filename."""
    return list(
        session.scalars(
            select(RawDocument)
            .where(RawDocument.workspace_id == workspace_id, RawDocument.slot == slot)
            .order_by(RawDocument.filename)
        )
    )


def register_raw_document(
    session: Session,
    workspace_id: int,
    slot: str,
    filename: str,
    size: int,
    sha256: str,
    object_key: str,
) -> RawDocument:
    """Record one raw document's metadata, updating the row when it already exists."""
    document = session.scalar(
        select(RawDocument).where(
            RawDocument.workspace_id == workspace_id,
            RawDocument.slot == slot,
            RawDocument.filename == filename,
        )
    )
    if document is None:
        document = RawDocument(workspace_id=workspace_id, slot=slot, filename=filename)
        session.add(document)
    document.bytes = size
    document.sha256 = sha256
    document.object_key = object_key
    session.flush()
    return document


def forget_raw_document(session: Session, workspace_id: int, slot: str, filename: str) -> None:
    """Drop one raw document's row, if it has one."""
    document = session.scalar(
        select(RawDocument).where(
            RawDocument.workspace_id == workspace_id,
            RawDocument.slot == slot,
            RawDocument.filename == filename,
        )
    )
    if document is not None:
        session.delete(document)
        session.flush()

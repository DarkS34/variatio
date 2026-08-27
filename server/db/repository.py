import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from variatio.core import languages

from .models import CURATED, DRAFT, Approval, Artifact, RawDocument, Workspace


# Byte-identical to what `storage.write_json`, `stages.save_bank` and `_source_docs.save_json`
# put on disk, so a file hash and a content hash of the same artifact agree. Verified against
# all four artifacts of the reference instance. Nothing *depends* on that agreement —
# `instance_io` re-derives hashes rather than trusting it — but keeping it makes the two
# storage backends comparable, so do not change the separators or the indent casually.
def content_sha256(content) -> str:
    payload = json.dumps(content, ensure_ascii=False, indent=2)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# WORKSPACES ----------------------------------------------------------------------------


def get_workspace(session: Session, slug: str) -> Workspace | None:
    return session.scalar(
        select(Workspace).where(Workspace.slug == slug, Workspace.deleted_at.is_(None))
    )


def list_workspaces(session: Session) -> list[Workspace]:
    return list(
        session.scalars(
            select(Workspace).where(Workspace.deleted_at.is_(None)).order_by(Workspace.slug)
        )
    )


def create_workspace(
    session: Session, slug: str, name: str | None = None, prompt_language: str | None = None
) -> Workspace:
    workspace = Workspace(
        slug=slug, name=name or slug, prompt_language=languages.resolve(prompt_language)
    )
    session.add(workspace)
    session.flush()
    return workspace


def ensure_workspace(session: Session, slug: str, name: str | None = None) -> Workspace:
    return get_workspace(session, slug) or create_workspace(session, slug, name)


# ARTIFACTS -----------------------------------------------------------------------------


def latest_artifact(
    session: Session, workspace_id: int, kind: str, stage: str
) -> Artifact | None:
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


# The curated version wins when it exists, the draft is the fallback — the same rule
# `stages._artifacts` applies to files, so both storage backends answer identically.
def current_artifact(session: Session, workspace_id: int, kind: str) -> Artifact | None:
    return latest_artifact(session, workspace_id, kind, CURATED) or latest_artifact(
        session, workspace_id, kind, DRAFT
    )


def save_artifact(
    session: Session, workspace_id: int, kind: str, stage: str, content
) -> Artifact:
    digest = content_sha256(content)
    previous = latest_artifact(session, workspace_id, kind, stage)

    # An identical save is not a new version: re-running a build that produced the same
    # bytes should not push a row that makes every approval look outdated.
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


def artifact_versions(session: Session, workspace_id: int, kind: str) -> list[Artifact]:
    return list(
        session.scalars(
            select(Artifact)
            .where(Artifact.workspace_id == workspace_id, Artifact.kind == kind)
            .order_by(Artifact.created_at.desc())
        )
    )


# APPROVALS -----------------------------------------------------------------------------


def get_approval(session: Session, workspace_id: int, kind: str) -> Approval | None:
    return session.scalar(
        select(Approval).where(Approval.workspace_id == workspace_id, Approval.kind == kind)
    )


def approve(
    session: Session,
    workspace_id: int,
    kind: str,
    sha256: str,
    upstream_hashes: dict,
    artifact_id: int | None = None,
) -> Approval:
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
    approval = get_approval(session, workspace_id, kind)
    if approval is not None:
        session.delete(approval)
        session.flush()


# RAW DOCUMENTS -------------------------------------------------------------------------


def list_raw_documents(session: Session, workspace_id: int, slot: str) -> list[RawDocument]:
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

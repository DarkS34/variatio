"""The installation's own panel: the accounts, the workspaces and how the study is going.

This router is the documented exception to phase 2's «an administrator runs the
installation, they do not read other people's instances». Taken by explicit user request
in phase 3, because the evaluation is a study whose unit of analysis is a session and
whose interesting question — «¿va ganando el sistema, y con qué evaluadores?» — cannot be
answered from inside one account. The bypass lives in `auth.deps.access_for`, one `if`,
and every route here is behind `require_admin`.

What it is NOT: a second way into the pipeline. Nothing here builds, edits or approves
anything. It reads what the installation has recorded, hands out access, and exports a CSV.

Handing out access is new: issuing invitations and moving people between workspaces used
to be an owner's job, done from a dialog in the account menu, while this panel listed the
same accounts and could only enable or disable them. Two screens for one question is how
you end up with two answers, so they are one — this one — and only the installation's
administrator gets it, by explicit user request. An owner still owns their workspace's
content; they no longer decide who else exists.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from variant_generator.evaluation import ARM_LABELS, ARMS

from .. import auth, deps, evaluation_store, review, runtime, settings
from ..auth.rate_limit import throttle
from ..db import identity, repository, study
from ..db.models import EDITOR, ROLES, Invite, User

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class InviteBody(BaseModel):
    """`workspace` is a slug, or nothing: an invitation that grants no membership creates
    an account and no access, which is the honest way to add someone who will be given a
    workspace later."""

    workspace: str | None = None
    role: str = EDITOR


class MembershipBody(BaseModel):
    workspace: str
    role: str = EDITOR


# WHO AND WHAT ----------------------------------------------------------------------------


@router.get("/overview")
def overview(db: DbSession = Depends(auth.db)) -> dict:
    workspaces = repository.list_workspaces(db)
    users = identity.list_users(db)
    generated = study.generations_per_user(db)
    headers = _headers(db)
    by_account = {group["key"]: group for group in evaluation_store.by_account(headers)}

    running = runtime.runner.current()
    return {
        "totals": {
            "users": len(users),
            "workspaces": len(workspaces),
            "generations": study.count_generations(db),
            "evaluations": len(headers),
            "decided": sum(1 for h in headers if h.get("chosen_at")),
        },
        "accounts": [
            {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "is_admin": user.is_admin,
                "disabled": not user.active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "workspaces": [
                    {"slug": w.slug, "role": m.role}
                    for m, w in identity.memberships_for(db, user.id)
                ],
                "generations": generated.get(user.id, 0),
                "evaluations": by_account.get(user.id, {}).get("sessions", 0),
                "decided": by_account.get(user.id, {}).get("decided", 0),
            }
            for user in users
        ],
        "workspaces": [
            {
                "id": workspace.id,
                "slug": workspace.slug,
                "name": workspace.name,
                "created_at": workspace.created_at.isoformat()
                if workspace.created_at
                else None,
                "members": len(identity.members_of(db, workspace.id)),
                "generations": study.count_generations(db, workspace.id),
                "warm": workspace.slug in deps.warm_slugs(),
                # La cadena de cada instancia, para poder vaciar una etapa desde aquí sin
                # cambiarse a ella. Es leer tres ficheros por workspace, no montar su índice.
                "stages": _chain(workspace.slug),
            }
            for workspace in workspaces
        ],
        "engine": {
            "busy": running is not None,
            "job": running.to_dict() if running else None,
            "queued": len(runtime.runner.pending()),
            "warm_contexts": deps.warm_slugs(),
        },
    }


# THE STUDY -------------------------------------------------------------------------------


@router.get("/evaluations")
def evaluations(
    workspace: str | None = None,
    account: int | None = None,
    db: DbSession = Depends(auth.db),
) -> dict:
    headers = _headers(db, workspace=workspace)
    if account is not None:
        headers = [h for h in headers if h.get("account_id") == account]

    return {
        "aggregates": evaluation_store.aggregates(headers),
        "by_account": evaluation_store.by_account(headers),
        "by_workspace": evaluation_store.by_workspace(headers),
        "per_day": evaluation_store.per_day(headers),
        "arms": [{"key": arm, "label": ARM_LABELS[arm]} for arm in ARMS],
        "filters": {
            "workspace": workspace,
            "account": account,
            "workspaces": sorted({h["workspace"] for h in _headers(db) if h["workspace"]}),
        },
        # Newest first, and every one openable: the point of the panel is being able to
        # go from «este evaluador nunca elige el sistema» to the sessions that say so.
        "sessions": [_row(h) for h in sorted(
            headers, key=lambda h: h.get("created_at") or 0, reverse=True
        )],
    }


@router.get("/evaluations/export.csv")
def export(
    workspace: str | None = None,
    account: int | None = None,
    db: DbSession = Depends(auth.db),
) -> Response:
    headers = _headers(db, workspace=workspace)
    if account is not None:
        headers = [h for h in headers if h.get("account_id") == account]
    return Response(
        content=evaluation_store.export_csv(headers),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="evaluaciones.csv"'},
    )


# The full trace of one session, reveal included. An administrator reading this is reading
# research data they are entitled to; the evaluator's own blinding is unaffected, because
# nothing here writes and the session is already judged or already theirs to judge.
@router.get("/evaluations/{session_id}")
def session_detail(session_id: str, db: DbSession = Depends(auth.db)) -> dict:
    row = study.get_evaluation(db, session_id)
    if row is None:
        raise HTTPException(404, f"No existe la sesión '{session_id}'.")
    return {
        "session": row.trace,
        "workspace": row.workspace.slug if row.workspace else None,
        "account": row.user.username if row.user else None,
    }


# ACCESS ----------------------------------------------------------------------------------
#
# The only way an account comes into existence, and the only way one enters a workspace.


@router.get("/invites")
def invites(db: DbSession = Depends(auth.db)) -> dict:
    return {"invites": [_invite(db, row) for row in identity.pending_invites(db)]}


@router.post("/invites", status_code=201)
def create_invite(
    body: InviteBody,
    request: Request,
    admin: User = Depends(auth.require_admin),
    db: DbSession = Depends(auth.db),
) -> dict:
    # An administrator session is not a licence to mint credentials without limit, and the
    # bucket already existed for the owner-scoped route this replaces.
    throttle("invite", request, admin.username)
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'. Usa uno de {', '.join(ROLES)}.")

    workspace = None
    if body.workspace:
        workspace = repository.get_workspace(db, body.workspace)
        if workspace is None:
            raise HTTPException(404, f"No existe el workspace '{body.workspace}'.")

    token = auth.new_token()
    invite = identity.create_invite(
        db,
        token_hash=auth.digest(token),
        ttl=settings.INVITE_TTL,
        workspace_id=workspace.id if workspace else None,
        role=body.role,
        created_by=admin.id,
    )

    # The link IS the invitation: single-use, expiring, and handed over by whoever issued
    # it. There is no address bound to it, so the person redeeming it chooses their own
    # username — which is why it must not be left anywhere its holder was not meant to be.
    return {
        "invite": _invite(db, invite),
        "link": f"{auth.base_url(request)}/invitacion?token={token}",
    }


@router.delete("/invites/{invite_id}")
def revoke_invite(invite_id: int, db: DbSession = Depends(auth.db)) -> dict:
    invite = db.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(404, "Esa invitación no existe.")
    return {"revoked": identity.revoke_invite(db, invite_id)}


@router.post("/accounts/{user_id}/memberships")
def grant_membership(
    user_id: int, body: MembershipBody, db: DbSession = Depends(auth.db)
) -> dict:
    if body.role not in ROLES:
        raise HTTPException(422, f"Rol desconocido: '{body.role}'.")
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    workspace = repository.get_workspace(db, body.workspace)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{body.workspace}'.")

    identity.grant(db, workspace.id, user.id, body.role)
    return {"user_id": user.id, "workspace": workspace.slug, "role": body.role}


@router.delete("/accounts/{user_id}/memberships/{slug}")
def revoke_membership(user_id: int, slug: str, db: DbSession = Depends(auth.db)) -> dict:
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
    identity.revoke_membership(db, workspace.id, user_id)
    return {"user_id": user_id, "workspace": slug}


# WORKSPACES ------------------------------------------------------------------------------
#
# Lo único que este panel escribe sobre las instancias, y es borrado: no construye, no
# edita y no aprueba nada. Está aquí y no en `/api/workspaces` porque aquello exige ser
# miembro del workspace activo — cuando lo que hace falta es limpiar la instalación, eso
# obliga a entrar en cada instancia para poder quitarla, que es justo lo contrario.


@router.delete("/workspaces/{slug}")
def delete_workspace(slug: str, db: DbSession = Depends(auth.db)) -> dict:
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
    if len(repository.list_workspaces(db)) == 1:
        raise HTTPException(409, "No se puede borrar el único workspace de la instalación.")

    ws = settings.workspace_for(slug)
    # El árbol primero: si la fila cae y el borrado del directorio falla, quedan ficheros
    # que ya no consta a quién pertenecían. Al revés, un fallo deja la fila y se reintenta.
    try:
        removed = settings.destroy(ws)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, f"No se pudo borrar '{ws.root}': {exc}") from exc

    db.delete(workspace)
    db.flush()
    deps.invalidate(slug, "workspace eliminado")
    return {"deleted": slug, "path": str(ws.root), "files_removed": removed}


# Vaciar una etapa. Deja el workspace en pie y su artefacto en «missing», que es lo que
# permite reconstruirlo: lo que se borra es el fichero curado, el borrador y las
# derivaciones de la caché que hablaban de él. `.history/` no se toca, así que un borrado
# equivocado se deshace desde «Restaurar» en la pantalla del artefacto.
@router.delete("/workspaces/{slug}/artifacts/{artifact}")
def delete_artifact(slug: str, artifact: str, db: DbSession = Depends(auth.db)) -> dict:
    if artifact not in review.ARTIFACTS:
        raise HTTPException(404, f"Artefacto desconocido: '{artifact}'.")
    workspace = repository.get_workspace(db, slug)
    if workspace is None:
        raise HTTPException(404, f"No existe el workspace '{slug}'.")
    if artifact in runtime.runner.building_artifacts(slug):
        raise HTTPException(
            409, "Ese artefacto se está construyendo ahora mismo; cancela el trabajo antes."
        )

    ws = settings.workspace_for(slug)
    result = review.discard(ws, artifact)
    deps.invalidate(slug, f"'{artifact}' eliminado desde administración")
    runtime.bus.publish(slug, None, "pipeline.changed", {"artifact": artifact, "action": "discard"})
    return {"workspace": slug, **result}


# ACCOUNTS --------------------------------------------------------------------------------


@router.post("/accounts/{user_id}/disable")
def disable(
    user_id: int, admin: User = Depends(auth.require_admin), db: DbSession = Depends(auth.db)
) -> dict:
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id:
        raise HTTPException(409, "No puedes desactivar tu propia cuenta.")
    user.disabled_at = identity.now()
    identity.revoke_all_sessions(db, user.id)
    return {"disabled": user_id}


@router.post("/accounts/{user_id}/enable")
def enable(user_id: int, db: DbSession = Depends(auth.db)) -> dict:
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    user.disabled_at = None
    return {"enabled": user_id}


# The other half of `disable`, and deliberately not the same thing: disabling keeps the
# account and shuts the door, this removes the account and leaves standing what it made.
# Both exist because they answer different questions — «esta persona ya no entra» and «esta
# cuenta no debería haber existido» — and having only the first left the panel unable to
# clean up after a mistyped invitation.
#
# Deleting yourself is refused, which is also what keeps the installation from losing its
# last administrator: whoever is calling this is an active one, and stays.
@router.delete("/accounts/{user_id}")
def delete_account(
    user_id: int, admin: User = Depends(auth.require_admin), db: DbSession = Depends(auth.db)
) -> dict:
    user = identity.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(404, "Esa cuenta no existe.")
    if user.id == admin.id:
        raise HTTPException(409, "No puedes borrar tu propia cuenta.")

    username = user.username
    identity.delete_user(db, user)
    return {"deleted": user_id, "username": username}


# HELPERS ---------------------------------------------------------------------------------


def _chain(slug: str) -> list[dict]:
    ws = settings.workspace_for(slug)
    return [
        {
            "artifact": stage["artifact"],
            "label": stage["label"],
            "status": stage["status"],
            "is_autogenerated": stage["is_autogenerated"],
        }
        for stage in runtime.pipeline_snapshot(ws)
    ]


def _invite(db: DbSession, invite: Invite) -> dict:
    workspace = invite.workspace
    author = identity.get_user_by_id(db, invite.created_by) if invite.created_by else None
    return {
        "id": invite.id,
        "role": invite.role,
        "workspace": workspace.name if workspace else None,
        "workspace_slug": workspace.slug if workspace else None,
        "created_at": invite.created_at.isoformat(),
        "expires_at": invite.expires_at.isoformat(),
        "created_by": author.username if author else None,
    }


def _headers(db: DbSession, workspace: str | None = None) -> list[dict]:
    workspace_id = None
    if workspace:
        row = repository.get_workspace(db, workspace)
        if row is None:
            raise HTTPException(404, f"No existe el workspace '{workspace}'.")
        workspace_id = row.id
    return [
        evaluation_store.header(row, user, row.workspace.slug if row.workspace else None)
        for row, user in study.all_evaluations(db, workspace_id)
    ]


def _row(header: dict) -> dict:
    return {
        "id": header["id"],
        "created_at": header.get("created_at"),
        "workspace": header.get("workspace"),
        "account": header.get("account"),
        "account_id": header.get("account_id"),
        "concepts": header.get("concepts") or [],
        "item_type": header.get("item_type"),
        "choice": header.get("choice"),
        "choice_arm": header.get("choice_arm"),
        "chosen_at": header.get("chosen_at"),
        "think": bool(header.get("think", True)),
        "rating": header.get("rating"),
        "arm_status": header.get("arm_status") or {},
        "arm_elapsed_ms": header.get("arm_elapsed_ms") or {},
        "evaluator_note": header.get("evaluator_note"),
    }

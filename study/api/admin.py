"""The study's own tab of the installation panel.

Same prefix and same `require_admin` as `server/routers/admin.py`, and mounted beside it
by `study.api.install`: the routes are the administrator's, the arithmetic behind them is
the study's, and this is the seam between the two.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from server import auth, runtime, settings
from server import curriculum as curriculum_store
from server.db import identity, repository
from server.db.models import User
from server.editors import kg_edit
from server.routers.jobs import gate_error

from .. import ARM_LABELS, ARMS
from . import queries
from . import store as evaluation_store

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


# What tells `jobs.evaluator_of` that a session is stock rather than somebody's own
# commission. The two routes reach the SAME handler, so without a mark in the parameters
# they are indistinguishable at the point the session is saved — and the panel is this
# flag's only writer.
STOCK_PARAM = "stock"


class DeleteBody(BaseModel):
    ids: list[str]


class AssignBody(BaseModel):
    """Who gets these three items. `repeat` is the deliberate exception: handing the same
    set to somebody who already judged it measures how consistent one person is with
    themselves, which is the only reliability an evaluator alone in their subject can
    provide. It is refused unless asked for, because the usual cause is a double click."""

    accounts: list[int]
    repeat: bool = False


class GenerateBody(BaseModel):
    """A commission, plus which workspace it runs in and how many comparisons to make.

    `n` here is NOT the item counter the generate screen drops — that one asks how many
    items one commission produces, and an evaluation always produces exactly one per arm.
    This one asks how many separate COMPARISONS to prepare, each its own session, so an
    administrator can stock a workspace and then hand out a subset.
    """

    workspace: str
    concepts: list[str] = []
    item_type: str | None = None
    fixed: dict = {}
    curriculum: list[str] | None = None
    instructions: str | None = None
    n: int = 1


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
        "by_profile": evaluation_store.by_profile(headers),
        "agreement": evaluation_store.agreement(headers),
        "per_day": evaluation_store.per_day(headers),
        "arms": [{"key": arm, "label": ARM_LABELS[arm]} for arm in ARMS],
        "filters": {
            "workspace": workspace,
            "account": account,
            # Every workspace of the installation, NOT the ones that happen to appear in a
            # recorded session. Deriving the list from the sessions was a chicken and egg:
            # with nothing evaluated yet the filter was empty, so no workspace could be
            # picked, so nothing could be handed out, so nothing was ever evaluated.
            "workspaces": [row.slug for row in repository.list_workspaces(db)],
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


# HANDING SETS OUT --------------------------------------------------------------------------
#
# The administrator is the one who knows which subject each evaluator teaches, so who gets
# which three items is decided here by hand rather than by a rule. That is the whole design:
# a panel drawn from different subjects cannot be given a shared workload automatically
# without asking somebody to judge a syllabus they have never taught.
#
# EVERY ROUTE WITH A FIXED PATH GOES ABOVE `/evaluations/{session_id}`, and that is not
# tidiness — FastAPI matches in declaration order, so a wildcard declared first swallows
# `/evaluations/accounts` as a session called «accounts» and answers 404 «No existe la
# sesión». The failure is silent in the worst way: a plausible 404 from a route nobody
# meant to call. `export.csv` was already up there for the same reason.
# `tests/study/test_route_order.py` is what keeps the next addition from landing below it.


# Whether a commission can be composed for this instance at all, and if not, WHICH stages
# are still pending. The rule is `gate_error`'s and stays `gate_error`'s — the same one
# `POST /evaluations/generate` enforces below, so the screen cannot offer what the endpoint
# would refuse. What is added here is the naming: the sentence it returns interpolates the
# unapproved stages' Spanish labels, and this list of theirs goes to the browser as
# ARTIFACT KEYS, which `web/src/lib/names.ts` already says in the reader's own language.
# The second read only happens on the unhappy path, and only ever once per workspace.
def _commission_gate(slug: str) -> dict:
    ws = settings.workspace_for(slug)
    if gate_error(ws, "evaluate") is None:
        return {"ready": True, "pending": []}
    return {
        "ready": False,
        "pending": [
            stage["artifact"]
            for stage in runtime.pipeline_snapshot(ws)
            if stage["status"] != "approved"
        ],
    }


# The flow starts with a PERSON, not with a set: an administrator knows which subject each
# evaluator teaches, so «¿a quién?» comes before «¿cuál?». Each account carries the
# workspaces it can actually open, because handing somebody a set of an instance they
# cannot reach produces a queue entry that 404s when they click it.
@router.get("/evaluations/accounts")
def assignable_accounts(db: DbSession = Depends(auth.db)) -> dict:
    everything = repository.list_workspaces(db)

    # Per WORKSPACE and not per (account, workspace): reading whether a chain is approved
    # touches the filesystem three times, and this endpoint loops over every account of the
    # installation — the same instance would be measured once for each of them.
    gates: dict[str, dict] = {}

    def gate(slug: str) -> dict:
        if slug not in gates:
            gates[slug] = _commission_gate(slug)
        return gates[slug]

    accounts = []
    for user in identity.list_users(db):
        if not user.active:
            continue
        # THE SAME RULE `assign_set` ENFORCES, and it has to be: an administrator reaches
        # every instance through the bypass in `auth.deps.access_for`, so listing only
        # their membership rows would have this screen refuse an assignment the endpoint
        # behind it accepts. Anybody else gets exactly the instances they can open.
        if user.is_admin:
            reachable = [
                {"slug": w.slug, "name": w.name, "role": "administración", **gate(w.slug)}
                for w in everything
            ]
        else:
            reachable = [
                {"slug": w.slug, "name": w.name, "role": m.role, **gate(w.slug)}
                for m, w in identity.memberships_for(db, user.id)
            ]
        accounts.append(
            {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "evaluator_profile": user.evaluator_profile,
                "is_admin": user.is_admin,
                "workspaces": reachable,
            }
        )
    return {"accounts": accounts}


# Stocking a workspace with comparisons to hand out. They are generated ONCE and belong to
# whoever launched them; assigning copies the three items to somebody else. What is not
# assigned simply stays here, which is the point — an administrator prepares a batch and
# then decides who is competent to judge which part of it.
@router.post("/evaluations/generate", status_code=202)
def generate(
    body: GenerateBody,
    db: DbSession = Depends(auth.db),
    admin: User = Depends(auth.require_admin),
) -> dict:
    if not body.concepts:
        raise HTTPException(422, "Hay que elegir al menos un concepto objetivo.")
    if not 1 <= body.n <= 10:
        raise HTTPException(422, "Entre 1 y 10 comparaciones por tanda.")
    if repository.get_workspace(db, body.workspace) is None:
        raise HTTPException(404, f"No existe el workspace '{body.workspace}'.")

    ws = settings.workspace_for(body.workspace)
    error = gate_error(ws, "evaluate")
    if error:
        raise HTTPException(409, error)

    graph = kg_edit.load_graph(ws)
    curriculum = curriculum_store.resolve(ws, graph, body.curriculum)

    # One job per comparison: the handler produces exactly one session, and the queue is
    # one deep, so they run one after another on the single GPU.
    jobs = [
        runtime.runner.submit(
            "evaluate",
            {
                "concepts": body.concepts,
                "item_type": body.item_type,
                "fixed": body.fixed,
                "curriculum": curriculum or [],
                "instructions": body.instructions,
                "seed": None,
                STOCK_PARAM: True,
            },
            workspace=body.workspace,
            user_id=admin.id,
            user_name=admin.name,
        )
        for _ in range(body.n)
    ]
    logger.info(
        f"[estudio] «{admin.username}» encargó {len(jobs)} comparación(es) "
        f"en «{body.workspace}»"
    )
    return {"jobs": [job.to_dict() for job in jobs], "since": runtime.bus.last_seq}


@router.get("/evaluations/sets")
def sets(workspace: str, db: DbSession = Depends(auth.db)) -> dict:
    row = repository.get_workspace(db, workspace)
    if row is None:
        raise HTTPException(404, f"No existe el workspace '{workspace}'.")

    members = [
        {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "evaluator_profile": user.evaluator_profile,
            "role": membership.role,
        }
        for membership, user in identity.members_of(db, row.id)
    ]

    listing = []
    for representative in queries.sets_in_workspace(db, row.id):
        set_id = representative.set_id or representative.id
        copies = queries.sessions_in_set(db, set_id)
        listing.append(
            {
                "set_id": set_id,
                "created_at": representative.created_at.timestamp()
                if representative.created_at
                else 0.0,
                "concepts": list(representative.concepts or []),
                "item_type": representative.item_type or "",
                "instructions": representative.instructions or "",
                "think": bool(representative.think),
                # One entry per person holding these items, so the panel can show at a
                # glance who still owes a judgement and who already gave one. Stock has no
                # evaluator and therefore no entry: listing it would draw the row nobody
                # holds as «cuenta borrada», which is the opposite of «sin repartir».
                "holders": [
                    {
                        "session_id": copy.id,
                        "account_id": copy.user_id,
                        "account": copy.user.username if copy.user else None,
                        "evaluator_profile": copy.user.evaluator_profile if copy.user else None,
                        "assigned": copy.assigned_by is not None,
                        "decided": copy.chosen_at is not None,
                        "declined": copy.declined_at is not None,
                    }
                    for copy in copies
                    if copy.user_id is not None
                ],
            }
        )

    return {
        "workspace": row.slug,
        "members": members,
        "sets": sorted(listing, key=lambda s: s["created_at"], reverse=True),
    }


@router.post("/evaluations/sets/{set_id}/assign", status_code=201)
def assign_set(
    set_id: str,
    body: AssignBody,
    db: DbSession = Depends(auth.db),
    admin: User = Depends(auth.require_admin),
) -> dict:
    existing = queries.sessions_in_set(db, set_id)
    if not existing:
        raise HTTPException(404, f"No existe el conjunto '{set_id}'.")
    source = existing[0]

    created, skipped = [], []
    for account_id in dict.fromkeys(body.accounts):
        user = identity.get_user_by_id(db, account_id)
        if user is None:
            raise HTTPException(404, f"La cuenta {account_id} no existe.")
        # Membership and not just an account: handing somebody a set of a workspace they
        # cannot open would produce a queue entry that 404s when they click it.
        if identity.membership(db, source.workspace_id, user.id) is None and not user.is_admin:
            raise HTTPException(
                409,
                f"«{user.username}» no es miembro de ese workspace: dale acceso antes de asignarle nada.",
            )
        try:
            session = evaluation_store.assign(
                db, source, user.id, assigned_by=admin.id, allow_repeat=body.repeat
            )
        except ValueError:
            skipped.append(user.username)
            continue
        created.append({"session_id": session.id, "account": user.username})

    if created:
        logger.info(
            f"[estudio] «{admin.username}» repartió el conjunto «{set_id}» "
            f"a {len(created)} evaluador(es)"
        )
    return {"set_id": set_id, "assigned": created, "already_had_it": skipped}


# The full trace of one session, reveal included. An administrator reading this is reading
# research data they are entitled to; the evaluator's own blinding is unaffected, because
# nothing here writes and the session is already judged or already theirs to judge.
@router.get("/evaluations/{session_id}")
def session_detail(session_id: str, db: DbSession = Depends(auth.db)) -> dict:
    row = queries.get_evaluation(db, session_id)
    if row is None:
        raise HTTPException(404, f"No existe la sesión '{session_id}'.")
    return {
        "session": row.trace,
        "workspace": row.workspace.slug if row.workspace else None,
        "account": row.user.username if row.user else None,
    }


@router.delete("/evaluations")
def delete_sessions(
    body: DeleteBody,
    db: DbSession = Depends(auth.db),
    admin: User = Depends(auth.require_admin),
) -> dict:
    ids = list(dict.fromkeys(i for i in body.ids if i))
    if not ids:
        raise HTTPException(422, "No se ha indicado ninguna sesión.")
    deleted = queries.delete_evaluations(db, ids)
    logger.warning(
        f"[estudio] «{admin.username}» borró {len(deleted)} sesión(es) de evaluación"
    )
    return {"deleted": deleted, "missing": [i for i in ids if i not in deleted]}


def _headers(db: DbSession, workspace: str | None = None) -> list[dict]:
    workspace_id = None
    if workspace:
        row = repository.get_workspace(db, workspace)
        if row is None:
            raise HTTPException(404, f"No existe el workspace '{workspace}'.")
        workspace_id = row.id
    return evaluation_store.headers(db, workspace_id)


def _row(header: dict) -> dict:
    return {
        "id": header["id"],
        "created_at": header.get("created_at"),
        "workspace": header.get("workspace"),
        "account": header.get("account"),
        "account_id": header.get("account_id"),
        "evaluator_profile": header.get("evaluator_profile"),
        "set_id": header.get("set_id"),
        "assigned": bool(header.get("assigned")),
        "concepts": header.get("concepts") or [],
        "item_type": header.get("item_type"),
        "triage_arm": header.get("triage_arm") or {},
        "choice": header.get("choice"),
        "choice_arm": header.get("choice_arm"),
        "chosen_at": header.get("chosen_at"),
        "declined_at": header.get("declined_at"),
        "seconds": header.get("seconds"),
        "think": bool(header.get("think", True)),
        "rating": header.get("rating"),
        "arm_status": header.get("arm_status") or {},
        "arm_elapsed_ms": header.get("arm_elapsed_ms") or {},
        "evaluator_note": header.get("evaluator_note"),
    }

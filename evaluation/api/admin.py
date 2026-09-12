"""The evaluation's own tab of the installation panel.

Same prefix and same `require_admin` as `server/routers/admin.py`, and mounted beside it
by `evaluation.api.install`: the routes are the administrator's, the arithmetic behind them is
the evaluation's, and this is the seam between the two.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from server import auth, installation, singletons
from server import curriculum as curriculum_store
from server.db import identity, repository
from server.db.models import User
from server.editors import kg_edit
from server.routers.jobs import gate_error

from .. import ARM_LABELS, ARMS
from . import queries
from . import stage_queries
from . import stage_store
from . import store as evaluation_store

# The two evaluator profiles a reading can be narrowed to. `None` in the filter is "todos";
# a value outside this pair is refused rather than silently matching nobody.
PROFILE_FILTERS = ("teacher", "student")

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


# What tells `jobs.evaluator_of` that a session is stock rather than somebody's own
# commission. Both routes reach the SAME handler, so without a mark in the parameters they
# are indistinguishable where the session is saved. The panel is this flag's only writer.
STOCK_PARAM = "stock"


class DeleteBody(BaseModel):
    """The sessions to remove."""

    ids: list[str]


class RecordsBody(BaseModel):
    """Whose records to remove: account ids, never usernames, so a rename cannot miss."""

    accounts: list[int]


class AssignBody(BaseModel):
    """Who gets these items.

    `repeat` is the deliberate exception: handing the same set to somebody who already
    judged it is test-retest, the only reliability an evaluator alone in their subject can
    contribute. Refused unless asked for, because the usual cause is a double click.
    """

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
    scenario: str | None = None
    n: int = 1


def _profile(profile: str | None) -> str | None:
    """Refuse a profile filter that names neither of the two the installation knows."""
    if profile is not None and profile not in PROFILE_FILTERS:
        raise HTTPException(422, f"No existe el perfil «{profile}»: docente o alumno.")
    return profile


def _narrow(headers: list[dict], account: int | None, profile: str | None) -> list[dict]:
    """Apply the two person filters the panel offers, in the order it asks them.

    WHO comes before WHERE on the screen, and both apply to both instruments: the same
    three arguments narrow the comparisons and the construction forms, so the two blocks
    of the panel always describe the same people.
    """
    if account is not None:
        headers = [h for h in headers if h.get("account_id") == account]
    if profile is not None:
        headers = [h for h in headers if h.get("evaluator_profile") == profile]
    return headers


def _filter_lists(db: DbSession) -> dict:
    """What the two selectors offer: every workspace, every active account.

    Both are the INSTALLATION's and not what appears in a recorded session: deriving
    them from the data is a chicken and egg, since with nothing evaluated yet the filter
    is empty and nothing can be chosen.
    """
    return {
        "workspaces": [row.slug for row in repository.list_workspaces(db)],
        "accounts": [
            {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "evaluator_profile": user.evaluator_profile,
            }
            for user in identity.list_users(db)
            if user.active
        ],
    }


@router.get("/evaluations")
def evaluations(
    workspace: str | None = None,
    account: int | None = None,
    profile: str | None = None,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Return the whole evaluation: the aggregates, the four groupings and every session."""
    profile = _profile(profile)
    headers = _narrow(_headers(db, workspace=workspace), account, profile)

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
            "profile": profile,
            **_filter_lists(db),
        },
        # Newest first, and every one openable: the point of the panel is going from "este
        # evaluador nunca elige el sistema" to the sessions that say so.
        "sessions": [_row(h) for h in sorted(
            headers, key=lambda h: h.get("created_at") or 0, reverse=True
        )],
    }


@router.get("/evaluations/export.csv")
def export(
    workspace: str | None = None,
    account: int | None = None,
    profile: str | None = None,
    db: DbSession = Depends(auth.db),
) -> Response:
    """Return the evaluation's raw data, one row per session, as a CSV attachment."""
    headers = _narrow(_headers(db, workspace=workspace), account, _profile(profile))
    return Response(
        content=evaluation_store.export_csv(headers),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="evaluaciones.csv"'},
    )


# THE CONSTRUCTION FORMS ---------------------------------------------------------------------
#
# The other instrument: what a teacher answered at the foot of each stage, about the build
# that was on screen. Same three filters as the comparisons, so the two blocks of the panel
# always describe the same people. Declared here, ABOVE the wildcard, for the reason the
# banner below gives.


@router.get("/evaluations/stages")
def stage_evaluations(
    workspace: str | None = None,
    account: int | None = None,
    profile: str | None = None,
    db: DbSession = Depends(auth.db),
) -> dict:
    """Return the construction forms: one summary per stage, by evaluator, and every row."""
    headers = _narrow(_stage_headers(db, workspace), account, _profile(profile))
    return {
        "aggregates": stage_store.aggregates(headers),
        "by_account": stage_store.by_account(headers),
        "rows": [
            _stage_row(h)
            for h in sorted(headers, key=lambda h: h.get("created_at") or 0, reverse=True)
        ],
    }


@router.get("/evaluations/stages/export.csv")
def export_stage_evaluations(
    workspace: str | None = None,
    account: int | None = None,
    profile: str | None = None,
    db: DbSession = Depends(auth.db),
) -> Response:
    """Return the forms' raw data, one row per (person, build, stage), as a CSV attachment."""
    headers = _narrow(_stage_headers(db, workspace), account, _profile(profile))
    return Response(
        content=stage_store.export_csv(headers),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="formularios-construccion.csv"'},
    )


@router.delete("/evaluations/records")
def delete_evaluator_records(
    body: RecordsBody,
    db: DbSession = Depends(auth.db),
    admin: User = Depends(auth.require_admin),
) -> dict:
    """Remove everything these evaluators contributed to the evaluation, both instruments.

    The comparisons they hold and the forms they answered go together, because a person
    withdrawn from the evaluation is withdrawn from all of it — keeping their forms while
    dropping their comparisons would leave half a contribution nobody asked for. The
    ACCOUNT is untouched: this is the evaluation's data, not the installation's access.
    """
    ids = list(dict.fromkeys(body.accounts))
    if not ids:
        raise HTTPException(422, "No se ha indicado ninguna cuenta.")
    sessions = queries.delete_for_accounts(db, ids)
    forms = stage_queries.delete_for_accounts(db, ids)
    logger.warning(
        f"[estudio] «{admin.username}» borró los registros de {len(ids)} evaluador(es): "
        f"{sessions} sesión(es) y {forms} formulario(s)"
    )
    return {"accounts": ids, "sessions": sessions, "forms": forms}


# HANDING SETS OUT --------------------------------------------------------------------------
#
# The administrator is the one who knows which subject each evaluator teaches, so who gets
# which three items is decided here by hand rather than by a rule: a panel drawn from
# different subjects cannot be given a shared workload without asking somebody to judge a
# syllabus they have never taught.
#
# EVERY ROUTE WITH A FIXED PATH GOES ABOVE `/evaluations/{session_id}`. FastAPI matches in
# declaration order, so a wildcard declared first swallows `/evaluations/accounts` as a
# session called "accounts" and answers a plausible 404 from a route nobody meant to call.
# `tests/evaluation/test_route_order.py` is what keeps the next addition from landing below it.


def _commission_gate(slug: str) -> dict:
    """Say whether a commission can be composed for this instance, and name what is pending.

    The rule is `gate_error`'s and stays `gate_error`'s — the same one `generate` enforces
    below, so the screen cannot offer what the endpoint would refuse. The pending stages go
    to the browser as ARTIFACT KEYS, which `web/src/lib/names.ts` says in the reader's own
    language; that second read only happens on the unhappy path.
    """
    ws = installation.workspace_for(slug)
    if gate_error(ws, "evaluate") is None:
        return {"ready": True, "pending": []}
    return {
        "ready": False,
        "pending": [
            stage["artifact"]
            for stage in singletons.pipeline_snapshot(ws)
            if stage["status"] != "approved"
        ],
    }


@router.get("/evaluations/accounts")
def assignable_accounts(db: DbSession = Depends(auth.db)) -> dict:
    """List every active account with the workspaces it can actually open.

    The flow starts with a PERSON and not with a set, so "¿a quién?" comes before "¿cuál?",
    and handing somebody a set of an instance they cannot reach would produce a queue entry
    that 404s when they click it.
    """
    everything = repository.list_workspaces(db)

    # Memoised per WORKSPACE and not per (account, workspace): reading whether a chain is
    # approved touches the filesystem three times, and this loops over every account.
    gates: dict[str, dict] = {}

    def gate(slug: str) -> dict:
        """Return this workspace's gate, reading it at most once per request."""
        if slug not in gates:
            gates[slug] = _commission_gate(slug)
        return gates[slug]

    accounts = []
    for user in identity.list_users(db):
        if not user.active:
            continue
        # THE SAME RULE `assign_set` ENFORCES: an administrator reaches every instance
        # through the bypass in `auth.deps.access_for`, so listing only their membership
        # rows would have this screen refuse an assignment the endpoint behind it accepts.
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


@router.post("/evaluations/generate", status_code=202)
def generate(
    body: GenerateBody,
    db: DbSession = Depends(auth.db),
    admin: User = Depends(auth.require_admin),
) -> dict:
    """Stock a workspace with N comparisons, belonging to nobody until they are assigned.

    What is not handed out simply stays: an administrator prepares a batch and then decides
    who is competent to judge which part of it.
    """
    if not body.concepts:
        raise HTTPException(422, "Hay que elegir al menos un concepto objetivo.")
    if not 1 <= body.n <= 10:
        raise HTTPException(422, "Entre 1 y 10 comparaciones por tanda.")
    if repository.get_workspace(db, body.workspace) is None:
        raise HTTPException(404, f"No existe la asignatura '{body.workspace}'.")

    ws = installation.workspace_for(body.workspace)
    error = gate_error(ws, "evaluate")
    if error:
        raise HTTPException(409, error)

    graph = kg_edit.load_graph(ws)
    curriculum = curriculum_store.resolve(ws, graph, body.curriculum)

    # One job per comparison: the handler produces exactly one session, and the lane
    # serialises them on the single GPU.
    jobs = [
        singletons.runner.submit(
            "evaluate",
            {
                "concepts": body.concepts,
                "item_type": body.item_type,
                "fixed": body.fixed,
                "curriculum": curriculum or [],
                "instructions": body.instructions,
                "scenario": body.scenario,
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
    return {"jobs": [job.to_dict() for job in jobs], "since": singletons.bus.last_seq}


@router.get("/evaluations/sets")
def sets(workspace: str, db: DbSession = Depends(auth.db)) -> dict:
    """List a workspace's distinct sets with who holds each, plus who could hold one."""
    row = repository.get_workspace(db, workspace)
    if row is None:
        raise HTTPException(404, f"No existe la asignatura '{workspace}'.")

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
                # One entry per person holding these items. Stock has no evaluator and
                # therefore no entry: listing it would draw the row nobody holds as
                # "cuenta borrada", which is the opposite of "sin repartir".
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
    """Hand a copy of these items to each named account.

    Each copy gets a fresh shuffle and every answer cleared, so what two evaluators end up
    agreeing about is the exercises and not the seating.
    """
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
                f"«{user.username}» no es miembro de esa asignatura: dale acceso antes de asignarle nada.",
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


@router.get("/evaluations/{session_id}")
def session_detail(session_id: str, db: DbSession = Depends(auth.db)) -> dict:
    """Return one session's full trace, reveal included.

    The evaluator's own blinding is unaffected: nothing here writes, so reading a session
    cannot change what its holder will be shown.
    """
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
    """Delete any sessions of the installation, reporting the ids that did not exist."""
    ids = list(dict.fromkeys(i for i in body.ids if i))
    if not ids:
        raise HTTPException(422, "No se ha indicado ninguna sesión.")
    deleted = queries.delete_evaluations(db, ids)
    logger.warning(
        f"[estudio] «{admin.username}» borró {len(deleted)} sesión(es) de evaluación"
    )
    return {"deleted": deleted, "missing": [i for i in ids if i not in deleted]}


def _headers(db: DbSession, workspace: str | None = None) -> list[dict]:
    """Read the population the panel aggregates over, optionally narrowed to a workspace."""
    return evaluation_store.headers(db, _workspace_id(db, workspace))


def _stage_headers(db: DbSession, workspace: str | None = None) -> list[dict]:
    """Read every construction form, optionally narrowed to a workspace."""
    return stage_store.headers(db, _workspace_id(db, workspace))


def _workspace_id(db: DbSession, workspace: str | None) -> int | None:
    """Resolve the workspace filter to a row id, or None for "todas"."""
    if not workspace:
        return None
    row = repository.get_workspace(db, workspace)
    if row is None:
        raise HTTPException(404, f"No existe la asignatura '{workspace}'.")
    return row.id


def _stage_row(header: dict) -> dict:
    """Shape one form for the panel's table: the verdict, and who gave it about what."""
    return {
        "id": header["id"],
        "created_at": header.get("created_at"),
        "updated_at": header.get("updated_at"),
        "seconds": header.get("seconds"),
        "workspace": header.get("workspace"),
        "account": header.get("account"),
        "account_id": header.get("account_id"),
        "evaluator_profile": header.get("evaluator_profile"),
        "artifact": header.get("artifact"),
        "instrument": header.get("instrument"),
        "answers": header.get("answers") or {},
        "overall": header.get("overall"),
        "curated": header.get("curated"),
        "answered": bool(header.get("answered")),
        "note": header.get("note"),
    }


def _row(header: dict) -> dict:
    """Shape one session for the panel's table, reveal and all."""
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

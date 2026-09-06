"""The machine and the process, as the administration panel sees them.

Behind `require_admin`, and under `/api/admin` because everything here is global to the
installation: the one GPU, the models on the engine's disk, the port forward that reaches
it, the registry of warm contexts, the queue's past and the database. Every write —
releasing the GPU, pulling or deleting a model, invalidating a context, opening or closing
the tunnel — changes something every workspace feels, which is why they are all here.

Three rules the routes below enforce and no screen may re-derive: a model the
configuration names cannot be deleted, a pull runs beside the queue rather than in it (a
download is network and disk, never the GPU), and releasing the GPU or invalidating a
context is refused while a job runs.
"""

import csv
import io
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from variatio import config
from variatio.core import cerebras_budget, inference

from .. import auth, csv_safe, deps, jobs, singletons
from ..db import Base, database_url
from ..db.models import User
from ..tunnel import TunnelError

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class ModelBody(BaseModel):
    """Which model is being pulled."""

    model: str


# THE ENGINE ------------------------------------------------------------------------------


def _listings() -> tuple[list[dict], list[dict]]:
    """Read what is on disk and what is resident, each degrading to an empty list."""
    installed: list[dict] = []
    running: list[dict] = []
    try:
        installed = inference.installed_models_detail()
    except Exception:  # noqa: BLE001 - no listing, not a broken screen
        installed = []
    try:
        running = inference.running_models()
    except Exception:  # noqa: BLE001 - idem
        running = []
    return installed, running


def _model_state(model: str, remote: set, resident: set, on_disk: set) -> str:
    """Say where one required model is: remote, loaded, on disk, or not installed.

    A remotely served model is never "not installed": there is no disk for it to be
    missing from, which is how a screen says "remoto" instead of "sin instalar".
    """
    if model in remote:
        return "remote"
    if model in resident:
        return "loaded"
    if model in on_disk:
        return "on_disk"
    return "not_installed"


@router.get("/engine")
def engine() -> dict:
    """Answer the whole "Motor" tab: the engine, its models, the queue and the tunnel."""
    available = inference.is_available()
    installed: list[dict] = []
    running: list[dict] = []
    if available:
        installed, running = _listings()

    required = inference.required_models()
    asked_by: dict[str, list[str]] = {}
    for name, model in required.items():
        asked_by.setdefault(model, []).append(name)
    on_disk = {info["model"] for info in installed}
    resident = {info["model"] for info in running}
    remote = inference.remote_models()

    return {
        "engine": inference.engine_name(),
        "host": config.OLLAMA_HOST,
        "available": available,
        "running": running,
        "installed": [
            {**info, "asked_by": asked_by.get(info["model"], [])}
            for info in sorted(installed, key=lambda info: info["model"])
        ],
        "required": [
            {
                "model": model,
                "asked_by": names,
                "state": _model_state(model, remote, resident, on_disk),
            }
            for model, names in sorted(asked_by.items())
        ],
        "idle": {
            "seconds": singletons.runner.idle_seconds(),
            "threshold": config.IDLE_UNLOAD_SECONDS,
            "poll": config.IDLE_UNLOAD_POLL_SECONDS,
        },
        "busy": singletons.runner.is_busy(),
        "contexts": deps.warm_slugs(),
        "pulls": singletons.pulls.all(),
        "tunnel": singletons.tunnel.status(),
        "cerebras": cerebras_state(),
    }


# THE REMOTE HALF -------------------------------------------------------------------------


def cerebras_state() -> dict:
    """Report the remote half from the rolling ledger on disk, and from nothing else.

    This endpoint is polled every 15 s by every open tab, so it never calls Cerebras;
    the catalogue has its own cached route. The ledger is a FILE because a build runs in
    `server.jobs.build_worker`, a separate process — the half of the work that actually
    empties a daily budget — and reading it here is what shows a build's spending live.

    `routed` and `usage` are two keys on purpose: the first is what the engine sends to
    Cerebras — its catalogue as last read plus the declared list, asked of the engine so
    it is the same answer routing gives — the second what has actually been spent. A model can be in one and
    not the other, and collapsing them into one "models" loses exactly that difference.
    """
    budget = cerebras_budget.shared().snapshot()
    return {
        "active": inference.engine_name() == "cerebras+ollama",
        "configured": bool(config.CEREBRAS_API_KEY),
        "routed": sorted(inference.remote_models()),
        "max_wait": config.CEREBRAS_MAX_WAIT_SECONDS,
        "usage": budget["models"],
        # One call and how many there are: the strip draws the one worth acting on — a
        # call the throttle is holding back — while the count is what tells a slow phase
        # from several jobs sharing the quota.
        "inflight": budget["inflight"],
        "inflight_count": budget["inflight_count"],
        "concurrency": config.CEREBRAS_MAX_CONCURRENT_JOBS,
    }


@router.get("/engine/cerebras/export.csv")
def cerebras_export() -> Response:
    """Export the per-phase Cerebras spending as a spreadsheet.

    Semicolons and a BOM rather than the evaluation's plain commas: this one is opened in Excel
    by hand, and a Spanish locale puts a comma-separated file in a single column.
    """
    columns = [
        "modelo",
        "fase",
        "peticiones",
        "tokens_entrada",
        "tokens_salida",
        "tokens",
        "porcentaje_del_dia",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, delimiter=";", extrasaction="ignore")
    writer.writeheader()
    for entry in cerebras_budget.shared().snapshot()["models"]:
        ceiling = entry["windows"]["day"]["tokens_limit"] or 1
        for row in entry["phases"]:
            writer.writerow(
                csv_safe.row(
                    {
                        "modelo": entry["model"],
                        "fase": row["phase"],
                        "peticiones": row["requests"],
                        "tokens_entrada": row["prompt_tokens"],
                        "tokens_salida": row["completion_tokens"],
                        "tokens": row["tokens"],
                        "porcentaje_del_dia": f"{row['tokens'] * 100 / ceiling:.2f}".replace(
                            ".", ","
                        ),
                    }
                )
            )
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cerebras-por-fase.csv"'},
    )


@router.post("/engine/release")
def release(admin: User = Depends(auth.require_admin)) -> dict:
    """Unload the resident models, refusing while any job runs."""
    job = singletons.runner.current()
    if job is not None:
        raise HTTPException(
            409, f"Hay un trabajo en curso («{job.label}»): espera o cancélalo antes."
        )
    if not inference.is_available():
        raise HTTPException(503, "El motor no responde: no hay nada que descargar.")
    return {"released": jobs.release_gpu(f"a petición de «{admin.username}»")}


# MODELS ON DISK --------------------------------------------------------------------------


@router.post("/engine/models/pull", status_code=202)
def pull_model(body: ModelBody, admin: User = Depends(auth.require_admin)) -> dict:
    """Start a download beside the queue, never in it.

    A pull is network and disk and never the GPU, so it must not wait behind a two-hour
    build; `PullTracker` runs a thread per model and this answers 202 straight away.
    """
    if body.model in inference.remote_models():
        raise HTTPException(422, f"'{body.model}' se sirve en Cerebras; no hay nada que descargar.")
    if not inference.is_available():
        raise HTTPException(503, "El motor no responde: no puede descargar nada.")
    try:
        return {"pull": singletons.pulls.start(body.model, admin.username)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.delete("/engine/models/{model:path}")
def delete_model(model: str) -> dict:
    """Remove a model from the engine's disk, unless the configuration names it.

    `required_models()` is the check: deleting a model some phase asks for would turn
    every build that reaches that phase into a failure forty minutes in.
    """
    asked_by = [name for name, value in inference.required_models().items() if value == model]
    if asked_by:
        raise HTTPException(
            409,
            f"'{model}' lo pide la configuración ({', '.join(asked_by)}): "
            "cambia esos ajustes antes de borrarlo.",
        )
    if singletons.pulls.is_pulling(model):
        raise HTTPException(409, f"'{model}' se está descargando ahora mismo.")
    job = singletons.runner.current()
    if job is not None:
        raise HTTPException(
            409, f"Hay un trabajo en curso («{job.label}») que podría estar usándolo."
        )
    if not inference.is_available():
        raise HTTPException(503, "El motor no responde.")
    try:
        inference.delete_model(model)
    except inference.InferenceError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"deleted": model}


# WARM CONTEXTS ---------------------------------------------------------------------------


@router.delete("/engine/contexts")
def invalidate_contexts(admin: User = Depends(auth.require_admin)) -> dict:
    """Drop every warm context, so the next job rebuilds its index."""
    _refuse_while_running()
    return {"invalidated": deps.invalidate_all(f"a petición de «{admin.username}»")}


@router.delete("/engine/contexts/{slug}")
def invalidate_context(slug: str, admin: User = Depends(auth.require_admin)) -> dict:
    """Drop one workspace's warm context."""
    _refuse_while_running(slug)
    if slug not in deps.warm_slugs():
        raise HTTPException(404, f"«{slug}» no tiene el contexto en memoria.")
    deps.invalidate(slug, f"a petición de «{admin.username}»")
    return {"invalidated": slug}


def _refuse_while_running(slug: str | None = None) -> None:
    """Raise 409 while a job runs: invalidating under it would pull its index away."""
    for job in singletons.runner.running():
        if slug is None or job.workspace == slug:
            raise HTTPException(
                409,
                f"«{job.label}» está en curso sobre ese contexto: espera o cancélalo antes.",
            )


# THE TUNNEL ------------------------------------------------------------------------------


@router.get("/engine/tunnel")
def tunnel() -> dict:
    """Answer the tunnel's state, with the last stderr lines a key problem lands in."""
    return singletons.tunnel.status()


@router.post("/engine/tunnel/start")
def tunnel_start() -> dict:
    """Open the port forward to the GPU box and let the watchdog keep it open."""
    try:
        return singletons.tunnel.start()
    except TunnelError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/engine/tunnel/stop")
def tunnel_stop() -> dict:
    """Close the port forward, and stop the watchdog relaunching it."""
    return singletons.tunnel.stop()


# THE QUEUE'S PAST ------------------------------------------------------------------------


@router.get("/jobs/history")
def job_history(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Answer the jobs that have finished, of every workspace.

    Reads a wider window than it returns, because what it filters out — the running and
    the queued — is what `admin.job_queue` already reports.
    """
    settled = [
        job.to_dict()
        for job in singletons.runner.all(limit=400)
        if job.status not in ("running", "queued")
    ]
    return {"jobs": settled[:limit]}


# THE DATABASE ----------------------------------------------------------------------------


@router.get("/system")
def system(db: DbSession = Depends(auth.db)) -> dict:
    """Answer where the database is, what revision it is at, and how long this has run.

    The location has its credentials stripped before it leaves the process.
    """
    url = database_url()
    safe = url.split("@")[-1] if "@" in url else url
    try:
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001 - a schema created outside Alembic has no such table
        db.rollback()
        revision = None
    counts = {
        table: db.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
        for table in sorted(Base.metadata.tables)
    }
    return {
        "database": {"location": safe, "revision": revision, "head": _head_revision(), "tables": counts},
        "process": {
            "started_at": _STARTED_AT,
            "uptime_seconds": time.time() - _STARTED_AT,
            "log_level": config.LOG_LEVEL,
        },
    }


_STARTED_AT = time.time()


def _head_revision() -> str | None:
    """Read Alembic's head from the migration scripts, or nothing if they cannot be read."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        from variatio.core.paths import PROJECT_ROOT

        script = ScriptDirectory.from_config(Config(str(PROJECT_ROOT / "alembic.ini")))
        return script.get_current_head()
    except Exception:  # noqa: BLE001 - the head is a nicety beside the revision
        return None

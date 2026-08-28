"""The machine and the process, as the administration panel sees them.

Everything here is global to the installation — the one GPU, the models on the engine's
disk, the port forward that reaches it, the registry of warm contexts, the queue's past
and the database — which is why it lives under `/api/admin` and not under a workspace.
Reading is free; the writes (releasing the GPU, pulling or deleting a model, invalidating a
context, opening or closing the tunnel) each change something every workspace feels, and
that is the reason they are the administrator's.
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

from .. import auth, csv_safe, deps, jobs, runtime
from ..db import Base, database_url
from ..db.models import User
from ..tunnel import TunnelError

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(auth.require_admin)]
)


class ModelBody(BaseModel):
    model: str


# THE ENGINE ------------------------------------------------------------------------------


@router.get("/engine")
def engine() -> dict:
    available = inference.is_available()
    installed: list[dict] = []
    running: list[dict] = []
    if available:
        try:
            installed = inference.installed_models_detail()
        except Exception:  # noqa: BLE001 - no listing, not a broken screen
            installed = []
        try:
            running = inference.running_models()
        except Exception:  # noqa: BLE001 - idem
            running = []

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
                "state": "remote"
                if model in remote
                else "loaded"
                if model in resident
                else "on_disk"
                if model in on_disk
                else "not_installed",
            }
            for model, names in sorted(asked_by.items())
        ],
        "idle": {
            "seconds": runtime.runner.idle_seconds(),
            "threshold": config.IDLE_UNLOAD_SECONDS,
            "poll": config.IDLE_UNLOAD_POLL_SECONDS,
        },
        "busy": runtime.runner.is_busy(),
        "contexts": deps.warm_slugs(),
        "pulls": runtime.pulls.all(),
        "tunnel": runtime.tunnel.status(),
        "cerebras": cerebras_state(),
    }


# THE REMOTE HALF -------------------------------------------------------------------------
#
# Read from the ledger on disk and from nothing else: this endpoint is polled every 15 s by
# every open tab, and `HybridEngine.is_available` already refuses to cross to Cerebras on
# that schedule for the same reason. The catalogue has its own cached route.
#
# The ledger is a file because a build runs in `server.jobs.build_worker`, a separate
# process — the half of the work that actually empties a daily budget. Reading it here is
# what lets the panel show a build's spending while it happens.


# `routed` and `usage` are deliberately two keys: the first is what the configuration sends
# to Cerebras, the second what has actually been spent. A model can be in one and not the
# other — routed but never called yet, or called before somebody took it off the list — and
# collapsing them into one «models» loses exactly that difference.
def cerebras_state() -> dict:
    budget = cerebras_budget.shared().snapshot()
    return {
        "active": inference.engine_name() == "cerebras+ollama",
        "configured": bool(config.CEREBRAS_API_KEY),
        "routed": sorted(config.CEREBRAS_MODELS),
        "max_wait": config.CEREBRAS_MAX_WAIT_SECONDS,
        "usage": budget["models"],
        "inflight": budget["inflight"],
    }


# The breakdown is a supporting table on screen and a spreadsheet off it: «qué fase se está
# comiendo el presupuesto» is a question you answer once and then want beside the memoria's
# own numbers. Semicolons and a BOM rather than the study's plain commas, because this one
# is opened in Excel by hand and a Spanish locale puts a comma-separated file in one column.
@router.get("/engine/cerebras/export.csv")
def cerebras_export() -> Response:
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
    job = runtime.runner.current()
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
    if body.model in inference.remote_models():
        raise HTTPException(422, f"'{body.model}' se sirve en Cerebras; no hay nada que descargar.")
    if not inference.is_available():
        raise HTTPException(503, "El motor no responde: no puede descargar nada.")
    try:
        return {"pull": runtime.pulls.start(body.model, admin.username)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.delete("/engine/models/{model:path}")
def delete_model(model: str) -> dict:
    asked_by = [name for name, value in inference.required_models().items() if value == model]
    if asked_by:
        raise HTTPException(
            409,
            f"'{model}' lo pide la configuración ({', '.join(asked_by)}): "
            "cambia esos ajustes antes de borrarlo.",
        )
    if runtime.pulls.is_pulling(model):
        raise HTTPException(409, f"'{model}' se está descargando ahora mismo.")
    job = runtime.runner.current()
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
    _refuse_while_running()
    return {"invalidated": deps.invalidate_all(f"a petición de «{admin.username}»")}


@router.delete("/engine/contexts/{slug}")
def invalidate_context(slug: str, admin: User = Depends(auth.require_admin)) -> dict:
    _refuse_while_running(slug)
    if slug not in deps.warm_slugs():
        raise HTTPException(404, f"«{slug}» no tiene el contexto en memoria.")
    deps.invalidate(slug, f"a petición de «{admin.username}»")
    return {"invalidated": slug}


def _refuse_while_running(slug: str | None = None) -> None:
    for job in runtime.runner.running():
        if slug is None or job.workspace == slug:
            raise HTTPException(
                409,
                f"«{job.label}» está en curso sobre ese contexto: espera o cancélalo antes.",
            )


# THE TUNNEL ------------------------------------------------------------------------------


@router.get("/engine/tunnel")
def tunnel() -> dict:
    return runtime.tunnel.status()


@router.post("/engine/tunnel/start")
def tunnel_start() -> dict:
    try:
        return runtime.tunnel.start()
    except TunnelError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/engine/tunnel/stop")
def tunnel_stop() -> dict:
    return runtime.tunnel.stop()


# THE QUEUE'S PAST ------------------------------------------------------------------------


@router.get("/jobs/history")
def job_history(limit: int = Query(50, ge=1, le=200)) -> dict:
    settled = [
        job.to_dict()
        for job in runtime.runner.all(limit=400)
        if job.status not in ("running", "queued")
    ]
    return {"jobs": settled[:limit]}


# THE DATABASE ----------------------------------------------------------------------------


@router.get("/system")
def system(db: DbSession = Depends(auth.db)) -> dict:
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
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        from variatio.core.paths import PROJECT_ROOT

        script = ScriptDirectory.from_config(Config(str(PROJECT_ROOT / "alembic.ini")))
        return script.get_current_head()
    except Exception:  # noqa: BLE001 - the head is a nicety beside the revision
        return None

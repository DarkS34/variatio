"""The installation's settings, read and rewritten without restarting the process.

Lives under `/api/admin` and not under `/api/workspaces` because the configuration
belongs to the whole installation: a workspace does not choose the model it is built
with, since the GPU co-residency arithmetic is one for the whole process.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from variant_generator import settings as vg_settings
from variant_generator.core import inference
from variant_generator.settings import Impact, SettingError

from .. import auth, deps, runtime

router = APIRouter(
    prefix="/api/admin/config", tags=["config"], dependencies=[Depends(auth.require_admin)]
)


class Patch(BaseModel):
    values: dict[str, object]


def _payload() -> dict:
    return {"groups": list(vg_settings.GROUPS), "settings": vg_settings.snapshot()}


def _refuse_while_busy() -> None:
    job = runtime.runner.current()
    if job is not None:
        raise HTTPException(
            409,
            f"Hay un trabajo en curso («{job.kind}»). Cambiar la configuración a mitad "
            "de una construcción dejaría el resultado escrito con dos configuraciones.",
        )


def _act(impacts: set) -> list[str]:
    done: list[str] = []
    if Impact.ENGINE in impacts:
        inference.reset_engine()
        done.append("motor de inferencia reiniciado")
    if impacts & {Impact.CONTEXTS, Impact.REINDEX, Impact.ENGINE}:
        count = deps.invalidate_all("configuración cambiada")
        done.append(f"{count} contexto(s) invalidado(s)")
    if Impact.REINDEX in impacts:
        done.append("el índice se reconstruirá en el próximo trabajo")
    return done


@router.get("")
def read() -> dict:
    return _payload()


@router.put("")
def write(body: Patch) -> dict:
    _refuse_while_busy()
    try:
        impacts = vg_settings.update(body.values)
    except SettingError as error:
        raise HTTPException(422, str(error)) from None
    return {**_payload(), "applied": _act(impacts)}


@router.post("/reload")
def reload() -> dict:
    _refuse_while_busy()
    impacts = vg_settings.reload()
    return {**_payload(), "applied": _act(impacts)}

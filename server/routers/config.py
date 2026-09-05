"""The installation's settings, read and rewritten without restarting the process.

Behind `require_admin`, and under `/api/admin` rather than under `/api/workspaces`
because the configuration belongs to the whole installation: a workspace does not choose
the model it is built with, the GPU co-residency arithmetic being one for the process.

What a change invalidates is keyed off the setting's `Impact` and off nothing else, in
`_act`: `ENGINE` resets the inference engine, and `ENGINE`, `CONTEXTS` or `REINDEX`
invalidate every warm context.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from variatio import config as vg_config
from variatio import settings
from variatio.core import cerebras, inference
from variatio.core.inference import InferenceError
from variatio.settings import Impact, SettingError

from .. import auth, deps, singletons

router = APIRouter(
    prefix="/api/admin/config", tags=["config"], dependencies=[Depends(auth.require_admin)]
)


class Patch(BaseModel):
    """The settings being written, keyed by registry key."""

    values: dict[str, object]


class Reset(BaseModel):
    """The registry keys whose stored value is being dropped."""

    keys: list[str]


def _payload() -> dict:
    """Assemble the whole configuration screen: groups, values, pipeline and models."""
    return {
        "groups": list(settings.GROUPS),
        "settings": settings.snapshot(),
        "pipeline": settings.pipeline(),
        "models": _models(),
    }


def _models() -> dict:
    """List what the engine can offer, so a model field is a choice and not a typed string.

    Both readings fail to an empty list: the configuration must stay editable while the
    engine is down, which is exactly when one wants to change it.
    """
    installed: list[dict] = []
    running: list[dict] = []
    if inference.is_available():
        try:
            installed = inference.installed_models_detail()
        except Exception:  # noqa: BLE001 - no listing, not a broken screen
            installed = []
        try:
            running = inference.running_models()
        except Exception:  # noqa: BLE001 - idem
            running = []
    return {"installed": installed, "running": running}


def _refuse_while_busy() -> None:
    """Raise 409 while a job runs: half a build written under two configurations."""
    job = singletons.runner.current()
    if job is not None:
        raise HTTPException(
            409,
            f"Hay un trabajo en curso («{job.kind}»). Cambiar la configuración a mitad "
            "de una construcción dejaría el resultado escrito con dos configuraciones.",
        )


def _act(impacts: set) -> list[str]:
    """Invalidate what the changed settings' `Impact` says has to go, and say what went."""
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
    """Answer the whole configuration screen."""
    return _payload()


@router.get("/cerebras-models")
def cerebras_models() -> dict:
    """Answer Cerebras' catalogue, degrading to the declared models and never to an error.

    Without a key, or with the API unreachable, the panel still has to be able to draw
    the model field — so the reason travels beside the fallback list.
    """
    declared = [str(model) for model in vg_config.CEREBRAS_MODELS]
    if not vg_config.CEREBRAS_API_KEY:
        return {
            "models": declared,
            "source": "config",
            "error": "Sin CEREBRAS_API_KEY en el entorno: se listan los modelos ya declarados.",
        }
    try:
        return {"models": cerebras.catalog(), "source": "api", "error": None}
    except InferenceError as error:
        return {"models": declared, "source": "config", "error": str(error)}


@router.put("")
def write(body: Patch) -> dict:
    """Store the given values and answer the screen, with what the change invalidated."""
    _refuse_while_busy()
    try:
        impacts = settings.update(body.values)
    except SettingError as error:
        raise HTTPException(422, str(error)) from None
    return {**_payload(), "applied": _act(impacts)}


@router.post("/reset")
def reset(body: Reset) -> dict:
    """Drop these keys from `config.json`, back to the registry's default.

    The key leaves the file, so the panel reports the value as «por defecto» again
    instead of as a stored value that happens to equal it.
    """
    _refuse_while_busy()
    try:
        impacts = settings.reset(body.keys)
    except SettingError as error:
        raise HTTPException(422, str(error)) from None
    return {**_payload(), "applied": _act(impacts)}


@router.post("/reload")
def reload() -> dict:
    """Re-read `config.json` and the environment, and answer what that invalidated."""
    _refuse_while_busy()
    impacts = settings.reload()
    return {**_payload(), "applied": _act(impacts)}

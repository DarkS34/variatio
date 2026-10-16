"""A commission: generate `n` exercises and save each one, with how it was made.

Registered on `server.jobs.catalogue.HANDLERS` by `consumers.generation.api.install`, not declared
there: the queue runs it as any other kind, and the construction's handlers know nothing of it.
"""

from importlib import metadata

from loguru import logger

from server import approvals, storage
from server import curriculum as curriculum_store
from server import generations as generations_store
from server.core import contexts, installation
from server.core.contexts import context_for
from server.db import identity, session_scope
from server.jobs import lanes
from server.jobs.catalogue import Job
from server.jobs.runner import JobControl
from variatio import config, entrypoints
from variatio.core import inference, progress
from variatio.core.workspace import Workspace
from variatio.loaders import locale

# The kind this module handles.
GENERATE = "generate"

_EFFORT_LEVELS = ("low", "medium", "high", "max")


def handle_generate(job: Job, control: JobControl) -> dict:
    """Generate `n` items on commission, saving each one the moment it validates.

    The curriculum is resolved FIRST and what is stored is the one that ran, never the one
    that was asked for, so a saved exercise is reproducible from its own file. `on_accepted`
    persists item by item, so a run cancelled after the third keeps three files.
    """
    contexts.require_inference()
    context = context_for(job)
    ws = installation.workspace_for(job.workspace)
    params = job.params
    # `or 1` was wrong on a falsy zero: "genera 0" produced one item and then recorded
    # `requested: 1`, falsifying the very thing a saved exercise exists to keep. An absent
    # `n` still means one; a zero travels as itself and the generator refuses it.
    n = 1 if params.get("n") is None else int(params["n"])
    concepts = params.get("concepts") or None
    item_type = params.get("item_type") or None
    fixed = params.get("fixed") or None
    omit = [str(name) for name in params.get("omit") or []] or None
    curriculum = curriculum_store.resolve(
        context.workspace, context.knowledge_graph, params.get("curriculum")
    )
    instructions = params.get("instructions") or None
    # Absent means "as it always was": a caller predating the switch reasons at the default
    # effort. A recognised level travels as itself; anything else collapses to a bool.
    raw_think = params.get("think", True)
    asked_think = raw_think if raw_think in _EFFORT_LEVELS else bool(raw_think)
    # Resolved here rather than deeper down because three things need the same answer: the
    # log line, the file saved for each item, and the call itself. An unoffered name
    # raises and the job fails with it said in one sentence — the submit route refused it
    # already, so getting here means the offered list changed under a queued job.
    model = entrypoints.resolve_generation_model(params.get("model"))
    # And with it the effort, because a model whose level the installation has locked is
    # not the requester's to adjust. Resolved here as well as inside `entrypoints.generate` —
    # the call is idempotent — so the log line and the file say what actually ran.
    think = entrypoints.resolve_generation_effort(model, asked_think)

    resolved_type = context.exemplars_profile.item_type(item_type)
    detail = _commission_detail(fixed, omit, curriculum, instructions, think)
    logger.info(
        f"Generando {n} ítem(s) de tipo «{resolved_type.label}» con "
        f"'{model}' sobre "
        + (", ".join(concepts) if concepts else "los conceptos más frecuentes del banco")
        + " — "
        + "; ".join(detail)
    )

    avoid = _recent_scenarios(job, ws, resolved_type, concepts)
    if avoid:
        logger.info(
            f"{len(avoid)} escenario(s) de ejercicios guardados entran en el prompt para no repetirse"
        )

    run = _run_record(job, ws, n, asked_think, model)
    run["resolved"].update(
        {"item_type": resolved_type.key, "curriculum": curriculum, "model": model, "effort": think}
    )
    saved_ids: dict[int, str] = {}

    def remember(result, index: int) -> None:
        """Persist one accepted item and tell the screen which file it became."""
        generation_id = _remember_one(job, ws, run, result, index)
        if generation_id is None:
            return
        saved_ids[index] = generation_id
        progress.emit("item.saved", index=index, id=generation_id)

    results = entrypoints.generate(
        context,
        concepts=concepts,
        item_type=resolved_type.key,
        n=n,
        fixed=fixed,
        curriculum=curriculum,
        instructions=instructions,
        think=think,
        model=model,
        avoid=avoid,
        on_accepted=remember,
        omit=omit,
    )
    if len(results) < n:
        logger.warning(f"{len(results)}/{n} ítem(s) validados; el resto no pasó el esquema")
    else:
        logger.success(f"{len(results)}/{n} ítem(s) generados y validados")

    items = [
        {
            "item": r.item.model_dump(mode="json"),
            "item_type": r.item_type,
            "thinking": r.thinking,
            "checks": r.checks,
            "retried": r.retried,
            "saved_id": saved_ids.get(i + 1),
        }
        for i, r in enumerate(results)
    ]
    return {
        "requested": n,
        "produced": len(results),
        "item_type": resolved_type.key,
        "model": model,
        "saved": len(saved_ids),
        "items": items,
    }


def _commission_detail(fixed, omit, curriculum, instructions, think) -> list[str]:
    """Spell out the parts of a commission that are not the concepts, for the log line."""
    detail = []
    if fixed:
        detail.append("campos fijados " + ", ".join(f"{k}={v}" for k, v in fixed.items()))
    if omit:
        detail.append("sin los campos " + ", ".join(omit))
    if curriculum:
        detail.append(f"currículo de {len(curriculum)} concepto(s)")
    if instructions:
        detail.append(f"instrucciones «{instructions}»")
    if isinstance(think, str):
        detail.append(f"con razonamiento ({think})")
    else:
        detail.append("con razonamiento" if think else "sin razonamiento")
    return detail


def _recent_scenarios(job: Job, ws: Workspace, item_type, concepts: list[str] | None) -> list[str]:
    """Read the statements of this account's last saved exercises, so the prompt can avoid them.

    Its OWN, never the instance's: a generated exercise is private to whoever asked for it,
    and reading a colleague's statement into somebody's prompt is that same reading through
    another door — so a job with no author reads nothing. A reminder and nothing more, so an
    unreadable directory costs the run nothing but this.
    """
    limit = int(config.GENERATION_AVOID_RECENT)
    if limit < 1 or job.user_id is None:
        return []
    try:
        items = generations_store.recent_items(
            ws, job.user_id, item_type=item_type.key, concepts=concepts, limit=limit
        )
    except Exception as exc:  # noqa: BLE001 - the run matters more than the reminder
        logger.warning(f"No se pudieron leer los ejercicios guardados recientes: {exc}")
        return []

    texts: list[str] = []
    for item in items:
        try:
            text = item_type.primary_text(item).strip()
        except (ValueError, AttributeError):
            continue
        if text:
            texts.append(text)
    return texts


# Read once per run and kept beside every item: what decides how a statement comes out
# beyond the commission and the artifacts, so two files can be read side by side.
_RECORDED_SETTINGS = (
    "TEMPERATURE_GENERATION",
    "CHECK_MAX_RETRIES",
    "MAX_FEW_SHOT_EXAMPLES",
    "MAX_JSON_REPAIR_TRIES",
    "REPAIR_LLM",
    "CONCEPT_TAGGER_LLM",
    "EMBEDDING_LLM",
    "EMBEDDER_SIMILARITY_THRESHOLD",
    "GUARDRAIL_LLM",
    "ADMISSIBILITY_LLM",
    "GENERATION_AVOID_RECENT",
)

# The sampling of every call a run makes, as configured: what the phase left empty is still
# empty here and was decided per call (`inference.sampling`).
_RECORDED_SAMPLING = ("guardrail", "admissibility", "variant_generation", "repair", "concept_tagger")


def _run_record(job: Job, ws: Workspace, n: int, asked_think, model: str) -> dict:
    """Assemble the half of every saved record that the whole run shares.

    `commission` is the request as it arrived — a `curriculum` of None is "the workspace's
    own", `[]` is "sin restricción" — and `resolved` starts with what this layer alone
    knows; the generator's provenance completes it per item.
    """
    params = job.params
    return {
        "workspace": ws.slug,
        "author": _author(job),
        "job": {"id": job.id, "requested": n},
        "commission": {
            "concepts": list(params.get("concepts") or []),
            "item_type": params.get("item_type") or None,
            "fixed": dict(params.get("fixed") or {}),
            "omit": [str(name) for name in params.get("omit") or []],
            "curriculum": params.get("curriculum"),
            "instructions": params.get("instructions") or None,
            "think": asked_think,
            "model": params.get("model") or None,
        },
        "resolved": {
            "engine": inference.engine_name(),
            "lane": lanes.backend_of(model),
            "prompt_language": locale.prompt_language(ws),
        },
        "inputs": _inputs(ws),
        "settings": {
            **{name: getattr(config, name, None) for name in _RECORDED_SETTINGS},
            "LLM_CONTEXT": (config.LLM_CONTEXT or {}).get(model),
            "SAMPLING": {phase: config.SAMPLING.get(phase) for phase in _RECORDED_SAMPLING},
        },
        "system_version": _system_version(),
    }


def _author(job: Job) -> dict:
    """Name the account a run belongs to, the username read best-effort from the database.

    The username travels so a workspace copied to another installation, where the ids
    differ, can still say whose each exercise was.
    """
    username = None
    if job.user_id is not None:
        try:
            with session_scope() as session:
                user = identity.get_user_by_id(session, job.user_id)
                username = user.username if user is not None else None
        except Exception as exc:  # noqa: BLE001 - a name is not worth a failed run
            logger.warning(f"No se pudo leer el usuario de la cuenta {job.user_id}: {exc}")
    return {"id": job.user_id, "username": username, "name": job.user_name}


def _inputs(ws: Workspace) -> dict[str, str | None]:
    """Hash every artifact a statement is generated against, as the approvals hash them."""
    hashes = {
        artifact: storage.sha256_of(approvals.current_path(ws, artifact))
        for artifact in approvals.ARTIFACTS
    }
    hashes["content_context"] = storage.sha256_of(entrypoints.content_context_path(ws))
    hashes["concept_descriptions"] = storage.sha256_of(ws.concept_descriptions_path)
    return hashes


def _system_version() -> str | None:
    """Return the installed version of this system, or None outside an installation."""
    try:
        return metadata.version("variatio")
    except metadata.PackageNotFoundError:
        return None


def _remember_one(job: Job, ws: Workspace, run: dict, result, index: int) -> str | None:
    """Save one validated item with how it was made, and return its id or `None`.

    Best-effort on purpose: a full disk must not turn a minute of GPU into a failed job —
    the item is already in the event stream and on screen, and only the record is lost.
    """
    try:
        body = {
            **run,
            "resolved": {**result.provenance, **run["resolved"]},
            "prompt": result.prompt,
            "output": {
                "item": result.item.model_dump(mode="json"),
                "thinking": result.thinking,
                "checks": result.checks,
                "retried": result.retried,
            },
        }
        return generations_store.save(ws, job.user_id, job.id, index, body)
    except Exception as exc:  # noqa: BLE001 - the item is on screen; only its record is lost
        logger.warning(f"No se pudo guardar el ejercicio generado: {exc}")
        return None

"""Phase 2b — one commission, three architectures, one blind comparison.

Mechanism, not policy, like the rest of `stages/`: it returns an `EvaluationSession`,
raises exceptions and NEVER writes to disk or knows about a database. Persisting is
`server/evaluation_store.py`'s job, which is what lets a batch mode reuse this untouched.
"""

import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from .. import config, guardrail, progress
from ..content_generator import clean_fixed
from ..evaluation import ARMS, FAILED, ArmResult, Commission, EvaluationSession, run_arm
from .initialize import PipelineContext


def evaluate(
    context: PipelineContext,
    concepts: list[str],
    item_type: str | None = None,
    fixed: dict[str, object] | None = None,
    curriculum: list[str] | None = None,
    instructions: str | None = None,
    seed: int | None = None,
    job_id: str | None = None,
) -> EvaluationSession:
    target_type = context.exemplars_profile.item_type(item_type)

    # Both draws come from the same seed and happen before anything runs, so the session
    # is reproducible from `seed` alone months later, when the memoria is being written.
    #
    # THE REASONING MODE IS DRAWN, NOT CHOSEN. The Generate screen offers it as a switch
    # because there the user is asking for an item; here it is the thing being measured,
    # and an evaluator who decides it decides it in correlation with their own mood, the
    # time they have and what they expect to see. Sorted at random it becomes a condition
    # whose effect can be read off the sessions afterwards. It is identical for the local
    # arms within a session, so it never enters the comparison BETWEEN architectures.
    seed = random.randrange(2**31) if seed is None else int(seed)
    draw = random.Random(seed)
    order = list(ARMS)
    draw.shuffle(order)
    think = draw.random() < 0.5
    logger.info(f"Semilla {seed}: razonamiento {'activado' if think else 'desactivado'}")

    commission = Commission(
        concepts=list(concepts),
        item_type=target_type.key,
        fixed=clean_fixed(fixed),
        curriculum=list(curriculum or []),
        instructions=(instructions or "").strip(),
        think=think,
    )
    _validate(context, target_type, commission)

    # Once, before the commission is handed out: it judges the user's text, not the arm.
    # If it blocks, the session never comes into existence.
    _screen(commission.instructions)

    results: dict[str, ArmResult] = {}
    # The external arm is network, not GPU: it overlaps with the local ones for free,
    # and its 3-8 s disappear from the wall clock.
    with ThreadPoolExecutor(max_workers=1) as pool:
        external = pool.submit(_safe_run, "naive", commission, context)

        # One GPU, one job at a time — as `jobs/runner.py` declares. Serialised on purpose.
        #
        # The step counts work done and NEVER names a position: emitting "propuesta 2 de 3"
        # in execution order would tell the evaluator which card was produced by which arm,
        # which is exactly the leak the shuffling is there to prevent.
        with progress.step("eval.arms", "Preparando las tres propuestas", total=3) as reporter:
            for done, arm in enumerate(("rag", "system"), start=1):
                progress.checkpoint()
                results[arm] = _safe_run(arm, commission, context)
                reporter.tick(done)
            results["naive"] = external.result()
            reporter.tick(3)

    logger.info(
        "Propuestas: "
        + ", ".join(f"{arm} {results[arm].status} en {results[arm].elapsed_ms} ms" for arm in ARMS)
    )

    return EvaluationSession(
        id=uuid.uuid4().hex[:12],
        created_at=time.time(),
        concepts=commission.concepts,
        item_type=commission.item_type,
        fixed=commission.fixed,
        curriculum=commission.curriculum,
        instructions=commission.instructions,
        seed=seed,
        shuffle=order,
        think=commission.think,
        arms=results,
        job_id=job_id,
    )


# A crash in one arm is a datum about that arm, never the end of the session: a run
# that dies because the commercial provider changed its JSON is a run of data lost.
def _safe_run(arm: str, commission: Commission, context) -> ArmResult:
    try:
        return run_arm(arm, commission, context)
    except progress.Cancelled:
        raise
    except Exception as e:  # noqa: BLE001 - reported as a failed arm, never swallowed
        logger.warning(f"La propuesta «{arm}» falló: {type(e).__name__}: {e}")
        return ArmResult(
            arm=arm,
            status=FAILED,
            item=None,
            raw_response="",
            prompt="",
            model="",
            provider="",
            exemplar_ids=[],
            elapsed_ms=0,
            error=f"{type(e).__name__}: {e}",
        )


def _screen(instructions: str) -> None:
    if not instructions:
        return
    with progress.step("eval.guardrail", "Revisando el encargo"):
        verdict = guardrail.check(instructions)
        if verdict.blocked:
            raise ValueError(
                f"Las instrucciones adicionales no han pasado la revisión: "
                f"el modelo juez ha detectado {verdict.reason}."
            )


# Checked here rather than inside the arms: an invalid commission must fail the whole
# request, not come back as two happy proposals and one arm that "failed".
def _validate(context: PipelineContext, item_type, commission: Commission) -> None:
    taggable = set(context.knowledge_graph.taggable_concepts)

    if not commission.concepts:
        raise ValueError("concepts must be a non-empty list")
    unknown = [c for c in commission.concepts if c not in taggable]
    if unknown:
        raise ValueError(f"Unknown concepts (not in KG taggable set): {unknown}")

    unknown_fields = [k for k in commission.fixed if k not in item_type.field_specs]
    if unknown_fields:
        raise ValueError(
            f"Unknown fixed fields for item type '{item_type.key}': {unknown_fields} "
            f"(it declares {list(item_type.field_specs)})"
        )

    if commission.curriculum:
        unknown_curriculum = [c for c in commission.curriculum if c not in taggable]
        if unknown_curriculum:
            raise ValueError(
                f"Unknown curriculum concepts (not in KG taggable set): {unknown_curriculum}"
            )
        outside = [c for c in commission.concepts if c not in set(commission.curriculum)]
        if outside:
            raise ValueError(f"Target concepts not contained in curriculum: {outside}")

    if len(commission.instructions) > config.GENERATION_INSTRUCTIONS_MAX_CHARS:
        raise ValueError(
            f"instructions must be at most {config.GENERATION_INSTRUCTIONS_MAX_CHARS} "
            f"characters, got {len(commission.instructions)}"
        )

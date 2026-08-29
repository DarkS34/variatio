"""One commission, three architectures, one blind comparison.

Mechanism, not policy, in the way `variatio.stages` is: it returns an `EvaluationSession`,
raises exceptions and NEVER writes to disk or knows about a database. Persisting is
`study/api/store.py`'s job, which is what lets a batch mode reuse this untouched.
"""

import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from loguru import logger

from variatio import admissibility, config, guardrail
from variatio.core import progress
from variatio.stages.initialize import PipelineContext
from variatio.variatio import _sentence_case, clean_fixed

from . import ARMS, FAILED, ArmResult, Commission, EvaluationSession, run_arm


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
    """Run one commission through the three architectures and return the blind session.

    The order of the cards and the reasoning mode are both DRAWN from `seed`, before
    anything runs, so a session is reproducible from that number alone. The reasoning mode
    is the condition being measured and is identical for the three arms within a session,
    which is what keeps it out of the comparison between them.
    """
    target_type = context.exemplars_profile.item_type(item_type)

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

    # The ruling travels ON the commission so the `system` arm does not screen the same
    # text a second time; `naive` and `rag` receive the free text untyped.
    ruling = _screen(context, target_type, commission)
    commission = replace(commission, ruling=ruling)

    results: dict[str, ArmResult] = {}
    # The external arm is network, not GPU: it overlaps with the local ones for free.
    with ThreadPoolExecutor(max_workers=1) as pool:
        external = pool.submit(_safe_run, "naive", commission, context)

        # The two local arms are serialised: one GPU, one job at a time. The step counts
        # work done and NEVER names a position — «propuesta 2 de 3» in execution order
        # would tell the evaluator which card each arm produced.
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


def _safe_run(arm: str, commission: Commission, context) -> ArmResult:
    """Run one arm, recording a crash as a failed result rather than losing the session.

    A run that dies because the commercial provider changed its JSON is a run of data lost;
    a cancellation still propagates.
    """
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


def _screen(context, item_type, commission: Commission):
    """Pay the guardrail and the admissibility judge ONCE, and return the ruling.

    Guardrail first, admissibility second, as the pipeline orders them. Either one blocking
    raises, so the session never comes into existence rather than recording a refusal.
    """
    if not commission.instructions:
        return admissibility.Ruling(requests=(), checked=True)

    with progress.step("eval.guardrail", "Revisando el encargo"):
        verdict = guardrail.check(commission.instructions)
        if verdict.blocked:
            raise ValueError(
                f"Las instrucciones adicionales no han pasado la revisión: "
                f"se ha detectado {verdict.reason}."
            )

    with progress.step("eval.admissibility", "Revisando el alcance del encargo"):
        ruling = admissibility.screen(
            commission.instructions,
            admissibility.owners(
                context.knowledge_graph,
                item_type,
                context.exemplars_profile,
                context.content_context,
                commission.concepts,
            ),
            commission.concepts,
            context.prompts,
            context.content_context.prompt_block(),
        )
        if not ruling.ok:
            first = ruling.blocked[0]
            raise ValueError(
                f"«{first.text}» no se pide aquí: lo decide {first.owner.label} "
                f"(«{first.term}»). {_sentence_case(first.owner.where)}."
            )
    return ruling


def _validate(context: PipelineContext, item_type, commission: Commission) -> None:
    """Raise ValueError unless the commission is runnable by all three arms.

    Checked here rather than inside the arms: an invalid commission must fail the whole
    request, not come back as two happy proposals and one arm that «failed».
    """
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
        known = set(context.knowledge_graph.all_concepts)
        unknown_curriculum = [c for c in commission.curriculum if c not in known]
        if unknown_curriculum:
            raise ValueError(
                f"Unknown curriculum concepts (not in the knowledge graph): {unknown_curriculum}"
            )
        outside = [c for c in commission.concepts if c not in set(commission.curriculum)]
        if outside:
            raise ValueError(f"Target concepts not contained in curriculum: {outside}")

    if len(commission.instructions) > config.GENERATION_INSTRUCTIONS_MAX_CHARS:
        raise ValueError(
            f"instructions must be at most {config.GENERATION_INSTRUCTIONS_MAX_CHARS} "
            f"characters, got {len(commission.instructions)}"
        )

"""One commission, three architectures, one blind comparison.

Mechanism, not policy, in the way `variatio.entrypoints` is: it returns an `EvaluationSession`,
raises exceptions and NEVER writes to disk or knows about a database. Persisting is
`evaluation/api/store.py`'s job, which is what lets a batch mode reuse this untouched.
"""

import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from loguru import logger

from variatio import config, entrypoints
from variatio.runtime import checks, screening
from variatio.core import progress
from variatio.entrypoints.initialize import RuntimeContext
from variatio.runtime.generator import clean_fixed, forbidden

from . import ARMS, FAILED, ArmResult, Commission, EvaluationSession, run_arm
from . import config as evaluation_config


def evaluate(
    context: RuntimeContext,
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

    The writer of the two local arms is the installation's (`evaluation.local_model`, read
    through `evaluation.config.LOCAL_MODEL`), never the commission's: what is compared is
    architectures, and the person asking for a comparison does not pick the model.
    """
    target_type = context.exemplars_profile.item_type(item_type)
    writer = evaluation_config.LOCAL_MODEL

    seed = random.randrange(2**31) if seed is None else int(seed)
    draw = random.Random(seed)
    order = list(ARMS)
    draw.shuffle(order)
    think = draw.random() < 0.5
    logger.info(
        f"Semilla {seed}: razonamiento {'activado' if think else 'desactivado'}; "
        f"las dos propuestas locales las escribe '{writer}'"
    )

    commission = Commission(
        concepts=list(concepts),
        item_type=target_type.key,
        fixed=clean_fixed(fixed),
        curriculum=list(curriculum or []),
        instructions=(instructions or "").strip(),
        think=think,
        model=writer,
        effort=entrypoints.resolve_generation_effort(writer, think),
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

    _tag(context, target_type, commission, results)

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


def off_limits(context, commission: Commission) -> list[str]:
    """Return the concepts this commission put out of bounds.

    Exactly the set `VariantGenerator` renders into the «no menciones» block of the system
    arm's prompt — `forbidden` over the dependent closure — and it is read from the same
    two functions so the two cannot drift. That identity is the whole point of using it
    here: the line under a proposal answers whether it broke the one rule the system was
    given, and the three arms are held to it alike even though only one of them was told.

    With no curriculum it degrades to the whole downstream closure, which is the closed
    decision `forbidden` already carries: nobody said what the class has covered, so what
    comes AFTER the targets is the only thing that can be called not yet taught.
    """
    closure = context.knowledge_graph.dependent_closure(
        commission.concepts, context.generator.prerequisite_relation
    )
    return forbidden(closure, commission.curriculum or None)


def _annotate(context, item_type, result: ArmResult) -> dict:
    """Return one proposal's concepts and the one it practises, as the bank's tagger reads them.

    The system arm has already been tagged — `checks.tagger_roundtrip` runs the same tagger
    over the very text this would render again — so tagging it a second time would pay a
    model call for an identical answer AND let the card disagree with the flag beside it.
    """
    reuse = (result.checks or {}).get("tagger")
    if reuse:
        return {"concepts": list(reuse.get("concepts") or []), "primary": reuse.get("primary")}
    annotation = context.tagger.tag(item_type.embed_text(result.item))
    return {
        "concepts": list(annotation.get("concepts") or []),
        "primary": annotation.get("primary_concept"),
    }


def _trespasses(
    item: dict, tagged: list[str], primary: str | None, limits: list[str], rule: str
) -> list[str]:
    """Return the out-of-bounds concepts this proposal brought in, under the rule in force.

    Under `RULE_MENTIONS` (a curriculum was given) it is the union of two readings, because
    the failure to avoid there is missing one: the tagger says what the exercise IS ABOUT
    and catches a proposal that leans on a later concept without naming it;
    `checks.forbidden_mentions` — the pipeline's own rule, called and not copied — says what
    it NAMES and catches what the tagger's candidate band did not surface. Under
    `RULE_PRACTISES` (no curriculum) only the PRIMARY concept counts, exactly as in
    `checks.run`: nobody said what the class has seen, so a mention holds nothing against
    the proposal, and what does is practising something after the target.
    """
    if rule == checks.RULE_PRACTISES:
        return checks.practised_later(primary, limits)
    limited = set(limits)
    return sorted(
        {name for name in tagged if name in limited} | set(checks.forbidden_mentions(item, limits))
    )


def _tag(context, item_type, commission: Commission, results: dict[str, ArmResult]) -> None:
    """Read the three proposals through the graph, and name what each one should not have used.

    Run AFTER the arms and never inside one: an arm must produce its item under exactly the
    conditions it is being measured on, and a tagging call inside the rag arm would land in
    its `elapsed_ms`. The step is over the proposals as a set and names no position, so it
    passes the blind filter without saying which card is which.

    It never costs a session: a tagger that fails leaves that proposal unread — the card
    then shows no concepts — where raising would throw away three generations.
    """
    limits = off_limits(context, commission)
    rule = checks.closure_rule(commission.curriculum)
    produced = [arm for arm in ARMS if results[arm].item]
    if not produced:
        return

    with progress.step(
        "eval.tagging", "Etiquetando las propuestas", total=len(produced)
    ) as reporter:
        for done, arm in enumerate(produced, start=1):
            progress.checkpoint()
            result = results[arm]
            try:
                annotation = _annotate(context, item_type, result)
            except progress.Cancelled:
                raise
            except Exception as e:  # noqa: BLE001 - one unread proposal, never a lost session
                logger.warning(
                    f"No se pudo etiquetar la propuesta «{arm}»: {type(e).__name__}: {e}"
                )
                reporter.tick(done)
                continue
            result.tagging = {
                **annotation,
                "rule": rule,
                "off_limits": _trespasses(
                    result.item, annotation["concepts"], annotation["primary"], limits, rule
                ),
            }
            reporter.tick(done)

    logger.info(
        "Etiquetado de las propuestas: "
        + ", ".join(
            f"{arm} {len((results[arm].tagging or {}).get('concepts') or [])} concepto(s), "
            f"{len((results[arm].tagging or {}).get('off_limits') or [])} fuera de lo permitido"
            for arm in produced
        )
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

    `screening.screen_instructions` is the pipeline's own sequence; the prefix is all that
    tells these steps from a generation's. Either screen blocking raises, so the session
    never comes into existence rather than recording a refusal.
    """
    return screening.screen_instructions(
        commission.instructions,
        knowledge_graph=context.knowledge_graph,
        item_type=item_type,
        profile=context.exemplars_profile,
        content_context=context.content_context,
        concepts=commission.concepts,
        prompts=context.prompts,
        step_prefix="eval.",
    )


def _validate(context: RuntimeContext, item_type, commission: Commission) -> None:
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

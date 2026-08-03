"""What each job kind actually does. One place, so the runner stays generic."""

from variant_generator import stages

from .. import deps, review
from .build_process import run_build
from .models import Job
from .runner import JobControl


def _build(artifact: str):
    def handler(job: Job, control: JobControl) -> dict:
        return run_build(artifact, control)

    return handler


def handle_describe_concepts(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    concepts = job.params.get("concepts")
    overwrite = bool(job.params.get("overwrite"))
    descriptions = stages.describe_concepts(concepts=concepts, overwrite=overwrite)
    # New prose means new embeddings; the cached context would keep matching the old.
    deps.invalidate("descripciones de conceptos regeneradas")
    return {"described": len(descriptions)}


def handle_index(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = deps.reload_context()
    return {
        "concepts": len(context.embedder.concepts_index),
        "items": len(context.exemplars_bank),
    }


def handle_tag(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = deps.get_context()
    ids = job.params.get("ids") or None
    bank = stages.tag_bank(context, ids=ids)
    untagged = [i for i, item in bank.items() if not item.get("concepts")]
    return {
        "items": len(bank),
        "tagged": len(bank) - len(untagged),
        "untagged": len(untagged),
    }


def handle_generate(job: Job, control: JobControl) -> dict:
    deps.require_inference()
    context = deps.get_context()
    params = job.params
    n = int(params.get("n") or 1)
    results = stages.generate(
        context,
        concepts=params.get("concepts") or None,
        n=n,
        fixed=params.get("fixed") or None,
        curriculum=params.get("curriculum") or None,
    )
    return {
        "requested": n,
        "produced": len(results),
        "items": [
            {"item": r.item.model_dump(mode="json"), "thinking": r.thinking} for r in results
        ],
    }


HANDLERS = {
    "build_profile": _build(review.CONTENT_PROFILE),
    "build_kg": _build(review.KNOWLEDGE_GRAPH),
    "build_bank": _build(review.EXEMPLARS_BANK),
    "describe_concepts": handle_describe_concepts,
    "index": handle_index,
    "tag": handle_tag,
    "generate": handle_generate,
}

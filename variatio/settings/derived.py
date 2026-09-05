"""What the registry does not store: the phase models, the context map and the efforts."""

from .registry.reasoning import PHASE_KEYS

PHASES = {
    "models.phases.transcribe": "TRANSCRIBE_MODEL",
    "models.phases.transcribe_seam": "TRANSCRIBE_SEAM_MODEL",
    "models.phases.ep_scan": "EP_SCAN_MODEL",
    "models.phases.ep_consolidate": "EP_CONSOLIDATE_MODEL",
    "models.phases.ep_context": "EP_CONTEXT_MODEL",
    "models.phases.eb_extract": "EB_EXTRACT_MODEL",
    "models.phases.kg_extract": "KG_EXTRACT_MODEL",
    "models.phases.kg_clean_merge": "KG_CLEAN_MERGE_MODEL",
    "models.phases.kg_clean_drop": "KG_CLEAN_DROP_MODEL",
    "models.phases.kg_units": "KG_UNITS_MODEL",
    "models.phases.kg_domains": "KG_DOMAINS_MODEL",
    "models.phases.kg_domains_leftovers": "KG_DOMAINS_LEFTOVERS_MODEL",
    "models.phases.kg_link_domain": "KG_LINK_DOMAIN_MODEL",
    "models.phases.kg_link_cross_domain": "KG_LINK_CROSS_DOMAIN_MODEL",
    "models.phases.kg_context": "KG_CONTEXT_MODEL",
    "models.phases.description_generation": "DESCRIPTION_GENERATION_LLM",
    "models.phases.kg_taggable": "KG_TAGGABLE_MODEL",
    "models.phases.concept_tagger": "CONCEPT_TAGGER_LLM",
    "models.phases.repair": "REPAIR_LLM",
    "models.phases.admissibility": "ADMISSIBILITY_LLM",
}


def derive(values: dict[str, object]) -> dict[str, object]:
    """Compute the `config` attributes no setting holds, from the resolved values.

    A phase's `THINK_*` is `False` or its effort as a string, never `True`: the boolean is
    turned into a level at the last hop, by the engine.
    """
    # The registry declares the bare `host:port` a person writes; every consumer wants a URL.
    host = str(values["engine.ollama_host"])
    out: dict[str, object] = {
        "OLLAMA_HOST": host if host.startswith(("http://", "https://")) else f"http://{host}",
        "EMBEDDING_MODELS": (values["models.embedding"],),
        "TEMPERATURE_DEFAULT": values["sampling.temperature_deterministic"],
    }

    # Every phase names its own model and none may be empty: there is nothing to resolve.
    for key, name in PHASES.items():
        out[name] = values[key]

    # The writer of a variant is not a phase model any more: the commission picks one of
    # the offered models, and the FIRST of them is what everything that does not pick uses
    # — the CLI, the evaluation's three arms, and a request naming none. Indexed without a
    # guard because `min_items=1` is what refuses an empty list, file and panel included.
    offered = [str(model) for model in values["generation.models"]]
    out["VARIANT_GENERATION_LLM"] = offered[0]

    for phase in PHASE_KEYS:
        on = values[f"reasoning.phases.{phase}"]
        out[f"THINK_{phase.upper()}"] = values[f"reasoning.effort.{phase}"] if on else False

    out["LLM_CONTEXT"] = {
        values["models.guardrail"]: values["context_window.guardrail"],
        values["models.embedding"]: values["context_window.embedding"],
    }
    for name in PHASES.values():
        out["LLM_CONTEXT"].setdefault(out[name], values["context_window.overrides"])
    # Every offered model and not only the default: choosing the second one would
    # otherwise run it at whatever context its Modelfile declares, which is the reservation
    # this map exists to cap.
    for model in offered:
        out["LLM_CONTEXT"].setdefault(model, values["context_window.overrides"])
    return out

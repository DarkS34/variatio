from ..instance.relations import BUILTIN_SCHEMAS
from .registry.reasoning import PHASE_KEYS

PHASES = {
    "models.phases.exemplars_transcribe": "EXEMPLARS_TRANSCRIBE_MODEL",
    "models.phases.ep_scan": "EP_SCAN_MODEL",
    "models.phases.ep_consolidate": "EP_CONSOLIDATE_MODEL",
    "models.phases.ep_context": "EP_CONTEXT_MODEL",
    "models.phases.eb_extract": "EB_EXTRACT_MODEL",
    "models.phases.kg_extract": "KG_EXTRACT_MODEL",
    "models.phases.kg_clean_merge": "KG_CLEAN_MERGE_MODEL",
    "models.phases.kg_clean_drop": "KG_CLEAN_DROP_MODEL",
    "models.phases.kg_domains": "KG_DOMAINS_MODEL",
    "models.phases.kg_domains_leftovers": "KG_DOMAINS_LEFTOVERS_MODEL",
    "models.phases.kg_link_domain": "KG_LINK_DOMAIN_MODEL",
    "models.phases.kg_link_cross_domain": "KG_LINK_CROSS_DOMAIN_MODEL",
    "models.phases.kg_taggable": "KG_TAGGABLE_MODEL",
    "models.phases.kg_context": "KG_CONTEXT_MODEL",
    "models.phases.description_generation": "DESCRIPTION_GENERATION_LLM",
    "models.phases.concept_tagger": "CONCEPT_TAGGER_LLM",
    "models.phases.variant_generation": "VARIANT_GENERATION_LLM",
    "models.phases.repair": "REPAIR_LLM",
    "models.phases.admissibility": "ADMISSIBILITY_LLM",
}


def derive(values: dict[str, object]) -> dict[str, object]:
    main = values["models.main"]
    schema = BUILTIN_SCHEMAS[values["builders.kg_relation_schema"]]

    # The registry declares the bare `host:port` because that is what a person writes and
    # what `OLLAMA_HOST` has always held. Every consumer wants a URL, so the scheme is added
    # here rather than at each call site, and a value that already carries one is left alone.
    host = str(values["engine.ollama_host"])
    out: dict[str, object] = {
        "OLLAMA_HOST": host if host.startswith(("http://", "https://")) else f"http://{host}",
        "RELATION_SCHEMA": schema,
        "KG_PREREQUISITE_RELATION": schema.prerequisite_verbose,
        "EMBEDDING_MODELS": (values["models.embedding"],),
        "TEMPERATURE_DEFAULT": values["sampling.temperature_deterministic"],
    }

    for key, name in PHASES.items():
        out[name] = values.get(key) or main

    for phase in PHASE_KEYS:
        on = values[f"reasoning.phases.{phase}"]
        out[f"THINK_{phase.upper()}"] = values[f"reasoning.effort.{phase}"] if on else False

    out["LLM_CONTEXT"] = {
        main: values["context_window.main"],
        values["models.guardrail"]: values["context_window.guardrail"],
        values["models.embedding"]: values["context_window.embedding"],
    }
    for name in PHASES.values():
        out["LLM_CONTEXT"].setdefault(out[name], values["context_window.overrides"])
    return out

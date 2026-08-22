import os

from loguru import logger

from ..relations import BUILTIN_SCHEMAS

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
        "EVAL_RAG_TOP_K": values["generation.max_few_shot_examples"],
    }

    for key, name in PHASES.items():
        out[name] = values.get(key) or main

    out["LLM_CONTEXT"] = {
        main: values["context_window.main"],
        values["models.guardrail"]: values["context_window.guardrail"],
        values["models.embedding"]: values["context_window.embedding"],
    }
    for name in PHASES.values():
        if out[name] not in out["LLM_CONTEXT"]:
            logger.warning(
                f"[config] '{out[name]}' no declara ventana de contexto: "
                "la fija Ollama desde su Modelfile"
            )

    providers = _chain(values["evaluation.providers"])
    models = {
        "gemini": values["evaluation.models.gemini"],
        "groq": values["evaluation.models.groq"],
    }
    keys = {
        "gemini": values["evaluation.keys.gemini"],
        "groq": values["evaluation.keys.groq"],
    }

    # An environment still exporting the old single-provider pair keeps working. The pair
    # moves TOGETHER onto whichever provider the chain leads with, because a key and a
    # model id from different providers is precisely the mix-up this prevents.
    legacy = os.environ.get("EVAL_EXTERNAL_API_KEY", "")
    first = providers[0] if providers else ""
    if legacy and first in keys and not keys[first]:
        keys[first] = legacy
        models[first] = os.environ.get("EVAL_EXTERNAL_MODEL_ID", "") or models[first]

    out["EVAL_EXTERNAL_PROVIDERS"] = providers
    out["EVAL_PROVIDER_MODELS"] = models
    out["EVAL_PROVIDER_KEYS"] = keys
    return out


def _chain(declared) -> list[str]:
    chain: list[str] = []
    for name in declared:
        name = str(name).strip().lower()
        if name and name != "none" and name not in chain:
            chain.append(name)
    return chain

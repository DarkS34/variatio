import type { Key } from "@/lib/i18n";

/**
 * WHICH SETTINGS CARRY AN (i), AND WHAT IT SAYS.
 *
 * The registry's `doc` is the measurement behind a value, written for whoever changes it in
 * the code, and it never reaches the panel. What a row may say instead is one sentence, and
 * only where it is needed: the name does not tell what the setting controls, or changing it
 * has a consequence nobody would guess. A setting absent here draws no (i) at all — the
 * phases' models and reasoning are explained by the pipeline drawing, and a name that
 * already reads plainly needs nothing beside it.
 *
 * Keyed by the registry's stable key, translated like every other sentence.
 */
const SETTING_HINTS: Record<string, Key> = {
  "engine.name": "cfg.hint.engine.name",
  "engine.cerebras_max_wait_seconds": "cfg.hint.engine.cerebras_max_wait_seconds",
  "engine.cerebras_max_concurrent_jobs": "cfg.hint.engine.cerebras_max_concurrent_jobs",
  "engine.idle_unload_seconds": "cfg.hint.engine.idle_unload_seconds",
  "engine.idle_unload_poll_seconds": "cfg.hint.engine.idle_unload_poll_seconds",
  "sampling.temperature_deterministic": "cfg.hint.sampling.temperature_deterministic",
  "sampling.temperature_reasoning": "cfg.hint.sampling.temperature_reasoning",
  "sampling.phases.repair.temperature": "cfg.hint.sampling.phases.repair.temperature",
  "context_window.guardrail": "cfg.hint.context_window.guardrail",
  "context_window.embedding": "cfg.hint.context_window.embedding",
  "context_window.overrides": "cfg.hint.context_window.overrides",
  "builders.transcribe_dpi": "cfg.hint.builders.transcribe_dpi",
  "sampling.phases.transcribe.temperature": "cfg.hint.sampling.phases.transcribe.temperature",
  "builders.transcribe_max_output_tokens": "cfg.hint.builders.transcribe_max_output_tokens",
  "builders.transcribe_seam_chars": "cfg.hint.builders.transcribe_seam_chars",
  "builders.exemplars_ocr": "cfg.hint.builders.exemplars_ocr",
  "builders.eb_batch_overlap_blocks": "cfg.hint.builders.eb_batch_overlap_blocks",
  "builders.kg_extract_gleaning_passes": "cfg.hint.builders.kg_extract_gleaning_passes",
  "builders.kg_max_source_passages": "cfg.hint.builders.kg_max_source_passages",
  "builders.kg_merge_qualifier_pattern": "cfg.hint.builders.kg_merge_qualifier_pattern",
  "builders.kg_unclassified_domain": "cfg.hint.builders.kg_unclassified_domain",
  "builders.kg_title_ubiquity": "cfg.hint.builders.kg_title_ubiquity",
  "builders.kg_merge_similarity": "cfg.hint.builders.kg_merge_similarity",
  "retrieval.query_prefix": "cfg.hint.retrieval.query_prefix",
  "retrieval.document_prefix": "cfg.hint.retrieval.document_prefix",
  "retrieval.field_max_chars": "cfg.hint.retrieval.field_max_chars",
  "retrieval.max_chars": "cfg.hint.retrieval.max_chars",
  "retrieval.similarity_threshold": "cfg.hint.retrieval.similarity_threshold",
  "retrieval.description_weight": "cfg.hint.retrieval.description_weight",
  "retrieval.description_siblings_top_k": "cfg.hint.retrieval.description_siblings_top_k",
  "retrieval.description_collision_similarity":
    "cfg.hint.retrieval.description_collision_similarity",
  "generation.tagger_top_k": "cfg.hint.generation.tagger_top_k",
  "generation.tagger_fallback_top_k": "cfg.hint.generation.tagger_fallback_top_k",
  "generation.check_similarity_threshold": "cfg.hint.generation.check_similarity_threshold",
  "generation.check_max_retries": "cfg.hint.generation.check_max_retries",
  "generation.avoid_recent": "cfg.hint.generation.avoid_recent",
  "evaluation.local_model": "cfg.hint.evaluation.local_model",
  "evaluation.providers": "cfg.hint.evaluation.providers",
  "evaluation.timeout": "cfg.hint.evaluation.timeout",
};

export function settingHint(key: string): Key | null {
  return SETTING_HINTS[key] ?? null;
}

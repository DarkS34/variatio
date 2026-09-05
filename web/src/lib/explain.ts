import type { Key } from "@/lib/i18n";

/**
 * What the pipeline is doing, in words.
 *
 * The core emits step ids written for whoever wrote the code. This is the other half: for
 * every step that reaches the UI, one sentence saying what is happening and why it takes
 * as long as it does.
 *
 * Two things it used to hold are gone with their readers, which is this repo's rule about
 * dead code: `describeEvent` went with «Qué ha ido pasando» on 2026-09-02, and `JOB_EXPLAIN`
 * — three sentences per job kind — on 2026-09-05, having outlived the run drawer that drew
 * them by four days and the panel by longer. Its 27 keys per catalogue went with it.
 */

const STEP_IDS = [
  "context",
  "load_instance",
  "descriptions",
  "index_concepts",
  "embed_bank",
  "embed_queries",
  "tagging",
  "guardrail",
  "admissibility",
  "generate",
  "check",
  "build_exemplars_profile",
  "build_knowledge_graph",
  "build_exemplars_bank",
  "kg_convert",
  "kg_extract",
  "kg_merge",
  "kg_drop",
  "kg_domains",
  "kg_link",
  "kg_curate",
  "taggability",
  "convert",
  "transcribe_documents",
  "transcribe",
  "transcribe_image",
  "transcribe_seam",
  "extract",
  "extract_batches",
  "scan",
  "consolidate",
  "eval.arms",
  "eval.guardrail",
  "eval.admissibility",
  "eval.tagging",
  "eval_rag_index_corpus",
  "eval_rag_index_exemplars",
];

// Derived rather than written out: a step id and its key differ by a prefix, and two lists
// of the same names is one more thing to keep in step.
//
// IT HAS TO MATCH WHAT THE SERVER ACTUALLY EMITS, and for a while it did not. Four ids
// here named nothing — `sample` and `infer_profile` predate the profile builder emitting
// `convert`/`scan`/`consolidate`, `kg_clean` predates the split into `kg_merge`/`kg_drop`,
// and `kg_taggability` was a misspelling of `taggability`. That last one cost the
// taggability review its (i) entirely: the step drew with no explanation while a perfectly
// good paragraph sat in both catalogues under a key nothing could ask for.
export const STEP_EXPLAIN: Record<string, Key> = Object.fromEntries(
  STEP_IDS.map((id) => [id, `step.${id}` as Key]),
);

export function stepExplain(id: string): Key | null {
  return STEP_EXPLAIN[id] ?? null;
}

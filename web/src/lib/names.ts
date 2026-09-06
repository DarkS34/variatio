import type { Key } from "@/lib/i18n";
import type { ArtifactName, JobKind } from "@/lib/types";

/**
 * WHAT THE SERVER NAMES, SAID IN THE READER'S LANGUAGE.
 *
 * The API sends a `label` with every stage and every job, and it is written in the API's
 * own language — so an account reading the interface in English still met "Perfil de
 * ejemplares" on the panel's cards and "Construir el grafo de conocimiento" in the run
 * log. What identifies a stage is its ARTIFACT and a job its KIND, both stable strings
 * that say nothing about who is reading, so the wording belongs in the catalogue like
 * every other sentence and this is the table between the two.
 *
 * Same shape and same reason as `lib/raw.ts` for the raw slots and `lib/evaluator.ts` for
 * the evaluator profiles: an enumerable set the server sends by name is translated here,
 * never rendered as it arrives.
 *
 * The server's own `label` survives as the fallback, which is what an API newer than the
 * bundle looks like — a stage or a job kind this browser has never heard of still gets a
 * name, just not one it chose.
 */

const ARTIFACT_KEYS: Record<string, Key> = {
  exemplars_profile: "artifact.profile",
  knowledge_graph: "artifact.graph",
  exemplars_bank: "artifact.bank",
};

/**
 * The call to build, one per step: what does not exist yet and which slot is read to make
 * it, since the four steps do not read the same one. The sentence about how long it takes
 * is shared.
 *
 * Same fallback as every other table here: an artifact this bundle has never heard of still
 * gets the generic pair rather than nothing.
 */
const BUILD_CALL: Record<string, { title: Key; body: Key }> = {
  exemplars_profile: { title: "build.call.profile.title", body: "build.call.profile.body" },
  knowledge_graph: { title: "build.call.graph.title", body: "build.call.graph.body" },
  exemplars_bank: { title: "build.call.bank.title", body: "build.call.bank.body" },
};

export function buildCall(artifact: string): { title: Key; body: Key } | null {
  return BUILD_CALL[artifact] ?? null;
}

const JOB_KEYS: Record<string, Key> = {
  build_profile: "job.build_profile.label",
  build_kg: "job.build_kg.label",
  build_bank: "job.build_bank.label",
  transcribe: "job.transcribe.label",
  describe_concepts: "job.describe_concepts.label",
  index: "job.index.label",
  tag: "job.tag.label",
  review_taggability: "job.review_taggability.label",
  generate: "job.generate.label",
  evaluate: "job.evaluate.label",
};

export function artifactName(
  artifact: ArtifactName | string,
  t: (key: Key) => string,
  fallback?: string,
): string {
  const key = ARTIFACT_KEYS[artifact];
  return key ? t(key) : (fallback ?? artifact);
}

export function jobName(
  kind: JobKind | string,
  t: (key: Key) => string,
  fallback?: string,
): string {
  const key = JOB_KEYS[kind];
  return key ? t(key) : (fallback ?? kind);
}

/**
 * WHAT A RUN IS DOING, SAID IN THE READER'S LANGUAGE.
 *
 * Every builder's `BUILD_PHASES` and every `progress.step(...)` carry a sentence written
 * where the work happens, and it travels with the event — so the phase bar's segments, the
 * line above them and every row of the run timeline were the API's own words. That is the
 * panel's main content for the hours a build takes, which is why it is the last family to
 * move here.
 *
 * The two tables have different SHAPES, and that is not an oversight. A step id is global:
 * `step.started` carries an `id` and nothing else, and `lib/explain.ts` already keys its
 * explanations on it alone. A phase key is only unique inside its own plan — the server
 * publishes the plans per artifact and per job kind, and `convert` names three different
 * phases across the three builders while `extract` names two genuinely different ones. So
 * the phase table is keyed by the plan first, which is the key the plan arrived under.
 *
 * As in `jobName`, the server's own label survives as the fallback: a phase or a step this
 * bundle has never heard of still gets a name, and so do the three whose sentence the
 * server builds around a filename or a stage.
 */

const PHASE_KEYS: Record<string, Record<string, Key>> = {
  knowledge_graph: {
    convert: "phase.knowledge_graph.convert.label",
    extract: "phase.knowledge_graph.extract.label",
    clean: "phase.knowledge_graph.clean.label",
    domains: "phase.knowledge_graph.domains.label",
    link: "phase.knowledge_graph.link.label",
    curate: "phase.knowledge_graph.curate.label",
    context: "phase.knowledge_graph.context.label",
  },
  exemplars_profile: {
    convert: "phase.exemplars_profile.convert.label",
    scan: "phase.exemplars_profile.scan.label",
    consolidate: "phase.exemplars_profile.consolidate.label",
    context: "phase.exemplars_profile.context.label",
  },
  exemplars_bank: {
    convert: "phase.exemplars_bank.convert.label",
    extract: "phase.exemplars_bank.extract.label",
  },
  review_taggability: { taggable: "phase.review_taggability.taggable.label" },
  transcribe: { transcribe: "phase.transcribe.transcribe.label" },
};

const STEP_KEYS: Record<string, Key> = {
  context: "step.context.label",
  load_instance: "step.load_instance.label",
  descriptions: "step.descriptions.label",
  index_concepts: "step.index_concepts.label",
  embed_bank: "step.embed_bank.label",
  embed_queries: "step.embed_queries.label",
  tagging: "step.tagging.label",
  guardrail: "step.guardrail.label",
  admissibility: "step.admissibility.label",
  generate: "step.generate.label",
  check: "step.check.label",
  build_exemplars_profile: "step.build_exemplars_profile.label",
  build_knowledge_graph: "step.build_knowledge_graph.label",
  build_exemplars_bank: "step.build_exemplars_bank.label",
  kg_convert: "step.kg_convert.label",
  kg_extract: "step.kg_extract.label",
  kg_merge: "step.kg_merge.label",
  kg_drop: "step.kg_drop.label",
  kg_domains: "step.kg_domains.label",
  kg_link: "step.kg_link.label",
  kg_curate: "step.kg_curate.label",
  convert: "step.convert.label",
  scan: "step.scan.label",
  consolidate: "step.consolidate.label",
  extract: "step.extract.label",
  transcribe_documents: "step.transcribe_documents.label",
  transcribe_seam: "step.transcribe_seam.label",
  taggability: "step.taggability.label",
  "eval.arms": "step.eval.arms.label",
  "eval.guardrail": "step.eval.guardrail.label",
  "eval.admissibility": "step.eval.admissibility.label",
  "eval.tagging": "step.eval.tagging.label",
  eval_rag_index_corpus: "step.eval_rag_index_corpus.label",
  eval_rag_index_exemplars: "step.eval_rag_index_exemplars.label",
};

/**
 * Which plan a run's phases belong to: a build is filed under its artifact and every other
 * job under its kind, exactly as `GET /api/pipeline/phases` publishes the two sets.
 */
export function phasePlan(
  job: { artifact?: ArtifactName | null; kind: string } | null | undefined,
): string | null {
  return job ? (job.artifact ?? job.kind) : null;
}

export function phaseName(
  plan: string | null | undefined,
  key: string | null | undefined,
  t: (key: Key) => string,
  fallback?: string | null,
): string {
  const entry = plan && key ? PHASE_KEYS[plan]?.[key] : undefined;
  return entry ? t(entry) : (fallback ?? key ?? "");
}

export function stepName(
  id: string | null | undefined,
  t: (key: Key) => string,
  fallback?: string | null,
): string {
  const entry = id ? STEP_KEYS[id] : undefined;
  return entry ? t(entry) : (fallback ?? id ?? "");
}

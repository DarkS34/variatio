import type { VgEvent } from "./types";
import type { Key, Translate } from "@/lib/i18n";
import { jobName, stepName } from "@/lib/names";

/**
 * What the pipeline is doing, in words.
 *
 * The core emits step ids and raw log lines; both are written for whoever wrote the
 * code. This is the other half: for every step and every event that reaches the UI,
 * one sentence saying what is happening and why it takes as long as it does. It lives
 * here and not in the components so the drawer, the timeline and the log view all
 * describe the same run the same way.
 */

export interface JobExplain {
  what: Key;
  produces: Key;
  cost: Key;
}

export const JOB_EXPLAIN: Record<string, JobExplain> = Object.fromEntries(
  [
    "transcribe",
    "build_profile",
    "build_kg",
    "build_bank",
    "describe_concepts",
    "index",
    "tag",
    "generate",
    "evaluate",
  ].map((kind) => [
    kind,
    {
      what: `job.${kind}.what` as Key,
      produces: `job.${kind}.produces` as Key,
      cost: `job.${kind}.cost` as Key,
    },
  ]),
);

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
  "transcribe_seam",
  "extract",
  "extract_batches",
  "scan",
  "consolidate",
  "eval.arms",
  "eval.guardrail",
  "eval.admissibility",
  "eval_rag_index",
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

export type ActivityTone = "info" | "good" | "warn" | "bad";

export interface ActivityLine {
  seq: number;
  ts: number;
  event: VgEvent;
}

/**
 * The one-line version of an event, in whatever language the reader has.
 *
 * It takes a translator rather than a hook because it is pure: `ActivityFeed` folds a whole
 * event stream through it on every render, and a function that reached for React here would
 * stop being testable and stop being callable from the store.
 */
export function describeEvent(
  event: VgEvent,
  tr: Translate,
): { text: string; tone: ActivityTone } | null {
  // The job's own name, said in the reader's language: the label the event carries is
  // the API's. `describeEvent` takes a translator rather than a hook precisely so this
  // stays callable from the store and from a test.
  const jobLabel = event.job
    ? jobName(event.job.kind, tr.t, event.job.label)
    : tr.t("activity.job.name");
  switch (event.kind) {
    case "job.queued":
      return { text: tr.t("activity.job.queued", { label: jobLabel }), tone: "info" };
    case "job.started":
      return { text: tr.t("activity.job.started", { label: jobLabel }), tone: "info" };
    case "job.finished":
      return { text: tr.t("activity.job.finished", { label: jobLabel }), tone: "good" };
    case "job.failed":
      return {
        text: tr.t("activity.job.failed", {
          error: event.job?.error ?? tr.t("activity.job.unknownError"),
        }),
        tone: "bad",
      };
    case "job.cancelling":
      return { text: tr.t("activity.job.cancelling"), tone: "warn" };
    case "job.cancelled":
      return { text: tr.t("activity.job.cancelled"), tone: "warn" };

    case "step.started":
      // The step's own name, for the same reason as the job's above: the label the event
      // carries is the API's. Through `tr.t` and not a hook, so this stays pure.
      return {
        text: event.label
          ? stepName(event.id, tr.t, event.label)
          : tr.t("activity.step.generic", { id: event.id ?? "" }),
        tone: "info",
      };
    case "step.finished":
      if (event.status === "failed") {
        return {
          text: tr.t("activity.step.failed", { id: event.id ?? "", error: event.error ?? "" }),
          tone: "bad",
        };
      }
      if (event.status === "cancelled") {
        return { text: tr.t("activity.step.cancelled", { id: event.id ?? "" }), tone: "warn" };
      }
      return null;

    case "retrieval": {
      const candidates = event.candidates ?? [];
      if (candidates.length === 0) {
        return { text: tr.t("activity.retrieval.none"), tone: "warn" };
      }
      const best = candidates[0];
      return {
        text: tr.plural("activity.retrieval.some", candidates.length, {
          best: best[0],
          score: best[1].toFixed(3),
        }),
        tone: "info",
      };
    }
    case "guardrail":
      if (!event.checked) return { text: tr.t("activity.guardrail.unchecked"), tone: "warn" };
      if (event.ok) return { text: tr.t("activity.guardrail.ok"), tone: "good" };
      return {
        text: tr.t("activity.guardrail.blocked", { criteria: event.criteria ?? "" }),
        tone: "bad",
      };
    case "admissibility":
      if (!event.checked) return { text: tr.t("activity.admissibility.unchecked"), tone: "warn" };
      if (event.ok) {
        return {
          text: tr.t("activity.admissibility.ok", { slots: (event.slots ?? []).join(", ") }),
          tone: "good",
        };
      }
      return {
        text: tr.t("activity.admissibility.blocked", {
          term: event.term ?? "",
          owner: event.owner ?? "",
        }),
        tone: "bad",
      };
    case "few_shot": {
      const used = (event.items ?? event.ids ?? []).length;
      if (used === 0) return { text: tr.t("activity.fewShot.none"), tone: "warn" };
      return { text: tr.plural("activity.fewShot.used", used), tone: "info" };
    }
    case "prompt":
      return {
        text: tr.t("activity.prompt.sent", {
          chars: (event.text ?? "").length.toLocaleString(),
        }),
        tone: "info",
      };
    case "repair":
      return {
        text: tr.t("activity.repair", {
          where: event.where ?? "",
          attempt: event.attempt ?? 0,
          max: event.max_attempts ?? 0,
        }),
        tone: "warn",
      };
    case "item.retried":
      return {
        text: tr.t("activity.item.retried", {
          index: event.index ?? 0,
          attempt: event.attempt ?? 0,
          reasons: (event.reasons ?? []).join("; "),
        }),
        tone: "warn",
      };
    case "item.produced": {
      const flags = event.checks?.flags?.length ?? 0;
      return flags
        ? {
            text: tr.plural("activity.item.flagged", flags, { index: event.index ?? 0 }),
            tone: "warn",
          }
        : { text: tr.t("activity.item.produced", { index: event.index ?? 0 }), tone: "good" };
    }
    case "item.saved":
      return { text: tr.t("activity.item.saved", { index: event.index ?? 0 }), tone: "good" };
    case "item.rejected":
      return { text: tr.t("activity.item.rejected", { index: event.index ?? 0 }), tone: "warn" };
    case "item.tagged": {
      const id = event.id ?? tr.t("activity.item.name");
      const concepts = event.concepts ?? [];
      return concepts.length
        ? { text: tr.t("activity.item.tagged", { id, concepts: concepts.join(", ") }), tone: "good" }
        : { text: tr.t("activity.item.taggedNone", { id }), tone: "warn" };
    }
    case "artifact.progress":
      return {
        text: tr.plural("activity.artifact.progress", event.count ?? 0, { name: event.name ?? "" }),
        tone: "info",
      };

    default:
      return null;
  }
}


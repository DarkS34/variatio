import type { StageState } from "@/lib/types";
import type { Key } from "@/lib/i18n";

/**
 * THE PATH, AS DATA. One home, because two places read it and they must not disagree.
 *
 * The bar draws every step and its state; the landing route needs only the one that is
 * next. Both used to be able to answer differently — which is exactly how the app ended up
 * with two contradictory numberings of one chain — so the answer is computed here and
 * nowhere else.
 *
 * The order is `server/review.ARTIFACTS` with the raw material in front, and it must stay
 * so: the profile leads because finishing the syllabus needs an APPROVED profile
 * (`routers/jobs.NEEDS_APPROVED` gates its taggability review on it), so starting at the
 * syllabus is starting at a step you cannot finish.
 */
export const STEPS = [
  { path: "/raw", labelKey: "nav.step.raw", artifact: null },
  { path: "/prepare/profile", labelKey: "nav.step.profile", artifact: "exemplars_profile" },
  { path: "/prepare/graph", labelKey: "nav.step.graph", artifact: "knowledge_graph" },
  { path: "/prepare/bank", labelKey: "nav.step.bank", artifact: "exemplars_bank" },
] as const satisfies readonly { path: string; labelKey: Key; artifact: string | null }[];

export type StepState = "done" | "now" | "later";

/**
 * Where each step stands, and which single one is the next move.
 *
 * The current step is the FIRST one not done and never «every one not done»: what makes a
 * path obvious is one next move, not a list of pending chores. Step 1 has no artifact and
 * no approval, so «done» there means both origins hold documents — the condition the three
 * builds behind it actually need. Being untranscribed is deliberately NOT part of it:
 * transcribing is an accelerator and never a gate, and a step marked pending by something
 * that does not stop you would be a false promise in the one bar everybody reads.
 */
export function stepStates(stages: StageState[], rawStocked: boolean): StepState[] {
  const done = STEPS.map((step) =>
    step.artifact
      ? stages.find((s) => s.artifact === step.artifact)?.status === "approved"
      : rawStocked,
  );
  const now = done.indexOf(false);
  return done.map((isDone, index) => (isDone ? "done" : index === now ? "now" : "later"));
}

/**
 * Where «/» lands: the step that is next, or generation once the whole path is walked.
 *
 * A landing route that resolves rather than a page of its own, because there is nothing
 * left to say from outside a chain that IS the navigation — and because the one question
 * somebody opening this has is «what do I do now», which this answers by doing it.
 */
export function currentStepPath(stages: StageState[], rawStocked: boolean): string {
  const states = stepStates(stages, rawStocked);
  const now = states.indexOf("now");
  return now === -1 ? "/generate" : STEPS[now].path;
}

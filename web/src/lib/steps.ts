import type { Job, StageState } from "@/lib/types";
import type { Key } from "@/lib/i18n";
import { isQueued } from "@/lib/queue";

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

/**
 * What the construction is FOR, after the rule: the one door that opens once the whole
 * construction is closed.
 *
 * A number encodes dependency, so it goes exactly where there is one: inside the
 * construction, `1 … 4`, where each step needs the one before it closed. The door carries
 * an ICON where a step carries its number: an icon says "a door", a number "a stop". It
 * stands under no caption of its own — with one door there is no phase to name.
 *
 * `USES` is one home for the bar and the guide, so the guide cannot draw a door the
 * navigation does not have.
 */
export const USES = [
  { key: "generate", path: "/generate", labelKey: "nav.create" },
] as const satisfies readonly { key: string; path: string; labelKey: Key }[];

/** How a construction step is numbered on screen, from its index in `STEPS`. */
export function stepNumber(index: number): string {
  return `${index + 1}`;
}

/** The same, addressed by the artifact a step builds — the stage screens' way in. */
export function stepNumberOf(artifact: string): string | null {
  const index = STEPS.findIndex((step) => step.artifact === artifact);
  return index === -1 ? null : stepNumber(index);
}

/**
 * Where the step AFTER this artifact's leads, and what to call it.
 *
 * `null` is the raw material — the one step with no artifact — so its screen can offer the
 * same "Continuar" every stage ends with, read from the same list.
 */
export function nextStepOf(
  artifact: string | null,
): { path: string; number: string | null; labelKey: Key } {
  const index = STEPS.findIndex((step) => step.artifact === artifact);
  const next = index === -1 ? -1 : index + 1;
  return next > 0 && next < STEPS.length
    ? { path: STEPS[next].path, number: stepNumber(next), labelKey: STEPS[next].labelKey }
    : { path: "/generate", number: null, labelKey: "nav.create" };
}

export type StepState = "done" | "now" | "later";

/**
 * Where each step stands, and which single one is the next move.
 *
 * The current step is the FIRST one not done and never "every one not done": what makes a
 * path obvious is one next move, not a list of pending chores. Step 1 has no artifact and
 * no approval, so "done" there means both origins hold documents — the condition the three
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
 * Where "/" lands: the step that is next, or generation once the whole path is walked.
 *
 * A landing route that resolves rather than a page of its own, because there is nothing
 * left to say from outside a chain that IS the navigation — and because the one question
 * somebody opening this has is "what do I do now", which this answers by doing it.
 */
export function currentStepPath(stages: StageState[], rawStocked: boolean): string {
  const states = stepStates(stages, rawStocked);
  const now = states.indexOf("now");
  return now === -1 ? "/generate" : STEPS[now].path;
}

/**
 * Which steps have work RUNNING on them right now — a build of a stage, or the reading of
 * the documents for step 1 — so the bar can spin a wheel where the number was.
 *
 * Running and not queued: a queued job is not a running one and no screen may draw
 * activity over it (the register's own rule), and a wheel is a claim that something is
 * happening. `building` is the pipeline's word and covers both, so the stream's own jobs
 * are what tell the two apart; with no job known for the artifact the pipeline is
 * believed, which is the state a reload lands in.
 */
export function stepBusy(stages: StageState[], jobs: Job[]): boolean[] {
  return STEPS.map((step) => {
    if (step.artifact === null) {
      return jobs.some((job) => job.kind === "transcribe" && job.status === "running");
    }
    const building = stages.some(
      (stage) => stage.artifact === step.artifact && stage.status === "building",
    );
    const queued = jobs.some(
      (job) => job.artifact === step.artifact && job.status !== "running" && isQueued(job),
    );
    return building && !queued;
  });
}

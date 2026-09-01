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

/**
 * THREE PHASES, AND THE FOUR STEPS ARE ALL INSIDE THE FIRST ONE (explicit user request).
 *
 * «Hay que dejar claro que esto es el paso uno necesario para preparar esta asignatura en
 * el sistema. Y una vez que esto lo tengas claro, ya puedes generar ejercicios. […] El
 * paso 1 tiene 1-1, 1-2, 1-3 y 1-4.» The app used to present four steps at one level with
 * generating outside the numbering altogether, as though asking for an exercise were not
 * part of the path — when it is the only reason the other four exist.
 *
 * The numbers carry it on their own: `1.1 … 1.4` says these four are one thing, and `2` on
 * «Crear ejercicios» says what that thing was for. No extra captions in the bar; the
 * tutorial does the naming.
 *
 * COMPARING IS THE THIRD (2026-09-02, explicit user request), which reverses the note that
 * used to sit on `UsePill`'s `n` — «its number on the path, for the one that IS a phase;
 * «Comparar» is not». What made it not a phase was that it is optional and belongs to the
 * study rather than to preparing a subject; what makes it one is that the tutorial now
 * names it «Fase 3», and the rule the figures are held to is that a picture may not
 * promise an order the navigation does not have. Either the deck stops calling it a phase
 * or the bar starts counting it, and counting it is the truer of the two: the whole
 * product is one numbered path, 1.1 → 2 → 3. Its `--study` tint is untouched — the number
 * says where it sits, the colour still says it is a different kind of thing.
 */
export const PREPARE_PHASE = 1;
export const GENERATE_PHASE = 2;
export const COMPARE_PHASE = 3;

/** How a preparation step is numbered on screen, from its index in `STEPS`. */
export function stepNumber(index: number): string {
  return `${PREPARE_PHASE}.${index + 1}`;
}

/** The same, addressed by the artifact a step builds — the stage screens' way in. */
export function stepNumberOf(artifact: string): string | null {
  const index = STEPS.findIndex((step) => step.artifact === artifact);
  return index === -1 ? null : stepNumber(index);
}

/** Where the step AFTER this artifact's leads, and what to call it. */
export function nextStepOf(artifact: string): { path: string; number: string | null } {
  const index = STEPS.findIndex((step) => step.artifact === artifact);
  const next = index === -1 ? -1 : index + 1;
  return next > 0 && next < STEPS.length
    ? { path: STEPS[next].path, number: stepNumber(next) }
    : { path: "/generate", number: null };
}

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

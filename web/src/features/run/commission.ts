import type { GenerateParams } from "@/lib/types";

import { EFFORT_ORDER, type EffortLevel } from "./effort";

/**
 * The commission as the form holds it, and its two conversions to what the API takes.
 *
 * Pure, and in a module of its own rather than beside the component, because three
 * different screens convert a form into a request — the generate screen, the evaluator's
 * own commission and the panel's stock — and the one field they disagree about is `n`.
 * A conversion that lives inside a component cannot be tested without a DOM, and this one
 * shipped wrong: see `evaluation/commission.ts`.
 */

export interface FormState {
  n: number;
  concepts: string[];
  /** null means "not chosen yet"; it resolves on its own only when the profile declares a
   *  single modality, because then there is nothing to choose. */
  itemType: string | null;
  /**
   * The workspace's own stored list, which no screen sets any more: it is only ever read
   * back off an older run whose request carried no `curriculum` at all.
   */
  usePresetCurriculum: boolean;
  /**
   * What the class has covered, as the person ticked it. IN FORCE EXACTLY WHEN IT HOLDS
   * SOMETHING (2026-09-05, explicit user request: «no lo detecte con un switch sino que
   * sea si hay conceptos dentro o no»). There used to be a `useCurriculum` switch beside
   * it, so the form could be «restricted» with nothing ticked and a ticked list could be
   * switched off; both states sent `[]`, which is what an empty list sends now.
   */
  curriculum: string[];
  decisions: Record<string, unknown>;
  instructions: string;
  /** Only the "generate" variant reads it: an evaluation draws its own, at random. */
  think: boolean;
  /** Only counts with `think` on; what the engine receives as reasoning effort. */
  effort: EffortLevel;
  /**
   * Which offered model writes it.
   *
   * Null is «el de por defecto», the first of `generation.models`. The form does not know
   * that list well enough to resolve it — the server does, and what a run RECORDS is the
   * model that actually wrote it, never the one a browser guessed. Only the "generate"
   * variant sets it: a comparison's two local proposals are written by the installation's
   * own `evaluation.local_model`, and `evaluation/commission.ts` strips the field on the way.
   *
   * IT WENT AWAY ON 2026-09-01 AND CAME BACK THE SAME DAY, both by explicit user request.
   * What the removal was for survives in the offer: an installation that wants to decide
   * offers one model, and then nothing is drawn.
   */
  model: string | null;
}

export const EMPTY_FORM: FormState = {
  n: 1,
  concepts: [],
  itemType: null,
  // FALSE, since 2026-09-01: the workspace's stored list can no longer be edited, so
  // nothing may resolve to it by default. It stays in the shape because `fromParams` reads
  // it — a run recorded before the change carried no `curriculum` field at all and did run
  // against the workspace's own, and describing that faithfully is what lets it be re-run
  // exactly as it ran.
  usePresetCurriculum: false,
  curriculum: [],
  decisions: {},
  instructions: "",
  think: true,
  effort: "low",
  model: null,
};

export function toParams(state: FormState): GenerateParams {
  const params: GenerateParams = {
    n: state.n,
    concepts: state.concepts,
    // Off travels as `false`; on travels as the level itself, which the engine boundary
    // forwards untouched (`_think_option` / `reasoning_effort`).
    think: state.think ? state.effort : false,
  };
  if (state.itemType) params.item_type = state.itemType;
  // Absent means the default, exactly as it does for the curriculum: what a run RECORDS is
  // the model that wrote it, resolved server-side, and never the one the form guessed.
  if (state.model) params.model = state.model;
  const fixed: Record<string, unknown> = {};
  for (const [field, value] of Object.entries(state.decisions)) {
    if (value === undefined || value === null) continue;
    if (typeof value === "string" && !value.trim()) continue;
    fixed[field] = value;
  }
  if (Object.keys(fixed).length > 0) params.fixed = fixed;
  // Absent and `[]` are NOT the same request: `server/curriculum.resolve` returns the
  // parameter unchanged whenever it is given — the empty list included, which is how one
  // says "no restriction" — and only falls back to the workspace's stored curriculum when
  // nothing arrives at all. So the preset case sends no field, not an empty one, and a
  // list with nothing ticked sends the empty one, which is «sin restricción».
  if (!state.usePresetCurriculum) params.curriculum = state.curriculum;
  if (state.instructions.trim()) params.instructions = state.instructions.trim();
  return params;
}

// The exact inverse of `toParams`, and it has to stay its mirror: it is what lets a screen
// describe the commission that RAN instead of the one on screen. A job carries its own
// parameters; the form state does not survive a reload or a visit to another screen, so the
// two drift apart and the collapsed bar ends up quoting the empty form's defaults over the
// results of a run that asked for something else.
export function fromParams(params: Record<string, unknown>): FormState {
  const curriculum = Array.isArray(params.curriculum)
    ? (params.curriculum as string[])
    : undefined;
  return {
    ...EMPTY_FORM,
    // `int(params.get("n") or 1)`, as the handler reads it.
    n: Number(params.n) || 1,
    concepts: Array.isArray(params.concepts) ? [...(params.concepts as string[])] : [],
    itemType: (params.item_type as string) || null,
    // Absent is the workspace's own and `[]` is «sin restricción», exactly as the server
    // resolves them.
    usePresetCurriculum: curriculum === undefined,
    curriculum: curriculum ? [...curriculum] : [],
    decisions: { ...((params.fixed as Record<string, unknown>) ?? {}) },
    instructions: (params.instructions as string) ?? "",
    think: params.think !== false,
    model: typeof params.model === "string" && params.model ? params.model : null,
    effort:
      typeof params.think === "string" && EFFORT_ORDER.includes(params.think as EffortLevel)
        ? (params.think as EffortLevel)
        : "low",
  };
}

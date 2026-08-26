import type { GenerateParams } from "@/lib/types";

import { EFFORT_ORDER, type EffortLevel } from "./effort";

/**
 * The commission as the form holds it, and its two conversions to what the API takes.
 *
 * Pure, and in a module of its own rather than beside the component, because three
 * different screens convert a form into a request — the generate screen, the evaluator's
 * own commission and the panel's stock — and the one field they disagree about is `n`.
 * A conversion that lives inside a component cannot be tested without a DOM, and this one
 * shipped wrong: see `study/commission.ts`.
 */

export interface FormState {
  n: number;
  concepts: string[];
  /** null means "not chosen yet"; it resolves on its own only when the profile declares a
   *  single modality, because then there is nothing to choose. */
  itemType: string | null;
  /** Off = no restriction. */
  useCurriculum: boolean;
  /** Only counts with `useCurriculum`. On = the workspace's own. */
  usePresetCurriculum: boolean;
  /** The ad-hoc one; only counts with `useCurriculum` on and `usePresetCurriculum` off. */
  curriculum: string[];
  decisions: Record<string, unknown>;
  instructions: string;
  /** Only the "generate" variant reads it: an evaluation draws its own, at random. */
  think: boolean;
  /** Only counts with `think` on; what the engine receives as reasoning effort. */
  effort: EffortLevel;
}

export const EMPTY_FORM: FormState = {
  n: 2,
  concepts: [],
  itemType: null,
  useCurriculum: false,
  usePresetCurriculum: true,
  curriculum: [],
  decisions: {},
  instructions: "",
  think: true,
  effort: "low",
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
  // nothing arrives at all. So the preset case sends no field, not an empty one.
  if (!state.useCurriculum) params.curriculum = [];
  else if (!state.usePresetCurriculum) params.curriculum = state.curriculum;
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
    useCurriculum: curriculum === undefined || curriculum.length > 0,
    usePresetCurriculum: curriculum === undefined,
    curriculum: curriculum ? [...curriculum] : [],
    decisions: { ...((params.fixed as Record<string, unknown>) ?? {}) },
    instructions: (params.instructions as string) ?? "",
    think: params.think !== false,
    effort:
      typeof params.think === "string" && EFFORT_ORDER.includes(params.think as EffortLevel)
        ? (params.think as EffortLevel)
        : "low",
  };
}

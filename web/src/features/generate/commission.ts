import type { GenerateParams } from "@/lib/types";

import { EFFORT_ORDER, type EffortLevel } from "./effort";

/**
 * The commission as the form holds it, and its two conversions to what the API takes.
 *
 * Pure, and in a module of its own rather than beside the component: a conversion that
 * lives inside a component cannot be tested without a DOM.
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
   * What the class has covered, as the person ticked it, and in force exactly when it holds
   * something. A switch beside it allows two states that say nothing — "restricted" with
   * nothing ticked, and a ticked list turned off — and both send `[]` anyway.
   */
  curriculum: string[];
  decisions: Record<string, unknown>;
  instructions: string;
  think: boolean;
  /** Only counts with `think` on; what the engine receives as reasoning effort. */
  effort: EffortLevel;
  /**
   * Which offered model writes it.
   *
   * Null is "the default one", the first of `generation.models`. The server resolves it,
   * never the form: what a run RECORDS is the model that actually wrote it and not one a
   * browser guessed.
   *
   * An installation that would rather decide offers ONE model, and then nothing is drawn.
   */
  model: string | null;
}

export const EMPTY_FORM: FormState = {
  n: 1,
  concepts: [],
  itemType: null,
  // Always false: the workspace's stored list can no longer be edited, so nothing may
  // resolve to it by default. It stays in the shape because `fromParams` reads it — a run
  // recorded with no `curriculum` field at all DID run against the workspace's own, and
  // describing that faithfully is what lets it be re-run exactly as it ran.
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
  // list with nothing ticked sends the empty one, which is "sin restricción".
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
    // Absent is the workspace's own and `[]` is "sin restricción", exactly as the server
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

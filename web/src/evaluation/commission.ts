import { toParams, type FormState } from "@/features/generate/commission";

import type { AdminGenerateParams } from "./api";
import type { EvaluationParams } from "./types";

/**
 * The two ways a comparison is commissioned, and the field that must never travel.
 *
 * `n` goes because one item per arm is what makes the session the statistical unit, and
 * `think` goes because the session draws it: sending the form's value would hand the
 * evaluator control of the very condition being measured. The server ignores both fields
 * too — this is the second lock, not the only one. `model` goes for the same reason: the
 * writer of the two local proposals is the installation's (`evaluation.local_model`), so
 * a value the form happened to hold must not reach the request.
 */
export function toEvaluationParams(form: FormState, scenario = ""): EvaluationParams {
  const { n: _n, think: _think, model: _model, ...rest } = toParams(form);
  return scenario.trim() ? { ...rest, scenario: scenario.trim() } : rest;
}

/**
 * The panel's batch: the same commission, plus WHERE it runs and HOW MANY comparisons to
 * prepare — which is a different question from the form's own counter and has to be asked
 * separately.
 *
 * It shipped answering it with `form.n`, and that is the whole bug: `variant="evaluation"`
 * hides the item counter, a hidden control keeps its default, and the default is 2. One
 * commission became two sessions, so the same exercise appeared twice in the list to hand
 * out and twice in "Mis sesiones" — differing only in the reasoning condition each session
 * had drawn for itself, which is exactly what made it look like a duplicate rather than
 * like a second comparison.
 */
export function toStockParams(
  form: FormState,
  workspace: string,
  comparisons: number,
): AdminGenerateParams {
  return { ...toEvaluationParams(form), workspace, n: comparisons };
}

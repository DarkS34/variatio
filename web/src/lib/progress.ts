/**
 * Whether the job now running REPLACES the artifact or only patches it.
 *
 * `JOB_ARTIFACT` puts both kinds under the same artifact, which is what lets the chain say
 * «este banco está ocupado» whoever is writing it. The two are not the same thing on screen,
 * though: a rebuild has a phase plan and throws the previous artifact away, while `tag`
 * rewrites the items in place, keeps every decision it has already made, and declares no
 * plan at all — drawing the builder's segments for it leaves a bar frozen at zero.
 */
export function isRebuild(kind: string | undefined | null): boolean {
  return Boolean(kind?.startsWith("build_"));
}

/**
 * How far a job with no phase plan is, from the step it is on.
 *
 * A plan is what turns several phases of wildly different cost into one honest number, and
 * only the builders have one. A job that is a single loop does not need it: its step already
 * counts what it is counting. `null` means "not measurable yet", which is the bar's
 * indeterminate state and not a zero.
 */
export function stepPercent(
  step: { current?: number; total?: number | null } | undefined | null,
): number | null {
  if (!step?.total || step.total <= 0) return null;
  return Math.min(100, Math.round(((step.current ?? 0) / step.total) * 100));
}

/**
 * How full a meter is, or `null` when the total is not known yet.
 *
 * «No sé cuánto hay» and «hay cero» are different facts and only the first one may sweep:
 * a bar that sweeps says work is under way. The two were one condition (`!max`), so an
 * empty exemplars bank drew `0/0` as the indeterminate sweep and the bank screen animated
 * for ever over a workspace where nothing at all was happening — read, correctly, as «se
 * ha quedado cargando». Deleting the last item of a bank is exactly how one gets there.
 *
 * A known total of zero is complete, not unmeasurable: the meter reads 0 % and stops.
 * Unknown is `null` or `undefined`, which is what every caller that means it already passes.
 */
export function barFill(value: number, max: number | null | undefined): number | null {
  if (max === null || max === undefined || Number.isNaN(max)) return null;
  if (max <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((value / max) * 100)));
}

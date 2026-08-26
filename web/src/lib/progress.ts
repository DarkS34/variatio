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

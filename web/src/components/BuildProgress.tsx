import { Hourglass } from "lucide-react";

import { RunTimeline } from "@/components/RunTimeline";
import { Card, CardContent } from "@/components/ui/card";
import { PhaseBar, Progress, Spinner } from "@/components/ui/misc";
import { duration } from "@/lib/format";
import { isRebuild, stepPercent } from "@/lib/progress";
import type { ArtifactName, BuildPhase } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { RunView } from "@/state/runStore";
import { useArtifactRun, useBuildPhases, useElapsed } from "@/state/queries";
import { useT } from "@/lib/i18n";
import { jobName, phaseName, phasePlan, stepName } from "@/lib/names";
import { CancelButton } from "./CancelButton";

/**
 * What a build is doing right now, on the screen of the thing being built.
 *
 * The drawer already shows every step of every run; this is the other question — "how
 * much is left of *this* artifact?" — answered where it is asked: the share of the plan
 * already done, drawn as the builder's own phases. The percentage comes from that
 * weighted plan and not from the running step, because steps nest and none of them knows
 * the size of the whole.
 *
 * What is deliberately NOT here is a countdown. It was, and it was a lie waiting to
 * happen: the seconds behind it were measured against one set of models, and this
 * instance's models are a config line away from being different ones.
 */
export function BuildProgress({
  artifact,
  className,
}: {
  artifact: ArtifactName;
  className?: string;
}) {
  const { t } = useT();
  const run = useArtifactRun(artifact);
  // The plan belongs to the BUILDER, not to the artifact: a `tag` job is filed under
  // the bank too, declares no phases and emits no `build.progress`, so handing it the
  // extractor's segments drew a five-segment bar stuck at zero for the whole run.
  const phases = useBuildPhases(isRebuild(run?.job?.kind) ? artifact : undefined);
  return (
    <JobProgress
      run={run}
      phases={phases}
      className={className}
      waiting={t("progress.building")}
    />
  );
}

/**
 * The same card, for any job with a phase plan.
 *
 * `BuildProgress` wraps it with the plan of the artifact being built; the jobs that write
 * none — the taggability review, which patches a list in place — use it directly with their
 * own plan. They were the same bar, and separating them would have given two different ways
 * of drawing the same thing.
 */
export function JobProgress({
  run,
  phases,
  className,
  waiting,
}: {
  run: RunView | null;
  phases: BuildPhase[];
  className?: string;
  /** What the card says before the first step arrives. Defaults to the generic sentence. */
  waiting?: string;
}) {
  const { t } = useT();
  const waitingText = waiting ?? t("progress.running");
  const status = run?.job?.status;
  const active = status === "running" || status === "queued";
  const elapsed = useElapsed(run?.job?.started_at ?? null, active);

  if (!run || !run.job) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center gap-2 py-4 text-body text-muted-foreground">
          <Spinner />
          {waitingText}
        </CardContent>
      </Card>
    );
  }

  const overall = run.overall;
  const step = run.steps.filter((s) => s.status === "running").at(-1);
  const position = phases.findIndex((phase) => phase.key === overall?.key);
  // With no plan the running step is the only thing that knows how far this is, and it
  // does know: it counts what it is iterating over. `null` is «todavía no medible».
  //
  // The two measures never mix. A build that has a plan but has not emitted its first
  // `build.progress` yet keeps saying «—»: taking the step's number there would print a
  // percentage beside a segmented bar still drawn at zero, and the two would disagree.
  const percent = overall?.percent ?? (phases.length === 0 ? stepPercent(step) : null);
  // The running phase, or the running step when there is no plan. Both arrive with the
  // API's own sentence and are named here; a phase key only means something inside its
  // plan, which is the artifact a build writes or, for a job that writes none, its kind.
  const running =
    (overall?.label
      ? phaseName(phasePlan(run.job), overall.key, t, overall.label)
      : null) ??
    (step ? stepName(step.id, t, step.label) : null) ??
    t("progress.preparing");

  return (
    <Card className={className}>
      <CardContent className="space-y-4 py-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="relative flex size-2 shrink-0">
            {active ? (
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60" />
            ) : null}
            <span
              className={cn(
                "relative inline-flex size-2 rounded-full",
                active ? "bg-primary" : "bg-muted-foreground",
              )}
            />
          </span>
          {/* No (i): this card appears under the artifact's header, which already explains what it
              is, and the job name plus the running phase say what is happening. The job's explanation
              is still given once, in the run drawer. */}
          <p className="text-body font-medium">{jobName(run.job.kind, t, run.job.label)}</p>
          <span className="flex items-center gap-1 text-small nums text-muted-foreground">
            <Hourglass className="size-3" />
            {duration(elapsed)}
          </span>
          {active ? <CancelButton run={run} className="ml-auto" /> : null}
        </div>

        {/* With no phase plan yet (start-up, or model loading) the bar is indeterminate on
            purpose: better that than a 0 % that looks stuck. */}
        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <p className="min-w-0 truncate text-body">
              {position >= 0 ? (
                <span className="mr-1.5 nums text-muted-foreground">
                  {position + 1}/{phases.length}
                </span>
              ) : null}
              {running}
            </p>
            <span className="shrink-0 text-body font-medium nums">
              {percent === null ? "—" : `${percent} %`}
            </span>
          </div>

          {phases.length > 0 ? (
            <PhaseBar
              phases={phases}
              percent={overall?.percent ?? 0}
              activeKey={overall?.key}
              live={active}
            />
          ) : (
            <Progress value={percent ?? 0} max={percent === null ? null : 100} />
          )}

          {overall?.detail ?? step?.detail ? (
            <p className="truncate text-small text-muted-foreground">
              {overall?.detail ?? step?.detail}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <h4 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
            {t("run.steps")}
          </h4>
          <RunTimeline steps={run.steps} />
          {run.job.error ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-small text-destructive">
              {run.job.error}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

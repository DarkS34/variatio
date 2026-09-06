import { ChevronRight, Hourglass } from "lucide-react";
import { useId, useState } from "react";

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
  compact = false,
}: {
  artifact: ArtifactName;
  className?: string;
  /**
   * Drop the step timeline and the stop button, for a caller that already has both.
   *
   * The panel is the one place where three drawings of one job used to coexist: this card
   * inside the stage's own card (with a `RunTimeline` and a "Cancelar"), `ActivityCard`
   * beside it (with a second "Cancelar"), and the run drawer behind the floating pill
   * (with the same timeline again). Two stop buttons for one job, thirty centimetres
   * apart and in different variants, is not redundancy that helps.
   *
   * Compact keeps what the stage's own card is FOR — which phase, how far, how long — and
   * lets the panel say the rest once, in the card whose subject is the run itself.
   */
  compact?: boolean;
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
      compact={compact}
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
/**
 * Whether the step timeline is unfolded, remembered per browser.
 *
 * Closed by default: the card's header already says which phase is running, how far and for
 * how long, and on a build of thirteen phases the list under it is most of the card.
 * `localStorage` and not state, so the choice survives moving between the four steps. Every
 * access is guarded — the accessor itself throws in some browsers' private modes.
 */
const STEPS_KEY = "vg.steps";

function readStepsOpen(): boolean {
  try {
    return localStorage.getItem(STEPS_KEY) === "open";
  } catch {
    return false;
  }
}

function writeStepsOpen(open: boolean) {
  try {
    if (open) localStorage.setItem(STEPS_KEY, "open");
    else localStorage.removeItem(STEPS_KEY);
  } catch {
    // Nothing to remember with: the card still folds and unfolds for this visit.
  }
}

export function JobProgress({
  run,
  phases,
  className,
  waiting,
  compact = false,
  cancel,
}: {
  run: RunView | null;
  phases: BuildPhase[];
  className?: string;
  /** What the card says before the first step arrives. Defaults to the generic sentence. */
  waiting?: string;
  /** See `BuildProgress`: no timeline and no stop button, for a caller that has both. */
  compact?: boolean;
  /**
   * What the stop button undoes, when that is not exactly this run.
   *
   * "Transcribir todo" starts one job per origin, and the card of either origin has to
   * stop BOTH — a stop that reached one left the other running and the person pressed the
   * button twice for one press of the launcher. `word` and `hint` are `CancelButton`'s
   * own: "Detener", and what stopping costs, for a job chewing through a slot.
   */
  cancel?: { runs?: (RunView | null)[]; word?: "cancel" | "stop"; hint?: string };
}) {
  const { t } = useT();
  const [stepsOpen, setStepsOpen] = useState(readStepsOpen);
  const stepsId = useId();
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
  // does know: it counts what it is iterating over. `null` is "todavía no medible".
  //
  // The two measures never mix. A build that has a plan but has not emitted its first
  // `build.progress` yet keeps saying "—": taking the step's number there would print a
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
          {active && !compact ? (
            <CancelButton
              run={cancel?.runs ?? run}
              word={cancel?.word}
              hint={cancel?.hint}
              className="ml-auto"
            />
          ) : null}
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

        {/* The timeline is the drawer's job when a caller says `compact`: on the panel it
            was drawn here, inside the stage card, and again behind the floating pill. The
            error is NOT part of that — a failure has to be readable where it happened. */}
        {compact ? (
          run.job.error ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-small text-destructive">
              {run.job.error}
            </p>
          ) : null
        ) : (
          <div className="space-y-2">
            {/* A button and not a heading: the list folds under it and starts folded. The
                count beside the word is what the shut state still says — how many steps
                there are to look at — and the error is never behind the fold. */}
            <button
              type="button"
              onClick={() =>
                setStepsOpen((was) => {
                  writeStepsOpen(!was);
                  return !was;
                })
              }
              aria-expanded={stepsOpen}
              aria-controls={stepsId}
              className="flex items-center gap-1.5 text-small font-medium uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
            >
              <ChevronRight
                aria-hidden
                className={cn(
                  "size-3.5 shrink-0 transition-transform duration-200 motion-reduce:transition-none",
                  stepsOpen && "rotate-90",
                )}
              />
              {t("run.steps")}
              <span className="nums font-normal normal-case tracking-normal">
                ({run.steps.length})
              </span>
            </button>
            {stepsOpen ? (
              <div id={stepsId}>
                <RunTimeline steps={run.steps} />
              </div>
            ) : null}
            {run.job.error ? (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-small text-destructive">
                {run.job.error}
              </p>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

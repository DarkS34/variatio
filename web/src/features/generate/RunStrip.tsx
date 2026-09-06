import { ChevronRight, Clock, Hourglass, RotateCcw } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Progress } from "@/components/ui/misc";
import { JOB_STATUS, duration } from "@/lib/format";
import { queuedLabel, type Wait } from "@/lib/queue";
import { cn } from "@/lib/utils";
import { useElapsed } from "@/state/queries";
import type { RunView } from "@/state/runStore";
import { useT, type Translate } from "@/lib/i18n";
import { jobName, phaseName, phasePlan, stepName } from "@/lib/names";
import { CancelButton } from "@/components/CancelButton";

/**
 * The run, as two lines above the thing it produces: what is running, how far it has got,
 * how long it has been and how to stop it. What a person is on this screen for is the
 * items.
 *
 * What a RETRY is doing is not behind the disclosure. A rejected exercise is generated
 * again, up to `CHECK_MAX_RETRIES` times, and each of those is a whole call — so the bar
 * sits still for minutes, and saying why is the difference between "se ha quedado colgado"
 * and "lo está rehaciendo porque menciona algo no impartido". Drawn in `--attention`, the
 * one thing on the strip that is not merely a measurement, and it goes when the item lands.
 *
 * What IS behind the disclosure is duplicated nowhere — the reasoning, the token stream,
 * the technical details and the few-shot exemplars — which is why it is a fold and not a
 * deletion. It opens by itself while the job runs, and it opens INSIDE this block, so a
 * disclosure grows the card it belongs to instead of producing a second one.
 */
export function RunStrip({
  run,
  running,
  queued,
  wait,
  onToggle,
  expanded,
  children,
}: {
  run: RunView;
  running: boolean;
  queued: boolean;
  wait: Wait | null;
  expanded: boolean;
  onToggle: () => void;
  /** What "Detalle" opens. Drawn inside this card, never as a block of its own. */
  children?: ReactNode;
}) {
  const tr: Translate = useT();
  const { t } = tr;
  const active = running || queued;
  const elapsed = useElapsed(run.job?.started_at ?? null, active);
  const status = run.job?.status;
  const overall = run.overall ?? null;
  const step = run.steps.filter((s) => s.status === "running").at(-1);

  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2.5">
        <span className="relative flex size-2 shrink-0">
          {running ? (
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60" />
          ) : null}
          <span
            className={cn(
              "relative inline-flex size-2 rounded-full",
              running ? "bg-primary" : "bg-muted-foreground",
            )}
          />
        </span>

        <span className="font-medium">{run.job ? jobName(run.job.kind, t, run.job.label) : null}</span>

        {status ? (
          <span className={cn("text-small font-medium", JOB_STATUS[status]?.tone)}>
            {JOB_STATUS[status] ? t(JOB_STATUS[status].labelKey) : status}
          </span>
        ) : null}

        <span className="flex items-center gap-1 text-small nums text-muted-foreground">
          <Hourglass className="size-3" />
          {duration(active ? elapsed : (run.job?.elapsed_ms ?? 0))}
        </span>

        {/* The wait REPLACES the progress and never sits beside it: nothing is being
            generated yet, and how many jobs are in front is the only honest measure of how
            far off it is. */}
        {queued ? (
          <span className="flex items-center gap-1.5 text-small font-medium">
            <Clock className="size-3.5" />
            {queuedLabel(wait, tr)}
          </span>
        ) : null}

        <span className="flex-1" />

        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex items-center gap-1 text-small text-muted-foreground transition-colors hover:text-foreground"
        >
          {t("run.detail")}
          <ChevronRight
            aria-hidden
            className={cn("size-3.5 transition-transform", expanded && "rotate-90")}
          />
        </button>

        {active ? <CancelButton run={run} /> : null}
      </div>

      {/* The reasons are the checker's own sentences, in the workspace's language, so they
          are printed rather than keyed: inventing a client-side table for them would be a
          second copy of `checks.py`. */}
      {running && !queued && run.retry ? (
        <div className="flex items-start gap-2 px-3 pb-2.5 text-small text-attention">
          <RotateCcw aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          <p className="min-w-0">
            {t("run.retrying", {
              index: run.retry.index,
              attempt: run.retry.attempt,
              max: run.retry.max,
            })}{" "}
            <span className="text-muted-foreground">{run.retry.reasons.join("; ")}</span>
          </p>
        </div>
      ) : null}

      {running && !queued ? (
        <div className="space-y-1.5 px-3 pb-2.5">
          <div className="flex items-baseline justify-between gap-2">
            <span className="min-w-0 truncate text-small text-muted-foreground">
              {/* The running phase, or the running step when there is no plan: both arrive
                  with the API's own sentence, and a phase key only means something inside
                  the plan it belongs to. */}
              {(overall?.label
                ? phaseName(phasePlan(run.job), overall.key, t, overall.label)
                : null) ??
                (step ? stepName(step.id, t, step.label) : null) ??
                t("progress.preparing")}
            </span>
            <span className="shrink-0 text-small font-medium nums">
              {overall
                ? `${overall.percent} %`
                : step?.total
                  ? `${step.current ?? 0}/${step.total}`
                  : "—"}
            </span>
          </div>
          <Progress
            value={overall ? overall.percent : (step?.current ?? 0)}
            max={overall ? 100 : (step?.total ?? null)}
          />
        </div>
      ) : null}

      {expanded && children ? <div className="border-t border-border">{children}</div> : null}
    </div>
  );
}

/** Open while it runs, shut once it is over — and whatever the person last chose after that. */
export function useRunDetail(running: boolean) {
  const [expanded, setExpanded] = useState(running);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (!touched) setExpanded(running);
  }, [running, touched]);

  return {
    expanded,
    toggle: () => {
      setTouched(true);
      setExpanded((value) => !value);
    },
  };
}

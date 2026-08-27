import { Ban, ChevronRight, Clock, Hourglass } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/misc";
import { JOB_STATUS, duration } from "@/lib/format";
import { queuedLabel, type Wait } from "@/lib/queue";
import { cn } from "@/lib/utils";
import { useCancelJob, useElapsed } from "@/state/queries";
import type { RunView } from "@/state/runStore";
import { useT, type Translate } from "@/lib/i18n";

/**
 * THE RUN, AS TWO LINES ABOVE THE THING IT PRODUCES.
 *
 * The generate screen used to be two columns: the five-step form on the left and, on the
 * right, a card carrying the timeline, the token stream, the technical details and an
 * activity feed — so while three items were being written the screen held a form nobody
 * was filling in, four live surfaces and the items themselves, side by side at half width
 * each. What one is there for is the items.
 *
 * So the run collapses to what a person actually watches: what is running, how far it has
 * got, how long it has been and how to stop it.
 *
 * WHAT IS BEHIND THE DISCLOSURE IS NOT DUPLICATED ANYWHERE, and that is why it is a
 * disclosure and not a deletion. The step timeline is also in «Ver ejecución», but the
 * token stream, the technical details and the exemplars the few-shot used are here and
 * nowhere else — folding them away is fine, dropping them is not. It opens by itself while
 * the job runs, because that is when watching the model write is worth a screen.
 */
export function RunStrip({
  run,
  running,
  queued,
  wait,
  onToggle,
  expanded,
}: {
  run: RunView;
  running: boolean;
  queued: boolean;
  wait: Wait | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  const tr: Translate = useT();
  const { t } = tr;
  const cancel = useCancelJob();
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

        <span className="font-medium">{run.job?.label}</span>

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

        {active ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => run.job && cancel.mutate(run.job.id)}
            disabled={cancel.isPending}
          >
            <Ban />
            {t("common.cancel")}
          </Button>
        ) : null}
      </div>

      {running && !queued ? (
        <div className="space-y-1.5 px-3 pb-2.5">
          <div className="flex items-baseline justify-between gap-2">
            <span className="min-w-0 truncate text-small text-muted-foreground">
              {overall?.label ?? step?.label ?? t("progress.preparing")}
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

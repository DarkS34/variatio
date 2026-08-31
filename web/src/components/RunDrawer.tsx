import { ChevronDown, ChevronsDownUp, ChevronsUpDown, ListTree } from "lucide-react";
import { useMemo, useState } from "react";

import { ActivityFeed } from "@/components/ActivityFeed";
import { RunTimeline } from "@/components/RunTimeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { JOB_EXPLAIN } from "@/lib/explain";
import { JOB_STATUS, duration } from "@/lib/format";
import { isQueued, pickActiveRun, waitOf, waitReason } from "@/lib/queue";
import { cn } from "@/lib/utils";
import { useLanes, useSplitEngine, useStream } from "@/state/queries";
import type { RunView } from "@/state/runStore";
import { useT } from "@/lib/i18n";
import { jobName } from "@/lib/names";
import { CancelButton } from "./CancelButton";

/**
 * The run the drawer is about, for a screen that has no job of its own.
 *
 * `stream.currentJobId` alone answered this while the queue was one deep. With one lane
 * per backend two jobs run at once and `currentJobId` is only the last one to emit an
 * event, so it flickered between them. A screen that DOES have a job of its own should ask
 * for it by kind (`useJobRun`) instead of taking whatever the machine is doing.
 */
export function useActiveRun(): RunView | null {
  const stream = useStream();
  return useMemo(
    () => pickActiveRun(stream.runs, stream.currentJobId),
    [stream.runs, stream.currentJobId],
  );
}

/**
 * The run in progress, at the foot of every screen: its steps and its running commentary.
 *
 * It carried a second tab, «Registro» — the pipeline's loguru output mirrored onto the bus
 * line by line — and that tab is gone (2026-08-31, explicit user request). Those lines are
 * written to `logs/<slug>/jobs.log` on the server now: they are diagnostics, they are read
 * next to a traceback, and half of them are in English since the pipeline's own log is. With
 * one view left there is no tab strip either.
 */
export function RunDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const tr = useT();
  const { t, plural } = useT();
  const run = useActiveRun();
  const lanes = useLanes();
  const split = useSplitEngine();
  const [tall, setTall] = useState(false);

  if (!open) return null;

  const status = run?.job?.status ?? "queued";
  const waiting = isQueued(run?.job);
  const wait = waitOf(run?.job, lanes);
  // A job that has not started yet is just as cancellable as one that has — the runner
  // drops a queued job outright — and it is the state one most wants to get out of.
  const active = status === "running" || waiting;
  const explain = run?.job ? JOB_EXPLAIN[run.job.kind] : undefined;

  return (
    <aside className="fixed inset-x-0 bottom-0 z-40 animate-slide-up border-t border-border bg-card shadow-overlay">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border px-3 py-2 sm:px-4">
        <ListTree className="size-4 shrink-0 text-muted-foreground" />
        <div className="flex min-w-0 items-center gap-1.5">
          <p className="truncate text-body font-medium">{run?.job ? jobName(run.job.kind, t, run.job.label) : t("run.untitled")}</p>
          {explain ? (
            <InfoHint label={t("run.whatThisJobDoes")}>
              <p>{t(explain.what)}</p>
              <p className="mt-1">
                <span className="font-medium">{t("run.produces")}</span> {t(explain.produces)}
              </p>
              <p className="mt-1">
                <span className="font-medium">{t("run.cost")}</span> {t(explain.cost)}
              </p>
            </InfoHint>
          ) : null}
        </div>

        <span className={cn("text-small font-medium", run?.job ? JOB_STATUS[status]?.tone : "text-muted-foreground")}>
          {run?.job && JOB_STATUS[status]
            ? t(JOB_STATUS[status].labelKey)
            : t("run.noRuns")}
        </span>
        {run?.job?.elapsed_ms !== null && run?.job?.elapsed_ms !== undefined ? (
          <span className="text-small nums text-muted-foreground">
            {duration(run.job.elapsed_ms)}
          </span>
        ) : null}
        {wait ? (
          <span className="text-small text-muted-foreground">{waitReason(wait, split, tr)}</span>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          {active && run?.job ? <CancelButton run={run} /> : null}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setTall((value) => !value)}
            aria-label={tall ? t("run.shrink") : t("run.expand")}
            title={tall ? t("run.shrink") : t("run.expand")}
          >
            {tall ? <ChevronsDownUp /> : <ChevronsUpDown />}
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label={t("run.collapse")}>
            <ChevronDown />
          </Button>
        </div>
      </header>

      <div
        className={cn(
          "thin-scroll overflow-y-auto p-3 sm:p-4",
          tall ? "max-h-[78vh]" : "max-h-[52vh]",
        )}
      >
        {!run ? (
          <p className="p-6 text-center text-body text-muted-foreground">
            {t("run.nothingRun")}
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <h4 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
                {t("run.steps")}
              </h4>
              <RunTimeline steps={run.steps} />
              {run.job?.error ? (
                <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-small text-destructive">
                  {run.job.error}
                </p>
              ) : null}
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <h4 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
                  {t("run.whatHappened")}
                </h4>
                {run.items.length > 0 ? (
                  <Badge variant="settled">{plural("run.itemCount", run.items.length)}</Badge>
                ) : null}
                {run.taggedCount > 0 ? (
                  <Badge variant="default">{plural("run.taggedCount", run.taggedCount)}</Badge>
                ) : null}
              </div>
              <ActivityFeed lines={run.activity} />
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

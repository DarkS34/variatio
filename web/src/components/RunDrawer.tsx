import { Ban, ChevronDown, ChevronsDownUp, ChevronsUpDown, ListTree } from "lucide-react";
import { useMemo, useState } from "react";

import { ActivityFeed } from "@/components/ActivityFeed";
import { LogViewer } from "@/components/LogViewer";
import { RunTimeline } from "@/components/RunTimeline";
import { TechnicalDetails } from "@/components/TechnicalDetails";
import { TokenStream } from "@/components/TokenStream";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Switch } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { JOB_EXPLAIN } from "@/lib/explain";
import { JOB_STATUS, duration } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useCancelJob, useStream } from "@/state/queries";
import type { RunView } from "@/state/runStore";

export type DrawerTab = "progress" | "model" | "logs";

export function useActiveRun(): RunView | null {
  const stream = useStream();
  return useMemo(() => {
    if (stream.currentJobId) return stream.runs[stream.currentJobId] ?? null;
    const runs = Object.values(stream.runs);
    if (runs.length === 0) return null;
    // Nothing is running: show the most recent finished run rather than an empty panel.
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream]);
}

export function RunDrawer({
  open,
  onClose,
  tab,
  onTab,
}: {
  open: boolean;
  onClose: () => void;
  tab: DrawerTab;
  onTab: (next: DrawerTab) => void;
}) {
  const run = useActiveRun();
  const stream = useStream();
  const cancel = useCancelJob();
  const [tall, setTall] = useState(false);
  const [onlyThisJob, setOnlyThisJob] = useState(false);

  if (!open) return null;

  const status = run?.job?.status ?? "queued";
  const active = status === "running";
  const explain = run?.job ? JOB_EXPLAIN[run.job.kind] : undefined;
  const logs = onlyThisJob && run ? run.logs : stream.logs;

  return (
    <aside className="fixed inset-x-0 bottom-0 z-40 animate-slide-up border-t border-border bg-card shadow-2xl">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border px-4 py-2">
        <ListTree className="size-4 shrink-0 text-muted-foreground" />
        <div className="flex min-w-0 items-center gap-1.5">
          <p className="truncate text-sm font-medium">{run?.job?.label ?? "Ejecución"}</p>
          {explain ? (
            <InfoHint label="Qué hace este trabajo">
              <p>{explain.what}</p>
              <p className="mt-1">
                <span className="font-medium">Produce:</span> {explain.produces}
              </p>
              <p className="mt-1">
                <span className="font-medium">Coste:</span> {explain.cost}
              </p>
            </InfoHint>
          ) : null}
          {run?.model ? (
            <span className="truncate text-xs text-muted-foreground">· {run.model}</span>
          ) : null}
        </div>

        <span className={cn("text-xs font-medium", run?.job ? JOB_STATUS[status]?.tone : "text-muted-foreground")}>
          {run?.job ? JOB_STATUS[status]?.label : "Sin ejecuciones en esta sesión"}
        </span>
        {run?.job?.elapsed_ms !== null && run?.job?.elapsed_ms !== undefined ? (
          <span className="text-xs tabular-nums text-muted-foreground">
            {duration(run.job.elapsed_ms)}
          </span>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          <Tabs
            items={[
              { value: "progress", label: "Progreso" },
              { value: "model", label: "Modelo" },
              {
                value: "logs",
                label: "Registro",
                badge: stream.logs.length ? (
                  <Badge variant="outline" className="ml-1">
                    {stream.logs.length}
                  </Badge>
                ) : undefined,
              },
            ]}
            value={tab}
            onChange={(next) => onTab(next as DrawerTab)}
          />
          {active && run?.job ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => cancel.mutate(run.job!.id)}
              disabled={cancel.isPending}
            >
              <Ban />
              Cancelar
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setTall((value) => !value)}
            aria-label={tall ? "Reducir el panel" : "Ampliar el panel"}
            title={tall ? "Reducir el panel" : "Ampliar el panel"}
          >
            {tall ? <ChevronsDownUp /> : <ChevronsUpDown />}
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Contraer">
            <ChevronDown />
          </Button>
        </div>
      </header>

      <div
        className={cn(
          "thin-scroll overflow-y-auto p-4",
          tall ? "max-h-[78vh]" : "max-h-[52vh]",
        )}
      >
        {tab === "logs" ? (
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <Switch
                checked={onlyThisJob}
                onCheckedChange={setOnlyThisJob}
                disabled={!run}
                label="solo este trabajo"
              />
              Solo este trabajo
            </label>
            <LogViewer logs={logs} height={tall ? "62vh" : "38vh"} />
          </div>
        ) : !run ? (
          <p className="p-6 text-center text-sm text-muted-foreground">
            Nada ejecutado en esta sesión.
          </p>
        ) : tab === "progress" ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Pasos
              </h4>
              <RunTimeline steps={run.steps} />
              {run.job?.error ? (
                <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
                  {run.job.error}
                </p>
              ) : null}
            </div>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Qué ha ido pasando
                </h4>
                {run.items.length > 0 ? (
                  <Badge variant="success">{run.items.length} ítem(s)</Badge>
                ) : null}
                {run.taggedCount > 0 ? (
                  <Badge variant="info">{run.taggedCount} etiquetado(s)</Badge>
                ) : null}
              </div>
              <ActivityFeed lines={run.activity} />
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <TokenStream
              answer={run.answer}
              thinking={run.thinking}
              phase={run.phase}
              active={active}
              height={tall ? "34rem" : "16rem"}
            />
            <TechnicalDetails run={run} />
          </div>
        )}
      </div>
    </aside>
  );
}

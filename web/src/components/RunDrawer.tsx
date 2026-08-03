import { ChevronDown, Ban, ListTree } from "lucide-react";
import { useMemo } from "react";

import { RunTimeline } from "@/components/RunTimeline";
import { TechnicalDetails } from "@/components/TechnicalDetails";
import { TokenStream } from "@/components/TokenStream";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { JOB_STATUS, duration } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useCancelJob, useStream } from "@/state/queries";
import type { RunView } from "@/state/runStore";

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

export function RunDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const run = useActiveRun();
  const cancel = useCancelJob();

  if (!open) return null;

  const status = run?.job?.status ?? "queued";
  const active = status === "running";

  return (
    <aside className="fixed inset-x-0 bottom-0 z-40 animate-slide-up border-t border-border bg-card shadow-2xl">
      <header className="flex items-center gap-3 border-b border-border px-4 py-2">
        <ListTree className="size-4 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">
            {run?.job?.label ?? "Ejecución"}
            {run?.model ? (
              <span className="ml-2 font-normal text-muted-foreground">· {run.model}</span>
            ) : null}
          </p>
        </div>
        <span className={cn("text-xs font-medium", JOB_STATUS[status]?.tone)}>
          {JOB_STATUS[status]?.label}
        </span>
        {run?.job?.elapsed_ms !== null && run?.job?.elapsed_ms !== undefined ? (
          <span className="text-xs tabular-nums text-muted-foreground">
            {duration(run.job.elapsed_ms)}
          </span>
        ) : null}
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
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Contraer">
          <ChevronDown />
        </Button>
      </header>

      {run ? (
        <div className="grid max-h-[52vh] grid-cols-1 gap-4 overflow-y-auto p-4 lg:grid-cols-2 thin-scroll">
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
                Salida del modelo
              </h4>
              {run.items.length > 0 ? (
                <Badge variant="success">{run.items.length} ítem(s)</Badge>
              ) : null}
              {run.taggedCount > 0 ? (
                <Badge variant="info">{run.taggedCount} etiquetado(s)</Badge>
              ) : null}
            </div>
            <TokenStream answer={run.answer} thinking={run.thinking} active={active} height="14rem" />
            <TechnicalDetails run={run} />
          </div>
        </div>
      ) : (
        <p className="p-6 text-center text-sm text-muted-foreground">
          Aún no se ha ejecutado nada en esta sesión.
        </p>
      )}
    </aside>
  );
}

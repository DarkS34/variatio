import { Ban, Hourglass } from "lucide-react";

import { RunTimeline } from "@/components/RunTimeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PhaseBar, Progress, Spinner } from "@/components/ui/misc";
import { duration } from "@/lib/format";
import type { ArtifactName, BuildPhase } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { RunView } from "@/state/runStore";
import { useArtifactRun, useBuildPhases, useCancelJob, useElapsed } from "@/state/queries";

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
  const run = useArtifactRun(artifact);
  const phases = useBuildPhases(artifact);
  return (
    <JobProgress
      run={run}
      phases={phases}
      className={className}
      waiting="Construyendo. El detalle aparecerá en cuanto el proceso emita su primer paso."
    />
  );
}

/**
 * La misma tarjeta, para cualquier trabajo con un plan de fases.
 *
 * `BuildProgress` la envuelve con el plan del artefacto que se construye; los trabajos que
 * no escriben ninguno —la revisión de etiquetabilidad, que parchea una lista en su sitio—
 * la usan directamente con su propio plan. Eran la misma barra, y separarlas habría dado
 * dos formas distintas de dibujar lo mismo.
 */
export function JobProgress({
  run,
  phases,
  className,
  waiting = "En marcha. El detalle aparecerá en cuanto el proceso emita su primer paso.",
}: {
  run: RunView | null;
  phases: BuildPhase[];
  className?: string;
  waiting?: string;
}) {
  const cancel = useCancelJob();
  const status = run?.job?.status;
  const active = status === "running" || status === "queued";
  const elapsed = useElapsed(run?.job?.started_at ?? null, active);

  if (!run || !run.job) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Spinner />
          {waiting}
        </CardContent>
      </Card>
    );
  }

  const overall = run.overall;
  const step = run.steps.filter((s) => s.status === "running").at(-1);
  const position = phases.findIndex((phase) => phase.key === overall?.key);

  return (
    <Card className={className}>
      <CardContent className="space-y-4 py-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="relative flex size-2 shrink-0">
            {active ? (
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-[var(--info)] opacity-60" />
            ) : null}
            <span
              className={cn(
                "relative inline-flex size-2 rounded-full",
                active ? "bg-[var(--info)]" : "bg-muted-foreground",
              )}
            />
          </span>
          {/* Sin (i): esta tarjeta sale bajo la cabecera del artefacto, que ya explica qué
              es, y el nombre del trabajo más la fase en curso dicen qué está pasando. La
              explicación del trabajo sigue estando una vez, en el cajón de ejecución. */}
          <p className="text-sm font-medium">{run.job.label}</p>
          <span className="flex items-center gap-1 text-xs tabular-nums text-muted-foreground">
            <Hourglass className="size-3" />
            {duration(elapsed)}
          </span>
          {active ? (
            <Button
              size="sm"
              variant="outline"
              className="ml-auto"
              onClick={() => cancel.mutate(run.job!.id)}
              disabled={cancel.isPending}
            >
              <Ban />
              Cancelar
            </Button>
          ) : null}
        </div>

        {/* Sin plan de fases todavía (arranque, o carga de modelos) la barra es
            indeterminada a propósito: mejor eso que un 0 % que parece atascado. */}
        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between gap-3">
            <p className="min-w-0 truncate text-sm">
              {position >= 0 ? (
                <span className="mr-1.5 tabular-nums text-muted-foreground">
                  {position + 1}/{phases.length}
                </span>
              ) : null}
              {overall?.label ?? step?.label ?? "Preparando el proceso…"}
            </p>
            <span className="shrink-0 text-sm font-medium tabular-nums">
              {overall ? `${overall.percent} %` : "—"}
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
            <Progress value={overall?.percent ?? 0} max={overall ? 100 : null} />
          )}

          {overall?.detail ? (
            <p className="truncate text-xs text-muted-foreground">{overall.detail}</p>
          ) : null}
        </div>

        <div className="space-y-2">
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Pasos
          </h4>
          <RunTimeline steps={run.steps} />
          {run.job.error ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
              {run.job.error}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

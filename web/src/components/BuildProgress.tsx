import { Ban, Hourglass, Timer } from "lucide-react";

import { RunTimeline } from "@/components/RunTimeline";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { PhaseBar, Progress, Spinner } from "@/components/ui/misc";
import { JOB_EXPLAIN } from "@/lib/explain";
import { approx, duration } from "@/lib/format";
import type { ArtifactName } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  projectRemaining,
  useArtifactRun,
  useBuildEstimate,
  useCancelJob,
  useElapsed,
} from "@/state/queries";

/**
 * What a build is doing right now, on the screen of the thing being built.
 *
 * The drawer already shows every step of every run; this is the other question — "how
 * much is left of *this* artifact?" — answered where it is asked, in the two forms the
 * question has: the share of the plan already done (the segmented bar, whose sections
 * are the builder's own phases) and the time still to wait (the estimate, which comes
 * from the documents the build is reading). The percentage comes from the builder's
 * weighted phase plan, not from the running step, because steps nest and none of them
 * knows the size of the whole.
 */
export function BuildProgress({
  artifact,
  className,
}: {
  artifact: ArtifactName;
  className?: string;
}) {
  const run = useArtifactRun(artifact);
  const cancel = useCancelJob();
  const estimate = useBuildEstimate(artifact);
  const status = run?.job?.status;
  const active = status === "running" || status === "queued";
  const elapsed = useElapsed(run?.job?.started_at ?? null, active);
  const remaining = projectRemaining(estimate, run?.overall?.percent ?? null, elapsed);
  const explain = run?.job ? JOB_EXPLAIN[run.job.kind] : undefined;

  if (!run || !run.job) {
    return (
      <Card className={className}>
        <CardContent className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
          <Spinner />
          Construyendo. El detalle aparecerá en cuanto el proceso emita su primer paso.
        </CardContent>
      </Card>
    );
  }

  const overall = run.overall;
  const step = run.steps.filter((s) => s.status === "running").at(-1);
  const phases = estimate?.phases ?? [];
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
          <p className="text-sm font-medium">{run.job.label}</p>
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

          <div
            className={cn(
              "flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1",
              !overall?.detail && !estimate && "hidden",
            )}
          >
            <p className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
              {overall?.detail ?? ""}
            </p>
            {estimate ? (
              <span className="flex shrink-0 items-center gap-1 text-xs tabular-nums text-muted-foreground">
                <Timer className="size-3" />
                {active ? `faltan ≈ ${approx(remaining)}` : `≈ ${approx(estimate.seconds * 1000)}`}
                <EstimateHint artifact={artifact} />
              </span>
            ) : null}
          </div>
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

/**
 * Where the number comes from, spelled out.
 *
 * An estimate nobody can check is a number to distrust the first time it is wrong, so
 * it shows its inputs — the documents, the pages, the fragments — and what each phase
 * is expected to cost. That is also what makes it obvious *why* a second build is much
 * cheaper than the first: the conversion no longer has anything left to convert.
 */
export function EstimateHint({ artifact }: { artifact: ArtifactName }) {
  const estimate = useBuildEstimate(artifact);
  if (!estimate) return null;

  const { basis, phases } = estimate;
  return (
    <InfoHint label="De dónde sale la estimación">
      <p>
        Calculada sobre {basis.documents} documento(s) ({basis.pages} página(s),{" "}
        {basis.chunks} fragmento(s) de texto) con los tiempos medidos por llamada en esta
        instalación. Es una estimación: el reloj real depende de lo que el modelo decida
        escribir en cada paso.
      </p>
      {basis.pending_pages > 0 || basis.pending_documents > 0 ? (
        <p className="mt-1">
          Incluye la conversión de {basis.pending_pages || basis.pending_documents} documento(s)
          o página(s) que aún no están transcritos. Una segunda construcción se los ahorra.
        </p>
      ) : (
        <p className="mt-1">
          Los documentos ya están transcritos en caché, así que esta construcción no paga
          la conversión.
        </p>
      )}
      <ul className="mt-1 space-y-0.5">
        {phases
          .filter((phase) => phase.seconds > 0)
          .map((phase) => (
            <li key={phase.key} className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate">{phase.label}</span>
              <span className="shrink-0 tabular-nums">{approx(phase.seconds * 1000)}</span>
            </li>
          ))}
      </ul>
    </InfoHint>
  );
}

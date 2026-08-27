import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Ban,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Cpu,
  Hourglass,
  Lock,
  Pencil,
  Server,
  UploadCloud,
  WifiOff,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { BuildButton } from "@/components/BuildButton";
import { BuildProgress } from "@/components/BuildProgress";
import { RawImport } from "@/components/RawImport";
import { useActiveRun } from "@/components/RunDrawer";
import { StageBadge } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Alert, PhaseBar, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { TranscriptionSection } from "@/features/raw/TranscriptionSection";
import { useTranscriptionSummary } from "@/features/raw/queries";
import { api } from "@/lib/api";
import { JOB_EXPLAIN } from "@/lib/explain";
import { ENGINE_LABEL, JOB_STATUS, bytes, duration, when } from "@/lib/format";
import { isQueued } from "@/lib/queue";
import { Link, useRouter } from "@/lib/router";
import type { Health, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ContextCard } from "./ContextCard";
import {
  useArtifactRun,
  useBuildPhases,
  useCancelJob,
  useElapsed,
  useHealth,
  useInvalidateChain,
  useJobRunning,
  keys,
  usePipeline,
  useRaw,
  useStream,
} from "@/state/queries";

const SCREEN: Record<string, string> = {
  exemplars_profile: "/preparar/perfil",
  knowledge_graph: "/preparar/grafo",
  exemplars_bank: "/preparar/banco",
};

const EXPLAIN: Record<string, string> = {
  exemplars_profile:
    "Define el esquema de un ítem y las guías de extracción y generación. Se infiere de una muestra de los ejemplares en bruto.",
  knowledge_graph:
    "El vocabulario de conceptos y dominios. Es la única fuente de conceptos que podrá usarse después: nada fuera de aquí puede etiquetarse ni generarse.",
  exemplars_bank:
    "Los ítems extraídos de los documentos, etiquetados con conceptos del grafo. Alimentan los ejemplos few-shot de la generación.",
};

function StageCard({ stage }: { stage: StageState }) {
  const blocked = Boolean(stage.blocked_reason);
  const missing = stage.status === "missing";
  const building = stage.status === "building";
  // A queued build already marks the artifact, which is right — it is about to be
  // rewritten — but a bar over a job that has not started claims work is happening. While
  // it waits, the button says so instead, which is also the control that would cancel it.
  const stageRun = useArtifactRun(stage.artifact);
  const queued = building && isQueued(stageRun?.job);

  return (
    <Card
      className={cn(
        "relative transition-colors",
        stage.status === "approved" && "border-[color-mix(in_oklch,var(--settled)_45%,var(--border))]",
        stage.status === "stale" && "border-destructive/50",
        blocked && "opacity-70",
      )}
    >
      <CardHeader className="pb-2">
        {/* No ordinal here. The cards are laid out in `server/review.ARTIFACTS` order and
            that order is load-bearing, but numbering it said something the layout already
            says — and said it wrongly to anyone who reads the chain as graph-first. What
            state the stage is in is `StageBadge`'s job, in a shape and a word; the numbered
            circle also turned green, so it was a third drawing of the same fact. */}
        <div className="flex items-center gap-2">
          <div className="flex flex-1 items-center gap-1.5">
            <CardTitle>{stage.label}</CardTitle>
            <InfoHint label={`Qué es ${stage.label}`}>{EXPLAIN[stage.artifact]}</InfoHint>
          </div>
          <StageBadge stage={stage} />
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {stage.stale_because.length > 0 ? (
          <div className="space-y-1 rounded-md border border-destructive/40 bg-destructive/10 p-2">
            {stage.stale_because.map((cause) => (
              <p key={cause.artifact} className="text-small text-destructive">
                {cause.reason}
              </p>
            ))}
          </div>
        ) : null}

        {blocked ? (
          <p className="flex items-center gap-1.5 text-small text-muted-foreground">
            <Lock className="size-3.5" />
            {stage.blocked_reason}
          </p>
        ) : null}

        {stage.approved_at && stage.status === "approved" ? (
          <p className="text-small text-muted-foreground">Aprobado el {when(stage.approved_at)}</p>
        ) : null}

        {building && !queued ? <BuildProgress artifact={stage.artifact} /> : null}

        <div className="flex flex-wrap gap-2 pt-1">
          {/* While building there is nothing to review: the artifact's screen hides the existing one
              until it finishes, and this card already shows the progress. */}
          {missing || building ? null : (
            <Link to={SCREEN[stage.artifact]}>
              <Button size="sm" variant={stage.status === "approved" ? "outline" : "default"} disabled={blocked}>
                <Pencil />
                {stage.status === "approved" ? "Revisar de nuevo" : "Revisar"}
              </Button>
            </Link>
          )}
          {building && !queued ? null : (
            <BuildButton stage={stage} variant={missing ? "default" : "ghost"} />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function RawSection() {
  const raw = useRaw();
  const slots = raw.data?.slots ?? [];
  const emptySlots = slots.filter((slot) => slot.files.length === 0);
  const [open, setOpen] = useState(false);
  const expanded = open || emptySlots.length > 0;
  const total = slots.reduce((sum, slot) => sum + slot.files.length, 0);
  const size = slots.reduce((sum, slot) => sum + slot.bytes, 0);
  const transcription = useTranscriptionSummary(slots);

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          disabled={emptySlots.length > 0}
          className="flex items-center gap-1.5 text-body font-medium disabled:cursor-default"
        >
          {emptySlots.length > 0 ? (
            <UploadCloud className="size-4 text-attention" />
          ) : (
            <ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} />
          )}
          Datos en bruto
        </button>
        {total > 0 ? (
          <span className="text-small text-muted-foreground">
            {total} archivo(s) · {bytes(size)}
          </span>
        ) : null}
        {emptySlots.length > 0 ? (
          <Badge variant="attention">
            {emptySlots.map((slot) => slot.label.toLowerCase()).join(" y ")} sin archivos
          </Badge>
        ) : null}
        {transcription.running ? (
          <Badge mark={<Spinner className="size-3" />}>transcribiendo</Badge>
        ) : transcription.stale > 0 ? (
          <Badge variant="attention">transcripción caducada</Badge>
        ) : null}
        {!expanded ? (
          <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
            <UploadCloud />
            Importar
          </Button>
        ) : null}
      </div>

      {expanded ? (
        <>
          <RawImport />
          <TranscriptionSection slots={slots} />
        </>
      ) : null}
    </section>
  );
}

/** `PHASE_LLM` → "Phase": the config constant is what asks for the model, but the tail
 *  of its name is noise once they are grouped under the model they all point at. */
function settingLabel(name: string): string {
  const stem = name.replace(/_(LLM|MODEL)$/, "").replace(/_/g, " ").toLowerCase();
  return stem.charAt(0).toUpperCase() + stem.slice(1);
}

/**
 * Which models the engine has loaded NOW, not how many constants name them.
 *
 * This row used to count the distinct models that appear in `config.py`, and that measures
 * the configuration file, not the machine: a named constant is not a loaded model, and with
 * all of them pointing at the same value the number was almost always the same whatever the
 * GPU said. What does answer «what is this using» is `/api/ps`: what is resident, how much
 * VRAM it takes and until when — the only honest reading of residency from here, because the
 * server does not run on the GPU machine.
 *
 * The ones the instance *asks for* stay reachable by opening the list, because that is where
 * one sees whether one is not installed and which phase would go without it.
 */
function ModelsRow({ models }: { models: Health["models"] }) {
  const [open, setOpen] = useState(false);

  const resident = useMemo(
    () => [...models.running].sort((a, b) => (b.size_vram ?? 0) - (a.size_vram ?? 0)),
    [models.running],
  );
  const vram = resident.reduce((sum, entry) => sum + (entry.size_vram ?? 0), 0);

  const required = useMemo(() => {
    const byModel = new Map<string, string[]>();
    for (const [setting, model] of Object.entries(models.required)) {
      if (!byModel.has(model)) byModel.set(model, []);
      byModel.get(model)!.push(setting);
    }
    return [...byModel.entries()]
      .map(([model, settings]) => ({
        model,
        settings: settings.sort(),
        missing: models.missing.includes(model),
        remote: (models.remote ?? []).includes(model),
        loaded: resident.some((entry) => entry.model === model),
      }))
      .sort((a, b) => b.settings.length - a.settings.length || a.model.localeCompare(b.model));
  }, [models, resident]);

  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <span className="text-muted-foreground">Modelos cargados</span>
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Ver qué hay cargado y qué modelos pide la instancia"
          className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {models.missing.length > 0 ? (
            <Badge variant="danger" className="cursor-pointer hover:opacity-85">
              {models.missing.length} sin instalar
            </Badge>
          ) : resident.length === 0 ? (
            <Badge variant="outline" className="cursor-pointer hover:opacity-85">
              ninguno en memoria
            </Badge>
          ) : (
            <Badge variant="settled" className="cursor-pointer hover:opacity-85">
              {resident.length} · {bytes(vram)}
            </Badge>
          )}
        </button>
      </div>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Modelos"
        description="Arriba, lo que el motor tiene residente en este momento; abajo, lo que la instancia pide en su configuración."
        className="max-w-2xl"
      >
        <div className="space-y-4">
          <section className="space-y-2">
            <h3 className="text-micro font-condensed uppercase text-muted-foreground">
              En memoria ahora ({resident.length})
            </h3>
            {resident.length === 0 ? (
              <p className="text-body text-muted-foreground">
                El motor no tiene ningún modelo cargado. El primer trabajo que necesite uno
                paga su carga.
              </p>
            ) : (
              <ul className="space-y-2">
                {resident.map((entry) => (
                  <li key={entry.model} className="rounded-lg border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <code className="font-mono text-body">{entry.model}</code>
                      <span className="ml-auto text-micro nums text-muted-foreground">
                        {entry.size_vram ? `${bytes(entry.size_vram)} en VRAM` : "sin VRAM"}
                      </span>
                    </div>
                    <p className="mt-1 flex flex-wrap gap-x-3 text-small text-muted-foreground">
                      {entry.context_length ? (
                        <span className="nums">
                          contexto {entry.context_length.toLocaleString("es-ES")}
                        </span>
                      ) : null}
                      {entry.expires_at ? <span>reside hasta {when(entry.expires_at)}</span> : null}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            {vram > 0 ? (
              <p className="text-small nums text-muted-foreground">
                {bytes(vram)} de VRAM ocupados en total.
              </p>
            ) : null}
          </section>

          <section className="space-y-2 border-t border-border pt-3">
            <h3 className="text-micro font-condensed uppercase text-muted-foreground">
              Los que pide la instancia ({required.length})
            </h3>
            <ul className="space-y-2">
              {required.map(({ model, settings, missing, remote, loaded }) => (
                <li key={model} className="rounded-lg border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-mono text-body">{model}</code>
                    {remote ? (
                      <Badge variant="outline">remoto</Badge>
                    ) : missing ? (
                      <Badge variant="danger">sin instalar</Badge>
                    ) : loaded ? (
                      <Badge variant="settled">cargado</Badge>
                    ) : (
                      <Badge variant="outline">en disco</Badge>
                    )}
                    <span className="ml-auto text-micro nums text-muted-foreground">
                      {settings.length} fase(s)
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {settings.map((setting) => (
                      <Badge key={setting} variant="secondary" title={setting}>
                        {settingLabel(setting)}
                      </Badge>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </Dialog>
    </>
  );
}

/**
 * What the system is doing right now — the one place it is said.
 *
 * The header carried this state and competed for width with the tabs until it pushed them
 * into a horizontal scroll, so it moves down here whole. It speaks of *any* job, not of the
 * mode that launched it: building, indexing, tagging, generating and evaluating come out of
 * the same stream and read the same. The step by step stays in the run drawer; this only
 * answers «what is running, how long has it been, and can I stop it».
 */
function ActivityCard() {
  const run = useActiveRun();
  const stream = useStream();
  const pipeline = usePipeline();
  const cancel = useCancelJob();

  const status = run?.job?.status;
  const active = status === "running" || status === "queued";
  const elapsed = useElapsed(run?.job?.started_at ?? null, active);
  const step = useMemo(() => run?.steps.filter((s) => s.status === "running").at(-1), [run]);
  const explain = run?.job ? JOB_EXPLAIN[run.job.kind] : undefined;
  const overall = run?.overall ?? null;
  const queued = pipeline.data?.queued ?? 0;
  const ahead = pipeline.data?.queue_ahead ?? null;
  // Only a build has a phase plan; everything else keeps the plain bar.
  const phases = useBuildPhases(run?.job?.artifact ?? undefined);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Activity className="size-4 text-muted-foreground" />
          Actividad
          <InfoHint label="Qué se ve aquí">
            El trabajo que el servidor tiene en marcha, sea cual sea: construir un
            artefacto, indexar, etiquetar el banco, generar o evaluar. El detalle paso a
            paso y el registro están en «Ver ejecución», abajo a la derecha.
          </InfoHint>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-body">
        {stream.connected ? null : (
          <p className="flex items-center gap-1.5 text-small text-attention">
            <WifiOff className="size-3.5 shrink-0" />
            Sin conexión con el servidor; reintentando.
          </p>
        )}

        {!run?.job ? (
          // «Nada en ejecución» would be a lie when the one GPU is busy with another
          // workspace: your own screen is idle and the next job you launch will wait,
          // and nothing else on the page would say why.
          pipeline.data?.engine_busy_elsewhere ? (
            <p className="flex items-start gap-1.5 text-small text-muted-foreground">
              <Hourglass className="mt-0.5 size-3.5 shrink-0" />
              Nada tuyo en ejecución. La GPU está ocupada con un trabajo de otro
              workspace: solo se ejecuta uno cada vez, así que lo que lances ahora
              esperará su turno.
            </p>
          ) : (
            <p className="text-muted-foreground">Nada en ejecución.</p>
          )
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
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
              <span className="font-medium">{run.job.label}</span>
            </div>

            {/* The explanation goes as text and not behind an (i): it was in both places at once, and
                of the two the one that gets read is the one already on screen. */}
            <p className="text-small text-muted-foreground">
              {explain?.what ?? "Trabajo en curso."}
            </p>

            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-small">
              <span className={cn("font-medium", JOB_STATUS[status!]?.tone)}>
                {JOB_STATUS[status!]?.label}
              </span>
              <span className="flex items-center gap-1 nums text-muted-foreground">
                <Hourglass className="size-3" />
                {duration(active ? elapsed : run.job.elapsed_ms)}
              </span>
              {status === "queued" && ahead !== null ? (
                <span className="text-muted-foreground">
                  {ahead === 0
                    ? "siguiente en arrancar"
                    : `${ahead} trabajo${ahead === 1 ? "" : "s"} delante`}
                </span>
              ) : queued > 0 ? (
                <span className="text-muted-foreground">{queued} en cola</span>
              ) : null}
            </div>

            {/* With no overall percentage the bar is indeterminate on purpose: a step can be at 8/8
                and still have half a run ahead. */}
            {active ? (
              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate text-small">
                    {overall?.label ?? step?.label ?? "Preparando el proceso…"}
                  </span>
                  <span className="shrink-0 text-small font-medium nums">
                    {overall
                      ? `${overall.percent} %`
                      : step?.total
                        ? `${step.current ?? 0}/${step.total}`
                        : "—"}
                  </span>
                </div>
                {overall && phases.length > 0 ? (
                  <PhaseBar
                    phases={phases}
                    percent={overall.percent}
                    activeKey={overall.key}
                  />
                ) : (
                  <Progress
                    value={overall ? overall.percent : (step?.current ?? 0)}
                    max={overall ? 100 : (step?.total ?? null)}
                  />
                )}
                {overall?.detail ? (
                  <p className="truncate text-small text-muted-foreground">{overall.detail}</p>
                ) : null}
              </div>
            ) : null}

            {run.job.error ? (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-small text-destructive">
                {run.job.error}
              </p>
            ) : null}

            {active ? (
              <Button
                size="sm"
                variant="outline"
                className="w-full"
                onClick={() => cancel.mutate(run.job!.id)}
                disabled={cancel.isPending}
              >
                <Ban />
                Cancelar
              </Button>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function SystemCard() {
  const health = useHealth();
  const invalidate = useInvalidateChain();
  const client = useQueryClient();
  const warm = useMutation({
    mutationFn: () => api.submitJob("warm_models", {}, true),
    onSuccess: invalidate,
  });
  const warming = useJobRunning("warm_models");
  useEffect(() => {
    if (!warming) client.invalidateQueries({ queryKey: keys.health });
  }, [warming, client]);

  if (health.isLoading) return <Skeleton className="h-40" />;
  if (!health.data) {
    return (
      <Alert tone="danger" title="Sin servidor">
        <p>La API no responde en el puerto 8000.</p>
      </Alert>
    );
  }

  const { available, engine, models } = health.data;
  const wanted = [...new Set(Object.values(models.required))];
  const cold = wanted.filter((m) => !models.running.some((entry) => entry.model === m));

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Server className="size-4 text-muted-foreground" />
          Sistema
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-body">
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">Motor de inferencia</span>
          <span className="flex items-center gap-1.5">
            {/* Reachable or not used to be one dot in two hues, which is the worst case
                of colour-only encoding: it is the single line this panel is read for. */}
            {available ? (
              <CircleCheck className="size-3.5 shrink-0 text-settled" />
            ) : (
              <CircleAlert className="size-3.5 shrink-0 text-destructive" />
            )}
            <span className="font-medium">{ENGINE_LABEL[engine] ?? engine}</span>
            {available ? null : (
              <span className="text-small text-destructive">sin conexión</span>
            )}
          </span>
        </div>

        <ModelsRow models={models} />

        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            Modelos en memoria
            <InfoHint label="Qué es calentar los modelos">
              Cargar en la GPU los modelos que pide la instancia antes de que haga falta. En
              frío, el primer trabajo que los necesite paga la carga; calentarlos la adelanta.
            </InfoHint>
          </span>
          {cold.length === 0 ? (
            <Badge variant="settled">Calientes</Badge>
          ) : (
            <div className="flex items-center gap-2">
              <Badge variant="outline">
                {cold.length === wanted.length ? "Fríos" : `${cold.length} en frío`}
              </Badge>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => warm.mutate()}
                disabled={warm.isPending || warming || !available}
              >
                {warm.isPending || warming ? <Spinner /> : <Cpu />}
                Calentar
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function Dashboard() {
  const pipeline = usePipeline();
  const { navigate } = useRouter();

  if (pipeline.isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-56" />
        <Skeleton className="h-56" />
        <Skeleton className="h-56" />
      </div>
    );
  }

  const stages = pipeline.data?.stages ?? [];
  const next = stages.find((s) => s.status !== "approved");

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-2">
        <h1 className="font-display font-expanded text-display">Panel</h1>
        <InfoHint label="Cómo funciona la cadena">
          Cada artefacto se construye, se revisa y se aprueba antes de desbloquear el siguiente.
          Se revisa una vez al principio; después se generan variantes contra una instancia
          congelada.
        </InfoHint>
      </header>

      <RawSection />

      {next ? (
        <Alert
          tone="info"
          title={`Siguiente paso: ${next.label}`}
          action={
            <Button size="sm" onClick={() => navigate(SCREEN[next.artifact])}>
              Ir
              <ArrowRight />
            </Button>
          }
        >
          <p>
            {next.blocked_reason ??
              (next.status === "missing"
                ? "Todavía no existe: hay que construirlo."
                : "Existe pero no está aprobado.")}
          </p>
        </Alert>
      ) : (
        <Alert
          tone="settled"
          title="Cadena aprobada de principio a fin"
          action={
            <Button size="sm" onClick={() => navigate("/generar")}>
              Generar
              <ArrowRight />
            </Button>
          }
        />
      )}

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="grid content-start gap-4 lg:col-span-3 xl:grid-cols-3">
          {stages.map((stage) => (
            <StageCard key={stage.artifact} stage={stage} />
          ))}
        </div>
        {/* «Sistema» opens the column: it is what gets checked at a glance — whether the engine
            answers, what it has loaded — and at the very bottom one had to scroll to find it. It is
            also the shortest of the three, so it does not push the other two away. */}
        <div className="space-y-4">
          <SystemCard />
          <ActivityCard />
          <ContextCard />
        </div>
      </div>

    </div>
  );
}

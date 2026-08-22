import { useMutation } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Ban,
  ChevronRight,
  CircleCheck,
  CircleDashed,
  Cpu,
  Hourglass,
  Lock,
  Pencil,
  Server,
  UploadCloud,
  WifiOff,
} from "lucide-react";
import { useMemo, useState } from "react";

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
import { Alert, PhaseBar, Progress, Separator, Skeleton, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { JOB_EXPLAIN } from "@/lib/explain";
import { ENGINE_LABEL, JOB_STATUS, bytes, duration, when } from "@/lib/format";
import { Link, useRouter } from "@/lib/router";
import type { Health, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useBuildPhases,
  useCancelJob,
  useElapsed,
  useHealth,
  useInvalidateChain,
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

function StageCard({ stage, index }: { stage: StageState; index: number }) {
  const blocked = Boolean(stage.blocked_reason);
  const missing = stage.status === "missing";
  const building = stage.status === "building";

  return (
    <Card
      className={cn(
        "relative transition-colors",
        stage.status === "approved" && "border-[color-mix(in_oklch,var(--success)_45%,var(--border))]",
        stage.status === "stale" && "border-destructive/50",
        blocked && "opacity-70",
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
              stage.status === "approved"
                ? "bg-[var(--success)] text-background"
                : "bg-muted text-muted-foreground",
            )}
          >
            {stage.status === "approved" ? <CircleCheck className="size-3.5" /> : index + 1}
          </span>
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
              <p key={cause.artifact} className="text-xs text-destructive">
                {cause.reason}
              </p>
            ))}
          </div>
        ) : null}

        {blocked ? (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Lock className="size-3.5" />
            {stage.blocked_reason}
          </p>
        ) : null}

        {stage.approved_at && stage.status === "approved" ? (
          <p className="text-xs text-muted-foreground">Aprobado el {when(stage.approved_at)}</p>
        ) : null}

        {building ? <BuildProgress artifact={stage.artifact} /> : null}

        <div className="flex flex-wrap gap-2 pt-1">
          {/* Mientras se construye no hay nada que revisar: la pantalla del artefacto
              oculta el que hay hasta que termine, y esta tarjeta ya muestra el progreso. */}
          {missing || building ? null : (
            <Link to={SCREEN[stage.artifact]}>
              <Button size="sm" variant={stage.status === "approved" ? "outline" : "default"} disabled={blocked}>
                <Pencil />
                {stage.status === "approved" ? "Revisar de nuevo" : "Revisar"}
              </Button>
            </Link>
          )}
          {building ? null : (
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

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          disabled={emptySlots.length > 0}
          className="flex items-center gap-1.5 text-sm font-medium disabled:cursor-default"
        >
          {emptySlots.length > 0 ? (
            <UploadCloud className="size-4 text-[var(--warning)]" />
          ) : (
            <ChevronRight className={cn("size-4 transition-transform", expanded && "rotate-90")} />
          )}
          Datos en bruto
        </button>
        {total > 0 ? (
          <span className="text-xs text-muted-foreground">
            {total} archivo(s) · {bytes(size)}
          </span>
        ) : null}
        {emptySlots.length > 0 ? (
          <Badge variant="attention">
            {emptySlots.map((slot) => slot.label.toLowerCase()).join(" y ")} sin archivos
          </Badge>
        ) : null}
        {!expanded ? (
          <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>
            <UploadCloud />
            Importar
          </Button>
        ) : null}
      </div>

      {expanded ? <RawImport /> : null}
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
 * Qué modelos tiene el motor cargados AHORA, no cuántas constantes los nombran.
 *
 * Esta fila contaba antes los modelos distintos que aparecen en `config.py`, y eso mide el
 * fichero de configuración, no la máquina: una constante nombrada no es un modelo cargado,
 * y con todas apuntando al mismo valor el número era casi siempre el mismo dijera lo que
 * dijera la GPU. Lo que sí responde a «qué está usando esto» es `/api/ps`: qué está
 * residente, cuánta VRAM ocupa y hasta cuándo — la única lectura honesta de residencia
 * desde aquí, porque el servidor no corre en la máquina de la GPU.
 *
 * Los que la instancia *pide* siguen accesibles al abrir la lista, porque es donde se ve
 * si uno está sin instalar y qué fase se quedaría sin él.
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
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              En memoria ahora ({resident.length})
            </h3>
            {resident.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                El motor no tiene ningún modelo cargado. El primer trabajo que necesite uno
                paga su carga.
              </p>
            ) : (
              <ul className="space-y-2">
                {resident.map((entry) => (
                  <li key={entry.model} className="rounded-lg border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <code className="font-mono text-sm">{entry.model}</code>
                      <span className="ml-auto text-xs tabular-nums text-muted-foreground">
                        {entry.size_vram ? `${bytes(entry.size_vram)} en VRAM` : "sin VRAM"}
                      </span>
                    </div>
                    <p className="mt-1 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                      {entry.context_length ? (
                        <span className="tabular-nums">
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
              <p className="text-xs tabular-nums text-muted-foreground">
                {bytes(vram)} de VRAM ocupados en total.
              </p>
            ) : null}
          </section>

          <section className="space-y-2 border-t border-border pt-3">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Los que pide la instancia ({required.length})
            </h3>
            <ul className="space-y-2">
              {required.map(({ model, settings, missing, loaded }) => (
                <li key={model} className="rounded-lg border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-mono text-sm">{model}</code>
                    {missing ? (
                      <Badge variant="danger">sin instalar</Badge>
                    ) : loaded ? (
                      <Badge variant="settled">cargado</Badge>
                    ) : (
                      <Badge variant="outline">en disco</Badge>
                    )}
                    <span className="ml-auto text-xs tabular-nums text-muted-foreground">
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
 * Qué está haciendo el sistema ahora mismo — el único sitio donde se dice.
 *
 * La cabecera llevaba este estado y competía por el ancho con las pestañas hasta
 * empujarlas a un scroll horizontal, así que baja aquí entero. Habla de *cualquier*
 * trabajo, no del modo que lo lanzó: construir, indexar, etiquetar, generar y evaluar
 * salen del mismo stream y se leen igual. El paso a paso sigue en el cajón de ejecución;
 * esto responde solo a «qué hay en marcha, cuánto lleva y puedo pararlo».
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
      <CardContent className="space-y-3 text-sm">
        {stream.connected ? null : (
          <p className="flex items-center gap-1.5 text-xs text-[var(--warning)]">
            <WifiOff className="size-3.5 shrink-0" />
            Sin conexión con el servidor; reintentando.
          </p>
        )}

        {!run?.job ? (
          // «Nada en ejecución» would be a lie when the one GPU is busy with another
          // workspace: your own screen is idle and the next job you launch will wait,
          // and nothing else on the page would say why.
          pipeline.data?.engine_busy_elsewhere ? (
            <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
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
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-[var(--info)] opacity-60" />
                ) : null}
                <span
                  className={cn(
                    "relative inline-flex size-2 rounded-full",
                    active ? "bg-[var(--info)]" : "bg-muted-foreground",
                  )}
                />
              </span>
              <span className="font-medium">{run.job.label}</span>
            </div>

            {/* La explicación va como texto y no detrás de una (i): estaba en las dos
                partes a la vez, y de las dos la que se lee es la que ya está en pantalla. */}
            <p className="text-xs text-muted-foreground">
              {explain?.what ?? "Trabajo en curso."}
            </p>

            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              <span className={cn("font-medium", JOB_STATUS[status!]?.tone)}>
                {JOB_STATUS[status!]?.label}
              </span>
              <span className="flex items-center gap-1 tabular-nums text-muted-foreground">
                <Hourglass className="size-3" />
                {duration(active ? elapsed : run.job.elapsed_ms)}
              </span>
              {queued > 0 ? (
                <span className="text-muted-foreground">{queued} en cola</span>
              ) : null}
            </div>

            {/* Sin porcentaje global la barra es indeterminada a propósito: un paso puede
                ir por 8/8 y quedar aún media ejecución por delante. */}
            {active ? (
              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate text-xs">
                    {overall?.label ?? step?.label ?? "Preparando el proceso…"}
                  </span>
                  <span className="shrink-0 text-xs font-medium tabular-nums">
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
                  <p className="truncate text-xs text-muted-foreground">{overall.detail}</p>
                ) : null}
              </div>
            ) : null}

            {run.job.error ? (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
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
  const raw = useRaw();
  const invalidate = useInvalidateChain();
  const index = useMutation({
    mutationFn: () => api.submitJob("index", {}, true),
    onSuccess: invalidate,
  });

  if (health.isLoading) return <Skeleton className="h-40" />;
  if (!health.data) {
    return (
      <Alert tone="danger" title="Sin servidor">
        <p>La API no responde en el puerto 8000.</p>
      </Alert>
    );
  }

  const { available, engine, host, models, context_ready } = health.data;
  const slots = raw.data?.slots ?? [];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Server className="size-4 text-muted-foreground" />
          Sistema
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">Motor de inferencia</span>
          <span className="flex items-center gap-1.5">
            <span
              className={cn(
                "size-1.5 rounded-full",
                available ? "bg-[var(--success)]" : "bg-destructive",
              )}
            />
            <span className="font-medium">{ENGINE_LABEL[engine] ?? engine}</span>
            <span className="font-mono text-xs text-muted-foreground">{host}</span>
            {available ? null : (
              <span className="text-xs text-destructive">sin conexión</span>
            )}
          </span>
        </div>

        <ModelsRow models={models} />

        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            Índices en memoria
            <InfoHint label="Qué son los índices en memoria">
              Los embeddings del grafo y del banco, cargados en RAM. En frío, el primer trabajo
              que los necesite paga la carga; calentarlos la adelanta.
            </InfoHint>
          </span>
          {context_ready ? (
            <Badge variant="settled">Calientes</Badge>
          ) : (
            <div className="flex items-center gap-2">
              <Badge variant="outline">Fríos</Badge>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => index.mutate()}
                disabled={index.isPending || !available}
              >
                {index.isPending ? <Spinner /> : <Cpu />}
                Calentar
              </Button>
            </div>
          )}
        </div>

        <Separator />

        <div className="space-y-1 text-xs text-muted-foreground">
          {slots.map((slot) => (
            <p key={slot.kind} className="flex items-center gap-1.5">
              {slot.files.length > 0 ? (
                <CircleCheck className="size-3.5 shrink-0 text-[var(--success)]" />
              ) : (
                <CircleDashed className="size-3.5 shrink-0" />
              )}
              <span className="min-w-0 flex-1 truncate">
                {slot.label}
              </span>
              <span className="tabular-nums">{slot.files.length} archivo(s)</span>
            </p>
          ))}
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
        <h1 className="text-xl font-semibold tracking-tight">Panel</h1>
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
          tone="success"
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
          {stages.map((stage, index) => (
            <StageCard key={stage.artifact} stage={stage} index={index} />
          ))}
        </div>
        <div className="space-y-4">
          <ActivityCard />
          <SystemCard />
        </div>
      </div>

    </div>
  );
}

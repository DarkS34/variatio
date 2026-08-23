import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  Cable,
  Database,
  Download,
  Flame,
  HardDrive,
  PlugZap,
  Power,
  Trash2,
  Unplug,
  X,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select } from "@/components/ui/input";
import { Alert, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { bytes, duration, JOB_STATUS, when } from "@/lib/format";
import type { AdminEngine, AdminOverview, Job, PullStatus, TunnelStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  keys,
  useAdminCancelJob,
  useAdminEngine,
  useAdminJobHistory,
  useAdminJobs,
  useAdminSystem,
  useEngineActions,
} from "@/state/queries";

/**
 * The machine and the process, as one screen.
 *
 * Everything here is global to the installation: the one GPU and what it holds, the port
 * forward that reaches it, the models on the engine's disk, the contexts this process keeps
 * warm, the queue and its past, and the database. None of it belongs to a workspace, which
 * is why it was scattered — a count on the panel's «Sistema» card, the queue under
 * «Workspaces» — and why it is gathered here.
 */
export function EngineTab({ overview }: { overview: AdminOverview }) {
  const engine = useAdminEngine();
  if (engine.isLoading) return <Skeleton className="h-96" />;
  if (!engine.data) return null;
  const data = engine.data;

  return (
    <div className="space-y-5">
      <div className="grid gap-4 lg:grid-cols-2">
        <TunnelCard tunnel={data.tunnel} available={data.available} host={data.host} />
        <ResidencyCard engine={data} overview={overview} />
      </div>
      <QueueSection />
      <ModelsCard engine={data} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ContextsCard engine={data} overview={overview} />
        <SystemCard />
      </div>
      <HistorySection />
    </div>
  );
}

/* The tunnel ----------------------------------------------------------------------------- */

function TunnelCard({
  tunnel,
  available,
  host,
}: {
  tunnel: TunnelStatus;
  available: boolean;
  host: string;
}) {
  const { tunnelStart, tunnelStop } = useEngineActions();
  const toast = useToast();

  const state = !tunnel.configured
    ? { label: "sin configurar", tone: "outline" as const }
    : tunnel.running
      ? { label: "conectado", tone: "settled" as const }
      : tunnel.wanted
        ? { label: "reconectando", tone: "attention" as const }
        : { label: "apagado", tone: "outline" as const };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Cable className="size-4 text-muted-foreground" />
          <CardTitle>Túnel SSH</CardTitle>
          <Badge variant={state.tone}>{state.label}</Badge>
          <InfoHint label="Qué hace el túnel">
            El motor corre en otra máquina; este túnel reenvía el puerto local de
            «OLLAMA_HOST» al puerto de Ollama en la máquina de la GPU, con el cliente ssh del
            servidor y tus claves. Se enciende y apaga desde aquí; si el proceso de ssh muere
            se relanza solo mientras esté pedido. El destino y el puerto remoto se fijan en
            «Configuración», bajo «Túnel SSH».
          </InfoHint>
        </div>
        <CardDescription>
          {tunnel.configured
            ? `${host} → ${tunnel.host}:${tunnel.remote_port}`
            : "Rellena OLLAMA_SSH_HOST en «Configuración» para poder levantarlo desde aquí."}
          {tunnel.autostart ? " · arranca con la API" : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {tunnel.wanted ? (
            <Button
              variant="outline"
              disabled={tunnelStop.isPending}
              onClick={() =>
                tunnelStop.mutate(undefined, {
                  onSuccess: () => toast({ title: "Túnel apagado" }),
                })
              }
            >
              {tunnelStop.isPending ? <Spinner /> : <Unplug />}
              Desconectar
            </Button>
          ) : (
            <Button
              disabled={!tunnel.configured || tunnelStart.isPending}
              onClick={() =>
                tunnelStart.mutate(undefined, {
                  onSuccess: (status) =>
                    toast({
                      title: status.running ? "Túnel abierto" : "Túnel pedido",
                      description: status.running
                        ? `ssh en marcha (pid ${status.pid})`
                        : "ssh arrancará en cuanto pueda",
                    }),
                  onError: (error: Error) =>
                    toast({ title: "No se ha podido abrir", description: error.message, tone: "danger" }),
                })
              }
            >
              {tunnelStart.isPending ? <Spinner /> : <PlugZap />}
              Conectar
            </Button>
          )}
          <span className="text-small text-muted-foreground">
            {tunnel.running && tunnel.since
              ? `desde hace ${duration((Date.now() / 1000 - tunnel.since) * 1000)}`
              : tunnel.attempts > 0
                ? `${tunnel.attempts} intento(s)`
                : null}
            {tunnel.running ? (available ? " · el motor responde" : " · el motor no responde aún") : null}
          </span>
        </div>
        <FormError error={tunnelStart.error ?? tunnelStop.error} />
        {tunnel.last_error && !tunnel.running ? (
          <Alert tone="attention" title="Último error">
            <p className="font-mono text-small">{tunnel.last_error}</p>
          </Alert>
        ) : null}
        {tunnel.stderr.length > 0 ? (
          <details className="text-small text-muted-foreground">
            <summary className="cursor-pointer select-none">Lo que dijo ssh</summary>
            <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted p-2 font-mono text-micro">
              {tunnel.stderr.join("\n")}
            </pre>
          </details>
        ) : null}
      </CardContent>
    </Card>
  );
}

/* Residency ------------------------------------------------------------------------------ */

function ResidencyCard({ engine, overview }: { engine: AdminEngine; overview: AdminOverview }) {
  const { release } = useEngineActions();
  const client = useQueryClient();
  const toast = useToast();
  const [slug, setSlug] = useState(overview.workspaces[0]?.slug ?? "");
  const warm = useMutation({
    mutationFn: (target: string) => api.adminWarmModels(target),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.adminJobs });
      toast({ title: "Calentado en cola", description: slug });
    },
  });
  const vram = engine.running.reduce((sum, m) => sum + (m.size_vram ?? 0), 0);
  const idleMinutes = Math.floor(engine.idle.seconds / 60);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Flame className="size-4 text-muted-foreground" />
          <CardTitle>La GPU</CardTitle>
          <Badge variant={engine.available ? "settled" : "outline"}>
            {engine.available ? "motor en línea" : "motor sin conexión"}
          </Badge>
        </div>
        <CardDescription>
          {engine.running.length > 0
            ? `${engine.running.length} modelo(s) residentes · ${bytes(vram)} de VRAM`
            : "Nada residente ahora mismo"}
          {engine.busy
            ? " · trabajando"
            : engine.idle.threshold > 0
              ? ` · ${idleMinutes} min sin trabajos (se libera a los ${Math.floor(engine.idle.threshold / 60)})`
              : " · la liberación automática está desactivada"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {engine.running.length > 0 ? (
          <ul className="divide-y divide-border rounded-md border border-border text-small">
            {engine.running.map((model) => (
              <li key={model.model} className="flex flex-wrap items-center justify-between gap-2 px-2 py-1.5">
                <span className="font-mono">{model.model}</span>
                <span className="nums text-muted-foreground">
                  {model.size_vram ? bytes(model.size_vram) : "—"}
                  {model.context_length ? ` · ctx ${model.context_length.toLocaleString("es-ES")}` : ""}
                  {model.expires_at ? ` · hasta ${when(model.expires_at)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="flex flex-wrap items-end gap-2">
          <Button
            variant="outline"
            disabled={release.isPending || engine.running.length === 0 || engine.busy}
            title={
              engine.busy
                ? "Hay un trabajo en curso"
                : engine.running.length === 0
                  ? "No hay nada cargado"
                  : "Descargar todos los modelos de la GPU ahora; el próximo trabajo los vuelve a cargar (~30 s)"
            }
            onClick={() =>
              release.mutate(undefined, {
                onSuccess: ({ released }) =>
                  toast({ title: "GPU liberada", description: `${released.length} modelo(s) descargados.` }),
                onError: (error: Error) =>
                  toast({ title: "No se ha podido liberar", description: error.message, tone: "danger" }),
              })
            }
          >
            {release.isPending ? <Spinner /> : <Power />}
            Liberar la GPU
          </Button>
          <div className="space-y-1">
            <Label htmlFor="warm-workspace">Calentar para</Label>
            <Select
              id="warm-workspace"
              value={slug}
              className="w-48"
              onChange={(event) => setSlug(event.target.value)}
            >
              {overview.workspaces.map((w) => (
                <option key={w.slug} value={w.slug}>
                  {w.name}
                </option>
              ))}
            </Select>
          </div>
          <Button
            variant="outline"
            disabled={!slug || !engine.available || warm.isPending}
            title="Carga en memoria los modelos del siguiente paso de ese workspace"
            onClick={() => warm.mutate(slug)}
          >
            {warm.isPending ? <Spinner /> : <Flame />}
            Calentar
          </Button>
        </div>
        <FormError error={release.error ?? warm.error} />
      </CardContent>
    </Card>
  );
}

/* Models on disk ------------------------------------------------------------------------- */

function ModelsCard({ engine }: { engine: AdminEngine }) {
  const { pull, remove } = useEngineActions();
  const toast = useToast();
  const [name, setName] = useState("");
  const resident = new Set(engine.running.map((m) => m.model));
  const missing = engine.required.filter((r) => r.state === "sin instalar");

  const confirmDelete = (model: string) => {
    if (!window.confirm(`¿Borrar '${model}' del disco del motor?\n\nHabrá que volver a descargarlo para usarlo.`)) return;
    remove.mutate(model, {
      onSuccess: () => toast({ title: "Modelo borrado", description: model, tone: "attention" }),
      onError: (error: Error) =>
        toast({ title: "No se ha podido borrar", description: error.message, tone: "danger" }),
    });
  };

  const startPull = (model: string) => {
    pull.mutate(model, {
      onSuccess: () => {
        setName("");
        toast({ title: "Descarga iniciada", description: model });
      },
      onError: (error: Error) =>
        toast({ title: "No se ha podido iniciar", description: error.message, tone: "danger" }),
    });
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <HardDrive className="size-4 text-muted-foreground" />
          <CardTitle>Modelos en el disco del motor</CardTitle>
          <InfoHint label="Qué se puede hacer aquí">
            Lo que Ollama tiene descargado, y qué ajustes piden cada uno. Descargar uno nuevo
            es lo que hace falta antes de elegirlo en «Configuración»; borrar uno libera disco
            en la máquina de la GPU. No se borra un modelo que algún ajuste nombre.
          </InfoHint>
        </div>
        <CardDescription>
          {engine.installed.length} en disco ·{" "}
          {bytes(engine.installed.reduce((sum, m) => sum + (m.size ?? 0), 0))}
          {missing.length > 0 ? ` · ${missing.length} que la configuración pide y faltan` : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {missing.length > 0 ? (
          <Alert tone="attention" title="Faltan modelos que la configuración pide">
            <ul className="space-y-1">
              {missing.map((row) => (
                <li key={row.model} className="flex flex-wrap items-center gap-2">
                  <span className="font-mono">{row.model}</span>
                  <span className="text-muted-foreground">({row.asked_by.join(", ")})</span>
                  <Button size="sm" variant="outline" disabled={pull.isPending} onClick={() => startPull(row.model)}>
                    <Download />
                    Descargar
                  </Button>
                </li>
              ))}
            </ul>
          </Alert>
        ) : null}

        {engine.pulls.length > 0 ? (
          <ul className="space-y-2">
            {engine.pulls.map((item) => (
              <PullRow key={item.model} pull={item} />
            ))}
          </ul>
        ) : null}

        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-64 flex-1 space-y-1">
            <Label htmlFor="pull-model">Descargar un modelo</Label>
            <Input
              id="pull-model"
              placeholder="nombre:etiqueta, tal como lo conoce Ollama"
              value={name}
              disabled={!engine.available}
              onChange={(event) => setName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && name.trim()) startPull(name.trim());
              }}
            />
          </div>
          <Button disabled={!name.trim() || !engine.available || pull.isPending} onClick={() => startPull(name.trim())}>
            {pull.isPending ? <Spinner /> : <Download />}
            Descargar
          </Button>
        </div>
        <FormError error={pull.error ?? remove.error} />

        {engine.installed.length > 0 ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <Table minWidth="40rem">
              <THead>
                <TR>
                  <TH>Modelo</TH>
                  <TH align="num">En disco</TH>
                  <TH>Estado</TH>
                  <TH>Lo piden</TH>
                  <TH />
                </TR>
              </THead>
              <TBody>
                {engine.installed.map((model) => {
                  const asked = model.asked_by.length > 0;
                  return (
                    <TR key={model.model}>
                      <TD className="px-3 py-2 font-mono text-small">{model.model}</TD>
                      <TD align="num" className="px-3 py-2 nums text-small">
                        {model.size ? bytes(model.size) : "—"}
                      </TD>
                      <TD className="px-3 py-2">
                        {resident.has(model.model) ? (
                          <Badge variant="settled">cargado</Badge>
                        ) : (
                          <Badge variant="outline">en disco</Badge>
                        )}
                      </TD>
                      <TD className="px-3 py-2 text-small text-muted-foreground">
                        {asked ? model.asked_by.join(", ") : "nadie"}
                      </TD>
                      <TD align="num" className="px-3 py-2">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          disabled={asked || remove.isPending || engine.busy}
                          title={
                            asked
                              ? "Lo pide la configuración: cambia esos ajustes antes"
                              : engine.busy
                                ? "Hay un trabajo en curso"
                                : "Borrar del disco del motor"
                          }
                          onClick={() => confirmDelete(model.model)}
                        >
                          <Trash2 />
                        </Button>
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          </div>
        ) : (
          <p className="text-small text-muted-foreground">
            {engine.available ? "El motor no tiene ningún modelo en disco." : "Sin conexión con el motor: no se puede listar lo instalado."}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function PullRow({ pull }: { pull: PullStatus }) {
  const running = pull.status === "running";
  const tone = pull.status === "failed" ? "danger" : pull.status === "succeeded" ? "settled" : "primary";
  return (
    <li className="space-y-1 rounded-md border border-border p-2 text-small">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono">{pull.model}</span>
        <span className="nums text-muted-foreground">
          {running
            ? pull.total > 0
              ? `${bytes(pull.completed)} de ${bytes(pull.total)}`
              : "preparando…"
            : pull.status === "succeeded"
              ? "descargado"
              : "falló"}
          {pull.user ? ` · ${pull.user}` : ""}
        </span>
      </div>
      <Progress value={pull.completed} max={running ? pull.total : pull.total || 1} tone={tone} />
      {pull.error ? <p className="text-destructive">{pull.error}</p> : null}
    </li>
  );
}

/* Warm contexts -------------------------------------------------------------------------- */

function ContextsCard({ engine, overview }: { engine: AdminEngine; overview: AdminOverview }) {
  const { invalidate, invalidateAll } = useEngineActions();
  const toast = useToast();
  const names = new Map(overview.workspaces.map((w) => [w.slug, w.name]));

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Contextos en memoria</CardTitle>
          <InfoHint label="Qué es un contexto">
            El índice de conceptos y el banco de un workspace, embebidos y listos para
            etiquetar o generar. Construirlo cuesta minutos, así que el proceso guarda hasta
            ocho. Invalidar uno obliga al próximo trabajo a reconstruirlo desde los ficheros:
            es lo que se hace cuando algo parece rancio.
          </InfoHint>
        </div>
        <CardDescription>
          {engine.contexts.length === 0
            ? "Ninguno: el próximo trabajo de cada workspace construirá el suyo."
            : `${engine.contexts.length} de 8 como máximo`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {engine.contexts.length > 0 ? (
          <ul className="divide-y divide-border rounded-md border border-border text-small">
            {engine.contexts.map((slug) => (
              <li key={slug} className="flex items-center justify-between gap-2 px-2 py-1.5">
                <span>
                  {names.get(slug) ?? slug}
                  <span className="ml-2 font-mono text-micro text-muted-foreground">{slug}</span>
                </span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  title="Invalidar este contexto"
                  disabled={invalidate.isPending}
                  onClick={() =>
                    invalidate.mutate(slug, {
                      onSuccess: () => toast({ title: "Contexto invalidado", description: slug }),
                      onError: (error: Error) =>
                        toast({ title: "No se ha podido", description: error.message, tone: "danger" }),
                    })
                  }
                >
                  <X />
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {engine.contexts.length > 1 ? (
          <Button
            variant="outline"
            size="sm"
            disabled={invalidateAll.isPending}
            onClick={() =>
              invalidateAll.mutate(undefined, {
                onSuccess: ({ invalidated }) =>
                  toast({ title: "Contextos invalidados", description: `${invalidated}` }),
                onError: (error: Error) =>
                  toast({ title: "No se ha podido", description: error.message, tone: "danger" }),
              })
            }
          >
            Invalidar todos
          </Button>
        ) : null}
        <FormError error={invalidate.error ?? invalidateAll.error} />
      </CardContent>
    </Card>
  );
}

/* The database and the process ----------------------------------------------------------- */

function SystemCard() {
  const system = useAdminSystem();
  if (system.isLoading) return <Skeleton className="h-40" />;
  const data = system.data;
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Database className="size-4 text-muted-foreground" />
          <CardTitle>Base de datos y proceso</CardTitle>
        </div>
        <CardDescription>
          {data ? (
            <>
              {data.database.location} · esquema{" "}
              <span className="font-mono">{data.database.revision ?? "—"}</span>
              {data.database.head && data.database.head !== data.database.revision ? (
                <Badge variant="attention" className="ml-2">
                  migración pendiente ({data.database.head})
                </Badge>
              ) : null}
            </>
          ) : (
            "Sin conexión con la base de datos"
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <FormError error={system.error} />
        {data ? (
          <>
            <p className="text-small text-muted-foreground">
              API en marcha desde hace {duration(data.process.uptime_seconds * 1000)} · registro en{" "}
              <span className="font-mono">{data.process.log_level}</span>
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-small sm:grid-cols-3">
              {Object.entries(data.database.tables).map(([table, count]) => (
                <div key={table} className="flex justify-between gap-2">
                  <dt className="font-mono text-muted-foreground">{table}</dt>
                  <dd className="nums">{count.toLocaleString("es-ES")}</dd>
                </div>
              ))}
            </dl>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

/* The queue ----------------------------------------------------------------------------- */

/**
 * The one GPU's queue, across every workspace and every account.
 *
 * Jobs run strictly in the order they were asked for: the running one first, then the
 * waiting ones by position. Each member sees only their own workspace's entries from
 * inside it; this is the only place the whole line is visible, and the only place an
 * entry of someone else's can be taken out of it.
 */
function QueueSection() {
  const jobs = useAdminJobs();
  const cancel = useAdminCancelJob();
  const toast = useToast();

  const running = jobs.data?.running ?? null;
  const queued = jobs.data?.queued ?? [];
  const rows = [...(running ? [running] : []), ...queued];

  const confirmCancel = (job: Job) => {
    const verb = job.status === "running" ? "Detener" : "Quitar de la cola";
    const message =
      `¿${verb} «${job.label}» de ${job.workspace}` +
      `${job.user_name ? `, pedido por ${job.user_name}` : ""}?` +
      (job.status === "running"
        ? "\n\nSe cancela en el siguiente punto de control y el siguiente de la cola arranca."
        : "");
    if (!window.confirm(message)) return;
    cancel.mutate(job.id, {
      onSuccess: () =>
        toast({
          title: job.status === "running" ? "Cancelación pedida" : "Quitado de la cola",
          description: `«${job.label}» de ${job.workspace}`,
          tone: "attention",
        }),
      onError: (error: Error) =>
        toast({ title: "No se ha podido cancelar", description: error.message, tone: "danger" }),
    });
  };

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          Cola de la GPU ({rows.length})
        </h2>
        <InfoHint label="Cómo funciona la cola">
          Hay una GPU y se ejecuta un trabajo cada vez. Lo que se pide mientras está ocupada
          —construir, generar, evaluar, de cualquier workspace— se apila por orden de llegada
          y arranca solo cuando termina lo anterior. Cada persona ve desde su instancia solo
          lo suyo; aquí se ve la fila entera y se puede sacar a cualquiera de ella.
        </InfoHint>
      </div>

      {jobs.isLoading ? (
        <Skeleton className="h-16" />
      ) : rows.length === 0 ? (
        <p className="text-small text-muted-foreground">Nada en ejecución ni en espera.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table minWidth="48rem">
            <THead>
              <TR>
                <TH align="num">#</TH>
                <TH>Trabajo</TH>
                <TH>Workspace</TH>
                <TH>Pedido por</TH>
                <TH>Pedido</TH>
                <TH>Estado</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {rows.map((job, index) => {
                const active = job.status === "running";
                return (
                  <TR key={job.id}>
                    <TD align="num" className="px-3 py-2 nums text-muted-foreground">
                      {active ? "—" : index + (running ? 0 : 1)}
                    </TD>
                    <TD className="px-3 py-2">{job.label}</TD>
                    <TD className="px-3 py-2 font-mono text-small">{job.workspace}</TD>
                    <TD className="px-3 py-2 text-small">{job.user_name ?? "—"}</TD>
                    <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
                      {when(new Date(job.created_at * 1000).toISOString())}
                    </TD>
                    <TD className="px-3 py-2">
                      <span className={cn("text-small font-medium", JOB_STATUS[job.status].tone)}>
                        {JOB_STATUS[job.status].label}
                      </span>
                    </TD>
                    <TD align="num" className="whitespace-nowrap px-3 py-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={cancel.isPending}
                        title={active ? "Detener el trabajo en curso" : "Quitar de la cola"}
                        onClick={() => confirmCancel(job)}
                      >
                        {active ? <Ban /> : <Trash2 />}
                        {active ? "Detener" : "Quitar"}
                      </Button>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </div>
      )}
      <FormError error={cancel.error} />
    </section>
  );
}

/* The queue's past ----------------------------------------------------------------------- */

function HistorySection() {
  const history = useAdminJobHistory();
  const jobs = history.data?.jobs ?? [];
  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          Trabajos terminados ({jobs.length})
        </h2>
        <InfoHint label="De dónde sale">
          Lo que la cola ha ejecutado desde que arrancó la API, de todos los workspaces. Vive
          en memoria: reiniciar la API lo vacía. El detalle de cada uno está en el registro de
          ejecución de su workspace.
        </InfoHint>
      </div>
      {history.isLoading ? (
        <Skeleton className="h-16" />
      ) : jobs.length === 0 ? (
        <p className="text-small text-muted-foreground">Ninguno desde que arrancó la API.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table minWidth="48rem">
            <THead>
              <TR>
                <TH>Trabajo</TH>
                <TH>Workspace</TH>
                <TH>Pedido por</TH>
                <TH>Terminó</TH>
                <TH align="num">Duró</TH>
                <TH>Estado</TH>
              </TR>
            </THead>
            <TBody>
              {jobs.map((job) => (
                <TR key={job.id}>
                  <TD className="px-3 py-2">
                    {job.label}
                    {job.error ? (
                      <span className="block truncate text-micro text-destructive" title={job.error}>
                        {job.error}
                      </span>
                    ) : null}
                  </TD>
                  <TD className="px-3 py-2 font-mono text-small">{job.workspace || "—"}</TD>
                  <TD className="px-3 py-2 text-small">{job.user_name ?? "—"}</TD>
                  <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
                    {job.finished_at ? when(new Date(job.finished_at * 1000).toISOString()) : "—"}
                  </TD>
                  <TD align="num" className="whitespace-nowrap px-3 py-2 nums text-small">
                    {duration(job.elapsed_ms)}
                  </TD>
                  <TD className="px-3 py-2">
                    <span className={cn("text-small font-medium", JOB_STATUS[job.status].tone)}>
                      {JOB_STATUS[job.status].label}
                    </span>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </div>
      )}
    </section>
  );
}

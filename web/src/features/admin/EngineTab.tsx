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
import { CerebrasCard } from "@/features/admin/CerebrasCard";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { bytes, duration, JOB_STATUS, when } from "@/lib/format";
import type {
  AdminEngine,
  AdminOverview,
  Job,
  PullStatus,
  RunningModel,
  TunnelStatus,
} from "@/lib/types";
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
import { useT, type Key } from "@/lib/i18n";

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

  // THE TAB IS ABOUT ONE ENGINE, AND THE ENGINE DECIDES HOW MANY HALVES IT HAS. Until
  // 2026-08-26 every card here spoke about the GPU, while the installation could be routing
  // its heaviest phases to Cerebras with nothing on screen saying so.
  //
  // What makes the two one subject rather than two lists is the question they both answer —
  // what limits the work here — so «Local» leads with the VRAM three models have to share
  // and «Remoto» with the quota, drawn with the same meters at a very different magnitude.
  //
  // THE SPLIT IS DRAWN ONLY WHEN THERE ARE TWO HALVES (2026-08-26, explicit user request).
  // On the plain `ollama` engine the tab goes back to being one panel about one machine,
  // headings included: «Local» with no «Remoto» beside it divides nothing, and a Cerebras
  // card kept alive by yesterday's spending would describe an engine this installation is
  // no longer running. The ledger keeps that history either way — switching back brings it
  // straight back, and `GET /engine/cerebras/export.csv` never stopped serving it.
  //
  // `cerebras` is read defensively because it can genuinely be absent: an API older than
  // this bundle does not send it, and a bare `data.cerebras.active` took the WHOLE tab down
  // with a blank screen — the failure this project already refuses elsewhere («un panel que
  // no puede cargar sus datos lo dice; nunca renderiza null»). Missing simply means no
  // remote half, which is the same thing the plain `ollama` engine means.
  const remote = data.cerebras?.active ?? false;

  return (
    <div className="space-y-5">
      {remote ? <Half titleKey="eng.half.local" noteKey="eng.half.localNote" /> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <TunnelCard tunnel={data.tunnel} available={data.available} host={data.host} />
        <ResidencyCard engine={data} overview={overview} />
      </div>
      <ModelsCard engine={data} />

      {remote ? (
        <>
          <Half titleKey="eng.half.remote" noteKey="eng.half.remoteNote" />
          <CerebrasCard cerebras={data.cerebras!} />
        </>
      ) : null}

      {remote ? (
        <Half titleKey="eng.half.process" noteKey="eng.half.processNote" />
      ) : null}
      <QueueSection />
      <div className="grid gap-4 lg:grid-cols-2">
        <ContextsCard engine={data} overview={overview} />
        <SystemCard />
      </div>
      <HistorySection />
    </div>
  );
}

/** A rule under a display-width word, drawn only while the tab has more than one subject. */
function Half({ titleKey, noteKey }: { titleKey: Key; noteKey: Key }) {
  const { t } = useT();
  return (
    <div className="flex flex-wrap items-baseline gap-3 border-b border-primary pb-2">
      <h2 className="font-expanded text-title">{t(titleKey)}</h2>
      <p className="text-small text-muted-foreground">{t(noteKey)}</p>
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
  const { t, plural } = useT();
  const { tunnelStart, tunnelStop } = useEngineActions();
  const toast = useToast();

  // The engine answering on the local port while this process runs no ssh means the port is
  // reached some other way — a tunnel opened by hand, or Ollama on this machine. That is
  // not «apagado», and offering «Conectar» would launch an ssh onto a port already taken.
  const external = available && !tunnel.running && !tunnel.wanted;
  const state = external
    ? { labelKey: "tunnel.external" as const, tone: "settled" as const }
    : !tunnel.configured
      ? { labelKey: "tunnel.unconfigured" as const, tone: "outline" as const }
      : tunnel.running
        ? { labelKey: "tunnel.connected" as const, tone: "settled" as const }
        : tunnel.wanted
          ? { labelKey: "tunnel.reconnecting" as const, tone: "attention" as const }
          : { labelKey: "tunnel.off" as const, tone: "outline" as const };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Cable className="size-4 text-muted-foreground" />
          <CardTitle>{t("eng.tunnel.title")}</CardTitle>
          <Badge variant={state.tone}>{t(state.labelKey)}</Badge>
          <InfoHint label={t("eng.tunnel.hintLabel")}>{t("eng.tunnel.hint")}</InfoHint>
        </div>
        <CardDescription>
          {external
            ? t("eng.tunnel.external", { host }) +
              (tunnel.configured ? "" : t("eng.tunnel.externalFill"))
            : tunnel.configured
              ? `${host} → ${tunnel.host}:${tunnel.remote_port}`
              : t("eng.tunnel.unconfigured")}
          {tunnel.autostart ? t("eng.tunnel.autostart") : ""}
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
                  onSuccess: () => toast({ title: t("eng.tunnel.stopped") }),
                })
              }
            >
              {tunnelStop.isPending ? <Spinner /> : <Unplug />}
              {t("eng.tunnel.disconnect")}
            </Button>
          ) : external ? null : (
            <Button
              disabled={!tunnel.configured || tunnelStart.isPending}
              onClick={() =>
                tunnelStart.mutate(undefined, {
                  onSuccess: (status) =>
                    toast({
                      title: status.running ? t("eng.tunnel.opened") : t("eng.tunnel.requested"),
                      description: status.running
                        ? t("eng.tunnel.sshRunning", { pid: status.pid ?? "—" })
                        : t("eng.tunnel.sshSoon"),
                    }),
                  onError: (error: Error) =>
                    toast({ title: t("eng.tunnel.openFailed"), description: error.message, tone: "danger" }),
                })
              }
            >
              {tunnelStart.isPending ? <Spinner /> : <PlugZap />}
              {t("eng.tunnel.connect")}
            </Button>
          )}
          <span className="text-small text-muted-foreground">
            {tunnel.running && tunnel.since
              ? t("eng.tunnel.since", {
                  elapsed: duration((Date.now() / 1000 - tunnel.since) * 1000),
                })
              : tunnel.attempts > 0
                ? plural("eng.tunnel.attempts", tunnel.attempts)
                : null}
            {tunnel.running
              ? available
                ? t("eng.tunnel.engineResponds")
                : t("eng.tunnel.engineSilent")
              : null}
            {external ? t("eng.tunnel.engineRespondsBare") : null}
          </span>
        </div>
        <FormError error={tunnelStart.error ?? tunnelStop.error} />
        {tunnel.last_error && !tunnel.running ? (
          <Alert tone="attention" title={t("eng.tunnel.lastError")}>
            <p className="font-mono text-small">{tunnel.last_error}</p>
          </Alert>
        ) : null}
        {tunnel.stderr.length > 0 ? (
          <details className="text-small text-muted-foreground">
            <summary className="cursor-pointer select-none">{t("eng.tunnel.sshSaid")}</summary>
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
  const { t, plural } = useT();
  const { release } = useEngineActions();
  const client = useQueryClient();
  const toast = useToast();
  const [slug, setSlug] = useState(overview.workspaces[0]?.slug ?? "");
  const warm = useMutation({
    mutationFn: (target: string) => api.adminWarmModels(target),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: keys.adminJobs });
      toast({ title: t("eng.gpu.warmQueued"), description: slug });
    },
  });
  const vram = engine.running.reduce((sum, m) => sum + (m.size_vram ?? 0), 0);
  const idleMinutes = Math.floor(engine.idle.seconds / 60);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Flame className="size-4 text-muted-foreground" />
          <CardTitle>{t("eng.gpu.title")}</CardTitle>
          <Badge variant={engine.available ? "settled" : "outline"}>
            {engine.available ? t("eng.gpu.online") : t("eng.gpu.offline")}
          </Badge>
        </div>
        <CardDescription>
          {engine.running.length > 0
            ? plural("eng.gpu.resident", engine.running.length, { size: bytes(vram) })
            : t("eng.gpu.nothingResident")}
          {engine.busy
            ? t("eng.gpu.working")
            : engine.idle.threshold > 0
              ? t("eng.gpu.idle", {
                  n: idleMinutes,
                  threshold: Math.floor(engine.idle.threshold / 60),
                })
              : t("eng.gpu.autoReleaseOff")}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {engine.running.length > 0 ? <Vram running={engine.running} total={vram} /> : null}
        <div className="flex flex-wrap items-end gap-2">
          <Button
            variant="outline"
            disabled={release.isPending || engine.running.length === 0 || engine.busy}
            title={
              engine.busy
                ? t("eng.gpu.jobRunning")
                : engine.running.length === 0
                  ? t("eng.gpu.nothingLoaded")
                  : t("eng.gpu.releaseHint")
            }
            onClick={() =>
              release.mutate(undefined, {
                onSuccess: ({ released }) =>
                  toast({
                    title: t("eng.gpu.released"),
                    description: plural("eng.gpu.releasedCount", released.length),
                  }),
                onError: (error: Error) =>
                  toast({
                    title: t("eng.gpu.releaseFailed"),
                    description: error.message,
                    tone: "danger",
                  }),
              })
            }
          >
            {release.isPending ? <Spinner /> : <Power />}
            {t("eng.gpu.release")}
          </Button>
          <div className="space-y-1">
            <Label htmlFor="warm-workspace">{t("eng.gpu.warmFor")}</Label>
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
            title={t("eng.gpu.warmHint")}
            onClick={() => warm.mutate(slug)}
          >
            {warm.isPending ? <Spinner /> : <Flame />}
            {t("eng.gpu.warm")}
          </Button>
        </div>
        <FormError error={release.error ?? warm.error} />
      </CardContent>
    </Card>
  );
}

/**
 * What the GPU is holding, as one bar plus its legend.
 *
 * IT IS A PROPORTION AND NOT A FRACTION, and that is the whole reason it has no «de 45 GB»:
 * `/api/ps` reports how much each resident model occupies and never how much the card has,
 * and `nvidia-smi` here answers about a different machine — the engine is reached through a
 * forwarded port. So the bar divides the resident total between the models and the total is
 * given in absolute terms. Inventing a denominator would make every percentage on it a
 * claim nothing measured.
 *
 * What it is worth seeing is the shape: the main model is two thirds of the residency and
 * the guardrail's context window was capped at 4096 precisely so the three of them fit at
 * once. That is legible in a bar and invisible in a list of three numbers.
 */
function Vram({ running, total }: { running: RunningModel[]; total: number }) {
  const { t, language } = useT();
  const shares = [...running].sort((a, b) => (b.size_vram ?? 0) - (a.size_vram ?? 0));
  const tint = ["bg-primary", "bg-primary/55", "bg-primary/30", "bg-primary/18"];

  return (
    <div className="space-y-2">
      {total > 0 ? (
        <div className="flex h-2.5 gap-0.5" role="img" aria-label={t("eng.vram.inUse", { size: bytes(total) })}>
          {shares.map((model, index) => (
            <span
              key={model.model}
              className={cn("h-full", tint[Math.min(index, tint.length - 1)])}
              style={{ width: `${((model.size_vram ?? 0) * 100) / total}%` }}
            />
          ))}
        </div>
      ) : null}
      <ul className="divide-y divide-border border border-border text-small">
        {shares.map((model, index) => (
          <li key={model.model} className="flex flex-wrap items-center gap-2 px-2 py-1.5">
            <span
              className={cn("size-2.5 shrink-0", tint[Math.min(index, tint.length - 1)])}
              aria-hidden="true"
            />
            <span className="font-mono">{model.model}</span>
            <span className="grow" />
            <span className="nums text-muted-foreground">
              {model.size_vram ? bytes(model.size_vram) : "—"}
              {model.context_length
                ? t("eng.vram.ctx", { n: model.context_length.toLocaleString(language) })
                : ""}
              {model.expires_at ? t("eng.vram.until", { when: when(model.expires_at) }) : ""}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-micro text-muted-foreground">
        {t("eng.vram.note")}
      </p>
    </div>
  );
}

/* Models on disk ------------------------------------------------------------------------- */

function ModelsCard({ engine }: { engine: AdminEngine }) {
  const { t, plural } = useT();
  const { pull, remove } = useEngineActions();
  const toast = useToast();
  const [name, setName] = useState("");
  const resident = new Set(engine.running.map((m) => m.model));
  const missing = engine.required.filter((r) => r.state === "not_installed");

  const confirmDelete = (model: string) => {
    if (!window.confirm(t("eng.models.confirmDelete", { model }))) return;
    remove.mutate(model, {
      onSuccess: () =>
        toast({ title: t("eng.models.deleted"), description: model, tone: "attention" }),
      onError: (error: Error) =>
        toast({ title: t("eng.models.deleteFailed"), description: error.message, tone: "danger" }),
    });
  };

  const startPull = (model: string) => {
    pull.mutate(model, {
      onSuccess: () => {
        setName("");
        toast({ title: t("eng.models.pullStarted"), description: model });
      },
      onError: (error: Error) =>
        toast({ title: t("eng.models.pullFailed"), description: error.message, tone: "danger" }),
    });
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <HardDrive className="size-4 text-muted-foreground" />
          <CardTitle>{t("eng.models.title")}</CardTitle>
          <InfoHint label={t("eng.models.hintLabel")}>{t("eng.models.hint")}</InfoHint>
        </div>
        <CardDescription>
          {plural("eng.models.onDisk", engine.installed.filter((m) => !m.remote).length)} ·{" "}
          {bytes(engine.installed.reduce((sum, m) => sum + (m.size ?? 0), 0))}
          {engine.installed.some((m) => m.remote)
            ? plural("eng.models.remoteCount", engine.installed.filter((m) => m.remote).length)
            : ""}
          {missing.length > 0 ? plural("eng.models.missingCount", missing.length) : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {missing.length > 0 ? (
          <Alert tone="attention" title={t("eng.models.missingTitle")}>
            <ul className="space-y-1">
              {missing.map((row) => (
                <li key={row.model} className="flex flex-wrap items-center gap-2">
                  <span className="font-mono">{row.model}</span>
                  <span className="text-muted-foreground">({row.asked_by.join(", ")})</span>
                  <Button size="sm" variant="outline" disabled={pull.isPending} onClick={() => startPull(row.model)}>
                    <Download />
                    {t("eng.models.pull")}
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
            <Label htmlFor="pull-model">{t("eng.models.pullLabel")}</Label>
            <Input
              id="pull-model"
              placeholder={t("eng.models.pullPlaceholder")}
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
            {t("eng.models.pull")}
          </Button>
        </div>
        <FormError error={pull.error ?? remove.error} />

        {engine.installed.length > 0 ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <Table minWidth="40rem">
              <THead>
                <TR>
                  <TH>{t("eng.models.col.model")}</TH>
                  <TH align="num">{t("eng.models.col.size")}</TH>
                  <TH>{t("eng.models.col.state")}</TH>
                  <TH>{t("eng.models.col.askedBy")}</TH>
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
                        {model.remote ? (
                          <Badge variant="outline">{t("eng.models.remote")}</Badge>
                        ) : resident.has(model.model) ? (
                          <Badge variant="settled">{t("eng.models.loaded")}</Badge>
                        ) : (
                          <Badge variant="outline">{t("eng.models.stored")}</Badge>
                        )}
                      </TD>
                      <TD className="px-3 py-2 text-small text-muted-foreground">
                        {asked ? model.asked_by.join(", ") : t("eng.models.nobody")}
                      </TD>
                      <TD align="num" className="px-3 py-2">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          disabled={Boolean(model.remote) || asked || remove.isPending || engine.busy}
                          title={
                            model.remote
                              ? t("eng.models.remoteDeleteHint")
                              : asked
                                ? t("eng.models.askedDeleteHint")
                                : engine.busy
                                  ? t("eng.gpu.jobRunning")
                                  : t("eng.models.deleteHint")
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
            {engine.available ? t("eng.models.empty") : t("eng.models.noEngine")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function PullRow({ pull }: { pull: PullStatus }) {
  const { t } = useT();
  const running = pull.status === "running";
  const tone = pull.status === "failed" ? "danger" : pull.status === "succeeded" ? "settled" : "primary";
  return (
    <li className="space-y-1 rounded-md border border-border p-2 text-small">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono">{pull.model}</span>
        <span className="nums text-muted-foreground">
          {running
            ? pull.total > 0
              ? t("eng.pull.progress", {
                  done: bytes(pull.completed),
                  total: bytes(pull.total),
                })
              : t("eng.pull.preparing")
            : pull.status === "succeeded"
              ? t("eng.pull.done")
              : t("eng.pull.failed")}
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
  const { t } = useT();
  const { invalidate, invalidateAll } = useEngineActions();
  const toast = useToast();
  const names = new Map(overview.workspaces.map((w) => [w.slug, w.name]));

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>{t("eng.ctx.title")}</CardTitle>
          <InfoHint label={t("eng.ctx.hintLabel")}>{t("eng.ctx.hint")}</InfoHint>
        </div>
        <CardDescription>
          {engine.contexts.length === 0
            ? t("eng.ctx.none")
            : t("eng.ctx.count", { n: engine.contexts.length })}
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
                  title={t("eng.ctx.invalidateOne")}
                  disabled={invalidate.isPending}
                  onClick={() =>
                    invalidate.mutate(slug, {
                      onSuccess: () =>
                        toast({ title: t("eng.ctx.invalidated"), description: slug }),
                      onError: (error: Error) =>
                        toast({ title: t("eng.ctx.failed"), description: error.message, tone: "danger" }),
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
                  toast({ title: t("eng.ctx.invalidatedAll"), description: `${invalidated}` }),
                onError: (error: Error) =>
                  toast({ title: t("eng.ctx.failed"), description: error.message, tone: "danger" }),
              })
            }
          >
            {t("eng.ctx.invalidateAll")}
          </Button>
        ) : null}
        <FormError error={invalidate.error ?? invalidateAll.error} />
      </CardContent>
    </Card>
  );
}

/* The database and the process ----------------------------------------------------------- */

function SystemCard() {
  const { t, language } = useT();
  const system = useAdminSystem();
  if (system.isLoading) return <Skeleton className="h-40" />;
  const data = system.data;
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Database className="size-4 text-muted-foreground" />
          <CardTitle>{t("eng.sys.title")}</CardTitle>
        </div>
        <CardDescription>
          {data ? (
            <>
              {data.database.location} · {t("eng.sys.schema")}{" "}
              <span className="font-mono">{data.database.revision ?? "—"}</span>
              {data.database.head && data.database.head !== data.database.revision ? (
                <Badge variant="attention" className="ml-2">
                  {t("eng.sys.pendingMigration", { head: data.database.head })}
                </Badge>
              ) : null}
            </>
          ) : (
            t("eng.sys.noDatabase")
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <FormError error={system.error} />
        {data ? (
          <>
            <p className="text-small text-muted-foreground">
              {t("eng.sys.uptime", { elapsed: duration(data.process.uptime_seconds * 1000) })}{" "}
              <span className="font-mono">{data.process.log_level}</span>
            </p>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-small sm:grid-cols-3">
              {Object.entries(data.database.tables).map(([table, count]) => (
                <div key={table} className="flex justify-between gap-2">
                  <dt className="font-mono text-muted-foreground">{table}</dt>
                  <dd className="nums">{count.toLocaleString(language)}</dd>
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
  const { t } = useT();
  const jobs = useAdminJobs();
  const cancel = useAdminCancelJob();
  const toast = useToast();

  const running = jobs.data?.running ?? null;
  const queued = jobs.data?.queued ?? [];
  const rows = [...(running ? [running] : []), ...queued];

  const confirmCancel = (job: Job) => {
    const verb = job.status === "running" ? t("eng.queue.stop") : t("eng.queue.remove");
    const message =
      t("eng.queue.confirm", {
        verb,
        label: job.label,
        workspace: job.workspace,
        by: job.user_name ? t("eng.queue.confirmBy", { name: job.user_name }) : "",
      }) + (job.status === "running" ? t("eng.queue.confirmRunning") : "");
    if (!window.confirm(message)) return;
    cancel.mutate(job.id, {
      onSuccess: () =>
        toast({
          title:
            job.status === "running" ? t("eng.queue.cancelRequested") : t("eng.queue.removed"),
          description: t("eng.queue.jobOf", { label: job.label, workspace: job.workspace }),
          tone: "attention",
        }),
      onError: (error: Error) =>
        toast({ title: t("eng.queue.cancelFailed"), description: error.message, tone: "danger" }),
    });
  };

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          {t("eng.queue.title", { n: rows.length })}
        </h2>
        <InfoHint label={t("eng.queue.hintLabel")}>{t("eng.queue.hint")}</InfoHint>
      </div>

      {jobs.isLoading ? (
        <Skeleton className="h-16" />
      ) : rows.length === 0 ? (
        <p className="text-small text-muted-foreground">{t("eng.queue.empty")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table minWidth="48rem">
            <THead>
              <TR>
                <TH align="num">#</TH>
                <TH>{t("eng.queue.col.job")}</TH>
                <TH>{t("eng.queue.col.workspace")}</TH>
                <TH>{t("eng.queue.col.askedBy")}</TH>
                <TH>{t("eng.queue.col.asked")}</TH>
                <TH>{t("eng.queue.col.state")}</TH>
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
                        {t(JOB_STATUS[job.status].labelKey)}
                      </span>
                    </TD>
                    <TD align="num" className="whitespace-nowrap px-3 py-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={cancel.isPending}
                        title={active ? t("eng.queue.stopHint") : t("eng.queue.remove")}
                        onClick={() => confirmCancel(job)}
                      >
                        {active ? <Ban /> : <Trash2 />}
                        {active ? t("eng.queue.stop") : t("eng.queue.removeShort")}
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
  const { t } = useT();
  const history = useAdminJobHistory();
  const jobs = history.data?.jobs ?? [];
  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          {t("eng.hist.title", { n: jobs.length })}
        </h2>
        <InfoHint label={t("eng.hist.hintLabel")}>{t("eng.hist.hint")}</InfoHint>
      </div>
      {history.isLoading ? (
        <Skeleton className="h-16" />
      ) : jobs.length === 0 ? (
        <p className="text-small text-muted-foreground">{t("eng.hist.empty")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table minWidth="48rem">
            <THead>
              <TR>
                <TH>{t("eng.queue.col.job")}</TH>
                <TH>{t("eng.queue.col.workspace")}</TH>
                <TH>{t("eng.queue.col.askedBy")}</TH>
                <TH>{t("eng.hist.col.finished")}</TH>
                <TH align="num">{t("eng.hist.col.elapsed")}</TH>
                <TH>{t("eng.queue.col.state")}</TH>
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
                      {t(JOB_STATUS[job.status].labelKey)}
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

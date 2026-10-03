import {
  Ban,
  Cable,
  Flame,
  HardDrive,
  ListOrdered,
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
import { Alert, LoadError, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { CerebrasCard } from "@/features/admin/CerebrasCard";
import { EngineBoard, panelId, tabId } from "@/features/admin/EngineBoard";
import { EngineChoice } from "@/features/admin/EngineChoice";
import {
  generalCell,
  HYBRID,
  localCell,
  remoteCell,
  tunnelState,
  type BoardCell,
  type ScreenKey,
} from "@/features/admin/engineState";
import {
  EngineSaveBar,
  SettingsPanel,
  useEngineSettings,
} from "@/features/admin/EngineSettings";
import { FormError } from "@/features/auth/AuthLayout";
import { bytes, duration, JOB_STATUS, when } from "@/lib/format";
import type {
  AdminEngine,
  AdminOverview,
  ConfigSetting,
  Job,
  RunningModel,
  TunnelStatus,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useAdminCancelJob,
  useAdminEngine,
  useAdminJobs,
  useEngineActions,
} from "@/state/queries";
import { useT } from "@/lib/i18n";
import { jobName } from "@/lib/names";

/**
 * The engine, one screen per part behind a board that reads them all.
 *
 * Everything here is global to the installation: which engine it runs, the queue, the port
 * forward that reaches the GPU, the contexts this process keeps warm, the one GPU and what
 * it holds, the models on its disk and the remote quota. None of it belongs to a workspace,
 * which is why it is gathered here.
 */
export function EngineTab({ overview }: { overview: AdminOverview }) {
  const { t } = useT();
  const engine = useAdminEngine();
  if (engine.isLoading) return <Skeleton className="h-96" />;
  if (!engine.data)
    return (
      <LoadError title={t("engine.unreadable")} error={engine.error} onRetry={engine.refetch} />
    );
  return <EngineScreens engine={engine.data} overview={overview} />;
}

function EngineScreens({ engine, overview }: { engine: AdminEngine; overview: AdminOverview }) {
  const tr = useT();
  const { t } = tr;
  const config = useEngineSettings();
  const jobs = useAdminJobs();

  // The engine decides how many parts the board has. The remote one is drawn from TWO
  // readings on purpose: its meters need the engine to be actually running Cerebras, its
  // settings only that somebody is ABOUT to. Reading the draft is what lets a person switch
  // engine on "General" and check the ceilings before saving.
  //
  // `cerebras` is read defensively: an older API does not send it, and a bare
  // `engine.cerebras.active` takes the WHOLE tab down with a blank screen. Missing means no
  // remote part, which is what the plain `ollama` engine means.
  const remote = engine.cerebras?.active ?? false;
  const engineName = String(
    ("engine.name" in config.draft ? config.draft["engine.name"] : config.stored.get("engine.name")) ??
      "ollama",
  );
  const paired = remote || engineName === HYBRID;

  // The draft is the tab's and not the screen's, so a change left behind on another part
  // has to be visible from this one: its cell counts it and the save bar follows it here.
  const pendingIn = (settings: ConfigSetting[]) =>
    settings.filter((setting) => setting.key in config.draft).length;
  const cells: BoardCell[] = [
    {
      ...generalCell(engine, jobs.data, tr),
      pending: pendingIn([...config.engine, ...config.tunnel]),
    },
    { ...localCell(engine, tr), pending: pendingIn(config.local) },
    ...(paired ? [{ ...remoteCell(engine, tr), pending: pendingIn(config.remote) }] : []),
  ];

  // The tab opens on the part that needs somebody, when one does, and on "General"
  // otherwise. Decided once: a part going wrong later changes its cell, never the screen
  // under a hand.
  const [chosen, setChosen] = useState<ScreenKey>(
    () => cells.find((cell) => cell.tone === "act" || cell.tone === "down")?.key ?? "general",
  );
  const active = cells.some((cell) => cell.key === chosen) ? chosen : "general";

  return (
    <div className="space-y-5">
      <EngineBoard cells={cells} value={active} onChange={setChosen} />

      <div
        role="tabpanel"
        id={panelId(active)}
        aria-labelledby={tabId(active)}
        className="min-w-0 space-y-4"
      >
        {/* What the installation runs on comes first and alone: it is the one choice here
            that changes every other screen of the tab, the remote one's existence included. */}
        {active === "general" ? (
          <>
            <EngineChoice config={config} />
            <div className="grid items-start gap-4 *:min-w-0 lg:grid-cols-[3fr_2fr]">
              <QueueSection />
              <div className="space-y-4">
                <TunnelCard tunnel={engine.tunnel} available={engine.available} host={engine.host} />
                <SettingsPanel
                  titleKey="eng.cfg.tunnel"
                  noteKey="eng.cfg.tunnelNote"
                  settings={config.tunnel}
                  config={config}
                />
                <ContextsCard engine={engine} overview={overview} />
              </div>
            </div>
          </>
        ) : null}

        {/* Inside these two the columns encode a DISTINCTION and not a width: the left one
            MEASURES and the right one SETS, so each setting sits beside what it governs. */}
        {active === "local" ? (
          <div className="grid items-start gap-4 *:min-w-0 lg:grid-cols-[3fr_2fr]">
            <div className="space-y-4">
              <ResidencyCard engine={engine} />
              <ModelsCard engine={engine} />
            </div>
            <SettingsPanel
              titleKey="eng.cfg.local"
              noteKey="eng.cfg.localNote"
              settings={config.local}
              config={config}
            />
          </div>
        ) : null}

        {active === "remote" ? (
          <div className="grid items-start gap-4 *:min-w-0 lg:grid-cols-[3fr_2fr]">
            {remote ? (
              <CerebrasCard cerebras={engine.cerebras!} />
            ) : (
              <p className="border border-dashed border-border p-4 text-small text-muted-foreground">
                {t("eng.remote.notYet")}
              </p>
            )}
            <SettingsPanel
              titleKey="eng.cfg.cerebras"
              noteKey="eng.cfg.cerebrasNote"
              settings={config.remote}
              config={config}
            />
          </div>
        ) : null}
      </div>

      <EngineSaveBar config={config} />
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

  const state = tunnelState(tunnel, available);
  const external = state.external;

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
            <pre className="mt-1 max-h-40 overflow-auto rounded bg-muted p-2 font-mono text-small">
              {tunnel.stderr.join("\n")}
            </pre>
          </details>
        ) : null}
      </CardContent>
    </Card>
  );
}

/* Residency ------------------------------------------------------------------------------ */

function ResidencyCard({ engine }: { engine: AdminEngine }) {
  const { t, plural } = useT();
  const { release } = useEngineActions();
  const toast = useToast();
  const vram = engine.running.reduce((sum, m) => sum + (m.size_vram ?? 0), 0);
  const resident = engine.running.length > 0;

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
        {resident ? null : (
          <CardDescription>
            {t("eng.gpu.nothingResident")}
            {engine.available ? t("eng.gpu.loadsOnDemand") : ""}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {resident ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <Vram running={engine.running} total={vram} />
              <IdleClock engine={engine} />
            </div>
            <Residents running={engine.running} />
          </>
        ) : null}
        <div className="flex flex-wrap items-end gap-2">
          <Button
            variant="outline"
            disabled={release.isPending || !resident || engine.busy}
            title={
              engine.busy
                ? t("eng.gpu.jobRunning")
                : resident
                  ? t("eng.gpu.releaseHint")
                  : t("eng.gpu.nothingLoaded")
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
        </div>
        <FormError error={release.error} />
      </CardContent>
    </Card>
  );
}

// One ink, four strengths: the residents are one thing shared out, not four entities, so
// the identity channel stays free and the bar and its legend agree by position.
const SHARE_TINT = ["bg-primary", "bg-primary/55", "bg-primary/30", "bg-primary/18"];

function byShare(running: RunningModel[]): RunningModel[] {
  return [...running].sort((a, b) => (b.size_vram ?? 0) - (a.size_vram ?? 0));
}

/**
 * What the GPU is holding, as a figure over one bar.
 *
 * IT IS A PROPORTION AND NOT A FRACTION, and that is the whole reason it has no "de 45 GB":
 * `/api/ps` reports how much each resident model occupies and never how much the card has,
 * and `nvidia-smi` here answers about a different machine — the engine is reached through a
 * forwarded port. So the bar divides the resident total between the models and the total is
 * given in absolute terms. Inventing a denominator would make every percentage on it a
 * claim nothing measured.
 *
 * What it is worth seeing is the shape: the main model is two thirds of the residency and
 * the guardrail's context window was capped at 4096 precisely so the three of them fit at
 * once. That is legible in a bar and invisible in a list of three numbers.
 *
 * It is set like the remote half's meters — a small label, the figure, the bar — because
 * the two answer the same question, what limits the work, at very different magnitudes.
 */
function Vram({ running, total }: { running: RunningModel[]; total: number }) {
  const { t, plural } = useT();
  return (
    <div className="space-y-1.5">
      <p className="flex items-center gap-1.5 text-micro font-condensed uppercase text-muted-foreground">
        {t("eng.vram.label")}
        <InfoHint label={t("eng.vram.noteLabel")}>{t("eng.vram.note")}</InfoHint>
      </p>
      <p className="nums text-title">
        {bytes(total)}{" "}
        <span className="text-small font-normal text-muted-foreground">
          {plural("eng.vram.residents", running.length)}
        </span>
      </p>
      {total > 0 ? (
        <div
          className="flex h-1.5 gap-0.5"
          role="img"
          aria-label={t("eng.vram.inUse", { size: bytes(total) })}
        >
          {byShare(running).map((model, index) => (
            <span
              key={model.model}
              className={cn("h-full", SHARE_TINT[Math.min(index, SHARE_TINT.length - 1)])}
              style={{ width: `${((model.size_vram ?? 0) * 100) / total}%` }}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

/**
 * How close the residents are to being unloaded for lack of work.
 *
 * Drawn only beside something resident: with the card empty the clock keeps counting and
 * has nothing to release, and "850 min sin trabajos (se libera a los 30)" was a sentence
 * about nothing. A running job stops the clock rather than resetting the figure to zero.
 */
function IdleClock({ engine }: { engine: AdminEngine }) {
  const { t } = useT();
  const threshold = Math.floor(engine.idle.threshold / 60);
  const idle = Math.min(Math.floor(engine.idle.seconds / 60), threshold);
  const counting = threshold > 0 && !engine.busy;

  return (
    <div className="space-y-1.5">
      <p className="text-micro font-condensed uppercase text-muted-foreground">
        {t("eng.idle.label")}
      </p>
      <p className="nums text-title">
        {counting ? idle : "—"}{" "}
        <span className="text-small font-normal text-muted-foreground">
          {threshold <= 0
            ? t("eng.idle.off")
            : engine.busy
              ? t("eng.idle.busy")
              : t("eng.idle.of", { threshold })}
        </span>
      </p>
      <Progress value={counting ? idle : 0} max={threshold > 0 ? threshold : 1} tone="settled" />
    </div>
  );
}

function Residents({ running }: { running: RunningModel[] }) {
  const { t, language } = useT();
  return (
    <ul className="divide-y divide-border border border-border text-small">
      {byShare(running).map((model, index) => (
        <li key={model.model} className="flex flex-wrap items-center gap-2 px-2 py-1.5">
          <span
            className={cn("size-2.5 shrink-0", SHARE_TINT[Math.min(index, SHARE_TINT.length - 1)])}
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
  );
}

/* Models on disk ------------------------------------------------------------------------- */

/**
 * What Ollama holds on the GPU machine's disk, and nothing else.
 *
 * A model Cerebras serves is not on this disk and has no row here: the engine lists it so a
 * phase can name it, and that listing belongs to the remote screen. Nothing is downloaded
 * from here either — a build pulls what it lacks before its first phase, so the panel only
 * says what is missing and lets a model nobody names be deleted.
 */
function ModelsCard({ engine }: { engine: AdminEngine }) {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const { remove } = useEngineActions();
  const toast = useToast();
  const onDisk = engine.installed.filter((model) => !model.remote);
  const resident = new Set(engine.running.map((m) => m.model));
  const missing = engine.required.filter((r) => r.state === "not_installed");

  const confirmDelete = async (model: string) => {
    if (!(await confirm({ title: t("eng.models.confirmDelete", { model }), tone: "danger" })))
      return;
    remove.mutate(model, {
      onSuccess: () =>
        toast({ title: t("eng.models.deleted"), description: model, tone: "attention" }),
      onError: (error: Error) =>
        toast({ title: t("eng.models.deleteFailed"), description: error.message, tone: "danger" }),
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
          {onDisk.length > 0
            ? `${plural("eng.models.onDisk", onDisk.length)} · ${bytes(
                onDisk.reduce((sum, m) => sum + (m.size ?? 0), 0),
              )}`
            : engine.available
              ? t("eng.models.empty")
              : t("eng.models.noEngine")}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {missing.length > 0 ? (
          <Alert tone="attention" title={t("eng.models.missingTitle")}>
            <ul className="space-y-1">
              {missing.map((row) => (
                <li key={row.model} className="flex flex-wrap items-baseline gap-2">
                  <span className="font-mono">{row.model}</span>
                  <span className="text-muted-foreground">({row.asked_by.join(", ")})</span>
                </li>
              ))}
            </ul>
            <p>{t("eng.models.missingNote")}</p>
          </Alert>
        ) : null}
        <FormError error={remove.error} />

        {onDisk.length > 0 ? (
          <div className="overflow-hidden border border-border">
            <Table minWidth="32rem">
              <THead>
                <TR>
                  <TH>{t("eng.models.col.model")}</TH>
                  <TH align="num">{t("eng.models.col.size")}</TH>
                  <TH>{t("eng.models.col.state")}</TH>
                  <TH />
                </TR>
              </THead>
              <TBody>
                {onDisk.map((model) => {
                  // Read only for the delete guard: a model some setting names cannot be
                  // removed. WHICH setting names it is read in "Configuración", where it
                  // can also be changed.
                  const asked = model.asked_by.length > 0;
                  return (
                    <TR key={model.model}>
                      <TD className="px-3 py-2 font-mono text-small">{model.model}</TD>
                      <TD align="num" className="px-3 py-2 nums text-small">
                        {model.size ? bytes(model.size) : "—"}
                      </TD>
                      <TD className="px-3 py-2">
                        {resident.has(model.model) ? (
                          <Badge variant="settled">{t("eng.models.loaded")}</Badge>
                        ) : (
                          <Badge variant="outline">{t("eng.models.stored")}</Badge>
                        )}
                      </TD>
                      <TD align="num" className="px-3 py-2">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          disabled={asked || remove.isPending || engine.busy}
                          aria-label={t("eng.models.deleteOne", { model: model.model })}
                          title={
                            asked
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
        ) : null}
      </CardContent>
    </Card>
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
  const confirm = useConfirm();
  const jobs = useAdminJobs();
  const cancel = useAdminCancelJob();
  const toast = useToast();

  const running = jobs.data?.running ?? null;
  const queued = jobs.data?.queued ?? [];
  const rows = [...(running ? [running] : []), ...queued];

  const confirmCancel = async (job: Job) => {
    const verb = job.status === "running" ? t("eng.queue.stop") : t("eng.queue.remove");
    const message =
      t("eng.queue.confirm", {
        verb,
        label: jobName(job.kind, t, job.label),
        workspace: job.workspace,
        by: job.user_name ? t("eng.queue.confirmBy", { name: job.user_name }) : "",
      }) + (job.status === "running" ? t("eng.queue.confirmRunning") : "");
    if (!(await confirm({ title: message, tone: "danger" }))) return;
    cancel.mutate(job.id, {
      onSuccess: () =>
        toast({
          title:
            job.status === "running" ? t("eng.queue.cancelRequested") : t("eng.queue.removed"),
          description: t("eng.queue.jobOf", { label: jobName(job.kind, t, job.label), workspace: job.workspace }),
          tone: "attention",
        }),
      onError: (error: Error) =>
        toast({ title: t("eng.queue.cancelFailed"), description: error.message, tone: "danger" }),
    });
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <ListOrdered className="size-4 text-muted-foreground" />
          <CardTitle>{t("eng.queue.title", { n: rows.length })}</CardTitle>
          <InfoHint label={t("eng.queue.hintLabel")}>{t("eng.queue.hint")}</InfoHint>
        </div>
        {jobs.isLoading || rows.length > 0 ? null : (
          <CardDescription>{t("eng.queue.empty")}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {jobs.isLoading ? (
          <Skeleton className="h-16" />
        ) : rows.length === 0 ? null : (
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
                      <TD className="px-3 py-2">{jobName(job.kind, t, job.label)}</TD>
                      <TD className="px-3 py-2 font-mono text-small">{job.workspace}</TD>
                      <TD className="px-3 py-2 text-small">{job.user_name ?? "—"}</TD>
                      <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
                        {when(new Date(job.created_at * 1000).toISOString())}
                      </TD>
                      <TD className="whitespace-nowrap px-3 py-2">
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
      </CardContent>
    </Card>
  );
}

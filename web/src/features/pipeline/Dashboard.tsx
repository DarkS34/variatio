import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  Ban,
  CircleAlert,
  CircleCheck,
  Cpu,
  Hourglass,
  Lock,
  Pencil,
  Server,
  WifiOff,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { BuildButton } from "@/components/BuildButton";
import { BuildProgress } from "@/components/BuildProgress";
import { useActiveRun } from "@/components/RunDrawer";
import { StageBadge } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Alert, PhaseBar, Progress, Separator, Skeleton, Spinner } from "@/components/ui/misc";
import { RawSection } from "@/features/raw/RawSection";
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
  useStream,
} from "@/state/queries";
import { useT, type Key } from "@/lib/i18n";

const SCREEN: Record<string, string> = {
  exemplars_profile: "/preparar/perfil",
  knowledge_graph: "/preparar/grafo",
  exemplars_bank: "/preparar/banco",
};

const EXPLAIN: Record<string, Key> = {
  exemplars_profile: "dash.explain.profile",
  knowledge_graph: "dash.explain.graph",
  exemplars_bank: "dash.explain.bank",
};

function StageCard({ stage }: { stage: StageState }) {
  const { t } = useT();
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
            <InfoHint label={t("stage.whatIs", { title: stage.label })}>
              {t(EXPLAIN[stage.artifact])}
            </InfoHint>
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
          <p className="text-small text-muted-foreground">
            {t("dash.approvedOn", { when: when(stage.approved_at) })}
          </p>
        ) : null}

        {building && !queued ? <BuildProgress artifact={stage.artifact} /> : null}

        <div className="flex flex-wrap gap-2 pt-1">
          {/* While building there is nothing to review: the artifact's screen hides the existing one
              until it finishes, and this card already shows the progress. */}
          {missing || building ? null : (
            <Link to={SCREEN[stage.artifact]}>
              <Button size="sm" variant={stage.status === "approved" ? "outline" : "default"} disabled={blocked}>
                <Pencil />
                {stage.status === "approved" ? t("dash.reviewAgain") : t("dash.review")}
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
  const { t, plural } = useT();
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
        <span className="text-muted-foreground">{t("dash.modelsLoaded")}</span>
        <button
          type="button"
          onClick={() => setOpen(true)}
          title={t("dash.modelsHint")}
          className="rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {models.missing.length > 0 ? (
            <Badge variant="danger" className="cursor-pointer hover:opacity-85">
              {plural("dash.modelsMissing", models.missing.length)}
            </Badge>
          ) : resident.length === 0 ? (
            <Badge variant="outline" className="cursor-pointer hover:opacity-85">
              {t("dash.noneResident")}
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
        title={t("dash.modelsTitle")}
        description={t("dash.modelsDescription")}
        className="max-w-2xl"
      >
        <div className="space-y-4">
          <section className="space-y-2">
            <h3 className="text-micro font-condensed uppercase text-muted-foreground">
              {t("dash.inMemoryNow", { n: resident.length })}
            </h3>
            {resident.length === 0 ? (
              <p className="text-body text-muted-foreground">
                {t("dash.noModelLoaded")}
              </p>
            ) : (
              <ul className="space-y-2">
                {resident.map((entry) => (
                  <li key={entry.model} className="rounded-lg border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <code className="font-mono text-body">{entry.model}</code>
                      <span className="ml-auto text-micro nums text-muted-foreground">
                        {entry.size_vram
                          ? t("dash.inVram", { size: bytes(entry.size_vram) })
                          : t("dash.noVram")}
                      </span>
                    </div>
                    <p className="mt-1 flex flex-wrap gap-x-3 text-small text-muted-foreground">
                      {entry.context_length ? (
                        <span className="nums">
                          {t("dash.context", { n: entry.context_length.toLocaleString() })}
                        </span>
                      ) : null}
                      {entry.expires_at ? (
                        <span>{t("dash.residentUntil", { when: when(entry.expires_at) })}</span>
                      ) : null}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            {vram > 0 ? (
              <p className="text-small nums text-muted-foreground">
                {t("dash.vramTotal", { size: bytes(vram) })}
              </p>
            ) : null}
          </section>

          <section className="space-y-2 border-t border-border pt-3">
            <h3 className="text-micro font-condensed uppercase text-muted-foreground">
              {t("dash.requiredBy", { n: required.length })}
            </h3>
            <ul className="space-y-2">
              {required.map(({ model, settings, missing, remote, loaded }) => (
                <li key={model} className="rounded-lg border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-mono text-body">{model}</code>
                    {remote ? (
                      <Badge variant="outline">{t("model.remote")}</Badge>
                    ) : missing ? (
                      <Badge variant="danger">{t("model.notInstalled")}</Badge>
                    ) : loaded ? (
                      <Badge variant="settled">{t("model.loaded")}</Badge>
                    ) : (
                      <Badge variant="outline">{t("model.onDisk")}</Badge>
                    )}
                    <span className="ml-auto text-micro nums text-muted-foreground">
                      {plural("dash.phases", settings.length)}
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
 * What is running, under the machine that runs it.
 *
 * It speaks of *any* job, not of the mode that launched it: building, indexing, tagging,
 * generating and evaluating come out of the same stream and read the same. The step by step
 * stays in the run drawer; this only answers «what is running, how long has it been, and can
 * I stop it».
 *
 * Idle, that is one line — which is the whole reason it stopped being a card of its own. A
 * heading, a border and an (i) around «Nada en ejecución» is a box built for the exception,
 * and the exception brings its own bar, its own numbers and its own cancel button when it
 * arrives.
 */
function ActivityBlock() {
  const { t, plural } = useT();
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
    <div className="space-y-3">
      <div className="flex items-center gap-1.5">
        <Activity className="size-3.5 shrink-0 text-muted-foreground" />
        <span className="text-micro font-condensed uppercase text-muted-foreground">
          {t("dash.activity")}
        </span>
        <InfoHint label={t("dash.whatIsHere")}>{t("dash.activityBody")}</InfoHint>
      </div>

      {stream.connected ? null : (
        <p className="flex items-center gap-1.5 text-small text-attention">
          <WifiOff className="size-3.5 shrink-0" />
          {t("dash.disconnected")}
        </p>
      )}

      {!run?.job ? (
        // «Nada en ejecución» would be a lie when the one GPU is busy with another
        // workspace: your own screen is idle and the next job you launch will wait,
        // and nothing else on the page would say why.
        pipeline.data?.engine_busy_elsewhere ? (
          <p className="flex items-start gap-1.5 text-small text-muted-foreground">
            <Hourglass className="mt-0.5 size-3.5 shrink-0" />
            {t("dash.busyElsewhere")}
          </p>
        ) : (
          <p className="text-muted-foreground">{t("dash.nothingRunning")}</p>
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
            {explain ? t(explain.what) : t("run.working")}
          </p>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-small">
            <span className={cn("font-medium", JOB_STATUS[status!]?.tone)}>
              {JOB_STATUS[status!] ? t(JOB_STATUS[status!].labelKey) : status}
            </span>
            <span className="flex items-center gap-1 nums text-muted-foreground">
              <Hourglass className="size-3" />
              {duration(active ? elapsed : run.job.elapsed_ms)}
            </span>
            {status === "queued" && ahead !== null ? (
              <span className="text-muted-foreground">
                {ahead === 0 ? t("dash.nextToStart") : plural("dash.jobsAhead", ahead)}
              </span>
            ) : queued > 0 ? (
              <span className="text-muted-foreground">{t("dash.inQueue", { n: queued })}</span>
            ) : null}
          </div>

          {/* With no overall percentage the bar is indeterminate on purpose: a step can be at 8/8
              and still have half a run ahead. */}
          {active ? (
            <div className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 truncate text-small">
                  {overall?.label ?? step?.label ?? t("progress.preparing")}
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
                <PhaseBar phases={phases} percent={overall.percent} activeKey={overall.key} />
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
              {t("common.cancel")}
            </Button>
          ) : null}
        </>
      )}
    </div>
  );
}

/**
 * ONE CARD FOR THE MACHINE AND FOR WHAT IT IS DOING WITH IT.
 *
 * «Sistema» and «Actividad» were two cards asking one question — is the thing that does the
 * work available, and is it working — and the split cost a heading, a border and an (i) to
 * say «Nada en ejecución», which is what the panel says most of the time. Together they are
 * four lines at rest and one card with a bar while a job runs.
 */
function MachineCard() {
  const { t } = useT();
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

  if (health.isLoading) return <Skeleton className="h-56" />;
  if (!health.data) {
    return (
      <Alert tone="danger" title={t("dash.noServer")}>
        <p>{t("dash.noServerBody")}</p>
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
          {t("dash.system")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-body">
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">{t("dash.engine")}</span>
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
              <span className="text-small text-destructive">{t("dash.offline")}</span>
            )}
          </span>
        </div>

        <ModelsRow models={models} />

        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            {t("dash.modelsInMemory")}
            <InfoHint label={t("dash.warmHint")}>{t("dash.warmBody")}</InfoHint>
          </span>
          {cold.length === 0 ? (
            <Badge variant="settled">{t("dash.warm")}</Badge>
          ) : (
            <div className="flex items-center gap-2">
              <Badge variant="outline">
                {cold.length === wanted.length ? t("dash.cold") : t("dash.someCold", { n: cold.length })}
              </Badge>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => warm.mutate()}
                disabled={warm.isPending || warming || !available}
              >
                {warm.isPending || warming ? <Spinner /> : <Cpu />}
                {t("dash.warmUp")}
              </Button>
            </div>
          )}
        </div>

        <Separator />

        <ActivityBlock />
      </CardContent>
    </Card>
  );
}

export function Dashboard() {
  const { t } = useT();
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
        <h1 className="font-display font-expanded text-display">{t("nav.dashboard")}</h1>
        <InfoHint label={t("dash.howTheChainWorks")}>
          {t("dash.chainBody")}
        </InfoHint>
      </header>

      {/* THE ONE BLUE THING ON THE SCREEN. `--attention` means «act here», and the frontier
          is exactly what this sentence names: the first stage of the chain that is not
          resolved yet. Everything else on the panel reports, and reports achromatically. */}
      {next ? (
        <Alert
          tone="attention"
          title={t("dash.nextStep", { label: next.label })}
          action={
            <Button size="sm" variant="attention" onClick={() => navigate(SCREEN[next.artifact])}>
              {t("dash.go")}
              <ArrowRight />
            </Button>
          }
        >
          <p>
            {next.blocked_reason ??
              (next.status === "missing"
                ? t("dash.notBuiltYet")
                : t("dash.notApproved"))}
          </p>
        </Alert>
      ) : (
        <Alert
          tone="settled"
          title={t("dash.chainApproved")}
          action={
            <Button size="sm" onClick={() => navigate("/generar")}>
              {t("nav.generate")}
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
        {/* «Sistema» opens the column: it is what gets checked at a glance — whether the
            engine answers, what it has loaded, what it is doing — and the subject sits
            under it, which is read once and edited rarely. */}
        <div className="space-y-4">
          <MachineCard />
          <ContextCard />
        </div>
      </div>

      {/* Last, and that is the reading order the chain deserves. The raw material is what
          you touch once at the start and then hardly ever, so opening the panel with it —
          expanded, because a slot was empty, which is the state every new workspace starts
          in — spent the top of the screen on the first ten minutes of an instance's life.
          An empty origin still announces itself: its row opens by itself, and the alert
          above already says the stage it feeds cannot be built. */}
      <RawSection />
    </div>
  );
}

import { Activity, ArrowRight, Hourglass, Lock, Pencil, WifiOff } from "lucide-react";
import { useMemo } from "react";

import { BuildButton } from "@/components/BuildButton";
import { GuideLink } from "@/components/GuideLink";
import { BuildProgress } from "@/components/BuildProgress";
import { useActiveRun } from "@/components/RunDrawer";
import { StageBadge } from "@/components/StageGate";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Alert, PhaseBar, Progress, Skeleton } from "@/components/ui/misc";
import { JOB_EXPLAIN } from "@/lib/explain";
import { JOB_STATUS, duration, when } from "@/lib/format";
import { isQueued } from "@/lib/queue";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";

import { useTranscriptionSummary } from "@/features/raw/queries";

import { ContextCard } from "./ContextCard";
import {
  useArtifactRun,
  useBuildPhases,
  useElapsed,
  usePipeline,
  useRaw,
  useStream,
} from "@/state/queries";
import { useT, type Key } from "@/lib/i18n";
import { artifactName, jobName, phaseName, phasePlan, stepName } from "@/lib/names";
import { CancelButton } from "@/components/CancelButton";

const SCREEN: Record<string, string> = {
  exemplars_profile: "/prepare/profile",
  knowledge_graph: "/prepare/graph",
  exemplars_bank: "/prepare/bank",
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
            <CardTitle>{artifactName(stage.artifact, t, stage.label)}</CardTitle>
            <InfoHint label={t("stage.whatIs", { title: artifactName(stage.artifact, t, stage.label) })}>
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

        {/* Compact: the panel already draws this run whole in `ActivityCard`, with its
            own stop button, and the drawer holds the step timeline. */}
        {building && !queued ? <BuildProgress artifact={stage.artifact} compact /> : null}

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

/**
 * WHAT IS RUNNING. Not what it is running ON.
 *
 * It speaks of *any* job, not of the mode that launched it: building, indexing, tagging,
 * transcribing, generating and evaluating come out of the same stream and read the same.
 * The step by step stays in the run drawer; this only answers «what is running, how long
 * has it been, and can I stop it».
 *
 * It shared a card with «Sistema» until now — the engine, the resident models, their VRAM
 * and a warm-up button. That block is GONE from the panel, and not merely folded: every
 * line of it is a property of the installation rather than of this instance, and all of it
 * is already in «Administración → Motor», where it is drawn against the quota and the
 * tunnel that give it meaning. What the panel actually needed from it survives in two
 * places that cost no card at all — the header's own strip already says when the engine
 * does not answer or a model is missing, which is the only reading anybody acted on.
 */
function ActivityCard() {
  const { t, plural } = useT();
  const run = useActiveRun();
  const stream = useStream();
  const pipeline = usePipeline();

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
          <Activity className="size-4 shrink-0 text-muted-foreground" />
          {t("dash.activity")}
          <InfoHint label={t("dash.whatIsHere")}>{t("dash.activityBody")}</InfoHint>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-body">
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
            <span className="font-medium">{jobName(run.job.kind, t, run.job.label)}</span>
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
                  {/* The running phase, or the running step when there is no plan: both
                      arrive with the API's own sentence, and a phase key only means
                      something inside the plan it belongs to. */}
                  {(overall?.label
                    ? phaseName(phasePlan(run?.job), overall.key, t, overall.label)
                    : null) ??
                    (step ? stepName(step.id, t, step.label) : null) ??
                    t("progress.preparing")}
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

          {active ? <CancelButton run={run} className="w-full" /> : null}
        </>
      )}
      </CardContent>
    </Card>
  );
}

export function Dashboard() {
  const { t, plural } = useT();
  const pipeline = usePipeline();
  const raw = useRaw();
  const summary = useTranscriptionSummary(raw.data?.slots ?? []);
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
      <header className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-display font-expanded text-display">{t("nav.dashboard")}</h1>
          <InfoHint label={t("dash.howTheChainWorks")}>
            {t("dash.chainBody")}
          </InfoHint>
        </div>
        <GuideLink slug="start" />
      </header>

      {/* THE ONE BLUE THING ON THE SCREEN. `--attention` means «act here», and the frontier
          is exactly what this sentence names: the first thing between here and a generated
          item. Everything else on the panel reports, and reports achromatically.

          THE RAW MATERIAL COMES FIRST, and that is a claim about order rather than about
          permission. An empty origin means a stage that cannot be built at all; documents
          that are not transcribed yet mean three builds that will each stop to transcribe
          them. Neither is a gate — every builder keeps its own conversion phase and the
          stage cards below stay pressable throughout — but both are what a person should
          do before spending an hour on a build. Once the material is in and read, the
          sentence goes back to naming the first unapproved stage. */}
      {raw.data && summary.empty ? (
        <Alert
          tone="attention"
          title={t("dash.next.import")}
          action={
            <Button size="sm" variant="attention" onClick={() => navigate("/raw")}>
              {t("dash.goRaw")}
              <ArrowRight />
            </Button>
          }
        >
          <p>{t("dash.next.importBody")}</p>
        </Alert>
      ) : summary.todo > 0 ? (
        <Alert
          tone="attention"
          title={plural("dash.next.transcribe", summary.todo)}
          action={
            <Button size="sm" variant="attention" onClick={() => navigate("/raw")}>
              {t("dash.goRaw")}
              <ArrowRight />
            </Button>
          }
        >
          <p>{t("dash.next.transcribeBody")}</p>
        </Alert>
      ) : next ? (
        <Alert
          tone="attention"
          title={t("dash.nextStep", { label: artifactName(next.artifact, t, next.label) })}
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
            <Button size="sm" onClick={() => navigate("/generate")}>
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
        {/* What is happening, and what it is about. «Sistema» used to open this column
            and it has left the panel entirely — see `ActivityCard`. The raw material left
            too, for a destination of its own: it is the one part of an instance that is
            neither watched nor approved here, and folded into the last card of the panel
            it could only ever be a disclosure inside a disclosure. */}
        <div className="space-y-4">
          <ActivityCard />
          <ContextCard />
        </div>
      </div>
    </div>
  );
}

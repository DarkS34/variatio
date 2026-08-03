import {
  Activity,
  AlertTriangle,
  Ban,
  CircleCheck,
  FileJson,
  Library,
  Network,
  Play,
  Share2,
  WifiOff,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { RunDrawer, useActiveRun } from "@/components/RunDrawer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/misc";
import { duration } from "@/lib/format";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCancelJob, useHealth, usePipeline, useStream } from "@/state/queries";
import { runStore } from "@/state/runStore";

const NAV = [
  { path: "/", label: "Panel", icon: Activity, artifact: null },
  { path: "/preparar/perfil", label: "Perfil", icon: FileJson, artifact: "content_profile" },
  { path: "/preparar/grafo", label: "Grafo", icon: Network, artifact: "knowledge_graph" },
  { path: "/preparar/banco", label: "Banco", icon: Library, artifact: "exemplars_bank" },
  { path: "/generar", label: "Generar", icon: Play, artifact: null },
] as const;

function useElapsed(startedAt: number | null | undefined, live: boolean) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [live]);
  if (!startedAt) return null;
  return Math.max(0, (now - startedAt) * 1000);
}

/** Level 1 of "what is happening": one glance, from any screen. */
function JobIndicator({ onOpen }: { onOpen: () => void }) {
  const run = useActiveRun();
  const stream = useStream();
  const cancel = useCancelJob();

  const running = run?.job?.status === "running" || run?.job?.status === "queued";
  const elapsed = useElapsed(run?.job?.started_at ?? null, Boolean(running));
  const step = useMemo(() => run?.steps.filter((s) => s.status === "running").at(-1), [run]);

  if (!run || !run.job) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {stream.connected ? (
          <>
            <span className="size-1.5 rounded-full bg-[var(--success)]" />
            En reposo
          </>
        ) : (
          <>
            <WifiOff className="size-3.5" />
            Sin conexión con el servidor
          </>
        )}
      </div>
    );
  }

  if (!running) {
    const tone = run.job.status === "failed" ? "danger" : run.job.status === "cancelled" ? "outline" : "success";
    return (
      <button onClick={onOpen} className="flex items-center gap-2 text-xs" title="Ver la última ejecución">
        <Badge variant={tone as never}>
          {run.job.status === "failed" ? <AlertTriangle /> : <CircleCheck />}
          {run.job.label}
        </Badge>
        <span className="tabular-nums text-muted-foreground">{duration(run.job.elapsed_ms)}</span>
      </button>
    );
  }

  return (
    <div className="flex min-w-0 items-center gap-3">
      <button onClick={onOpen} className="flex min-w-0 items-center gap-2 text-left">
        <span className="relative flex size-2 shrink-0">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-[var(--info)] opacity-60" />
          <span className="relative inline-flex size-2 rounded-full bg-[var(--info)]" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">{step?.label ?? run.job.label}</p>
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            {step?.total ? (
              <span className="tabular-nums">
                {step.current ?? 0}/{step.total}
              </span>
            ) : null}
            <span className="tabular-nums">{duration(elapsed)}</span>
            {stream.connected ? null : <span className="text-[var(--warning)]">reconectando…</span>}
          </div>
        </div>
      </button>
      {step?.total ? (
        <Progress value={step.current ?? 0} max={step.total} className="hidden w-28 md:block" />
      ) : null}
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Cancelar"
        title="Cancelar la ejecución"
        onClick={() => cancel.mutate(run.job!.id)}
      >
        <Ban />
      </Button>
    </div>
  );
}

function NavItem({
  path,
  label,
  icon: Icon,
  stage,
  active,
}: {
  path: string;
  label: string;
  icon: typeof Activity;
  stage?: StageState;
  active: boolean;
}) {
  const locked = Boolean(stage?.blocked_reason);
  return (
    <Link
      to={path}
      className={cn(
        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
        active ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <Icon className="size-4" />
      {label}
      {stage ? <StageDot status={stage.status} locked={locked} /> : null}
    </Link>
  );
}

function StageDot({ status, locked }: { status: StageState["status"]; locked: boolean }) {
  const colour = locked
    ? "bg-muted-foreground/40"
    : {
        approved: "bg-[var(--success)]",
        draft: "bg-[var(--warning)]",
        stale: "bg-destructive",
        building: "bg-[var(--info)] animate-pulse-soft",
        missing: "bg-muted-foreground/40",
      }[status];
  return <span className={cn("size-1.5 rounded-full", colour)} />;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { path } = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const pipeline = usePipeline();
  const health = useHealth();
  const stream = useStream();

  useEffect(() => {
    runStore.connect();
  }, []);

  // The pipeline is derived from files on disk; a job that finishes changes it.
  useEffect(() => {
    if (stream.currentJobId === null) pipeline.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.currentJobId]);

  const stages = pipeline.data?.stages ?? [];
  const stageFor = (artifact: string | null) => stages.find((s) => s.artifact === artifact);

  const offline = health.data && !health.data.available;
  const missingModels = health.data?.models.missing ?? [];

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-4 px-4">
          <Link to="/" className="flex shrink-0 items-center gap-2 font-semibold">
            <Share2 className="size-5 text-primary" />
            <span className="hidden sm:inline">Generador de variantes</span>
          </Link>

          <nav className="flex items-center gap-0.5">
            {NAV.map((item) => (
              <NavItem
                key={item.path}
                path={item.path}
                label={item.label}
                icon={item.icon}
                stage={stageFor(item.artifact)}
                active={path === item.path}
              />
            ))}
          </nav>

          <div className="ml-auto flex min-w-0 items-center gap-4">
            <JobIndicator onOpen={() => setDrawerOpen(true)} />
          </div>
        </div>

        {offline || missingModels.length > 0 ? (
          <div className="border-t border-border bg-[color-mix(in_oklch,var(--warning)_12%,transparent)] px-4 py-1.5 text-xs">
            {offline ? (
              <span>
                No hay conexión con Ollama en <code className="font-mono">{health.data?.host}</code>.
                Los trabajos fallarán hasta que arranque.
              </span>
            ) : (
              <span>
                Modelos no instalados: <code className="font-mono">{missingModels.join(", ")}</code>.
                Un trabajo que los use fallará.
              </span>
            )}
          </div>
        ) : null}
      </header>

      <main
        className={cn(
          "mx-auto w-full max-w-[1600px] flex-1 px-4 py-6",
          drawerOpen && "pb-[56vh]",
        )}
      >
        {children}
      </main>

      <RunDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />

      {!drawerOpen ? (
        <button
          onClick={() => setDrawerOpen(true)}
          className="fixed bottom-4 right-4 z-30 flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-xs font-medium shadow-lg transition-transform hover:-translate-y-0.5"
        >
          <Activity className="size-4" />
          Ver ejecución
        </button>
      ) : null}
    </div>
  );
}

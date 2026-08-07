import {
  Activity,
  AlertTriangle,
  Ban,
  CircleCheck,
  FileJson,
  Library,
  Network,
  Play,
  ScrollText,
  Share2,
  WifiOff,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";


import { RunDrawer, useActiveRun, type DrawerTab } from "@/components/RunDrawer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Progress } from "@/components/ui/misc";
import { duration } from "@/lib/format";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useCancelJob,
  useElapsed,
  useHealth,
  useInvalidateChain,
  usePipeline,
  useStream,
} from "@/state/queries";
import { runStore } from "@/state/runStore";

const NAV = [
  { path: "/", label: "Panel", icon: Activity, artifact: null },
  { path: "/preparar/perfil", label: "Perfil", icon: FileJson, artifact: "content_profile" },
  { path: "/preparar/grafo", label: "Grafo", icon: Network, artifact: "knowledge_graph" },
  { path: "/preparar/banco", label: "Banco", icon: Library, artifact: "exemplars_bank" },
  { path: "/generar", label: "Generar", icon: Play, artifact: null },
] as const;

/**
 * What is still pending, in one line — nothing else.
 *
 * The detail of a run lives in the drawer; up here the only questions worth answering
 * are "is something missing?" and "can I generate yet?". Anything more turns the header
 * into a second log.
 */
function Readiness() {
  const pipeline = usePipeline();
  const stages = pipeline.data?.stages ?? [];
  if (stages.length === 0) return null;

  const missing = stages.filter((stage) => stage.status === "missing");
  const stale = stages.filter((stage) => stage.status === "stale");
  const draft = stages.filter((stage) => stage.status === "draft");

  const [tone, text] =
    missing.length > 0
      ? (["bg-muted-foreground/50", `Falta construir: ${missing.map((s) => s.label).join(", ")}`] as const)
      : stale.length > 0
        ? (["bg-destructive", `Obsoleto: ${stale.map((s) => s.label).join(", ")}`] as const)
        : draft.length > 0
          ? (["bg-[var(--warning)]", `Pendiente de aprobar: ${draft.map((s) => s.label).join(", ")}`] as const)
          : (["bg-[var(--success)]", "Listo para generar"] as const);

  return (
    <span className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
      <span className={cn("size-1.5 shrink-0 rounded-full", tone)} />
      <span className="truncate">{text}</span>
    </span>
  );
}

/** Level 1 of "what is happening": one glance, from any screen. */
function JobIndicator({ onOpen }: { onOpen: () => void }) {
  const run = useActiveRun();
  const stream = useStream();
  const cancel = useCancelJob();

  const running = run?.job?.status === "running" || run?.job?.status === "queued";
  const elapsed = useElapsed(run?.job?.started_at ?? null, Boolean(running));
  const step = useMemo(() => run?.steps.filter((s) => s.status === "running").at(-1), [run]);

  if (!stream.connected) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <WifiOff className="size-3.5" />
        Sin conexión con el servidor
      </div>
    );
  }

  if (!run || !run.job) return <Readiness />;

  if (!running) {
    const tone = run.job.status === "failed" ? "danger" : run.job.status === "cancelled" ? "outline" : "success";
    return (
      <div className="flex min-w-0 items-center gap-3">
        <Readiness />
        <button
          onClick={onOpen}
          className="flex shrink-0 items-center gap-2 text-xs"
          title="Ver la última ejecución"
        >
          <Badge variant={tone as never}>
            {run.job.status === "failed" ? <AlertTriangle /> : <CircleCheck />}
            {run.job.label}
          </Badge>
          <span className="tabular-nums text-muted-foreground">{duration(run.job.elapsed_ms)}</span>
        </button>
      </div>
    );
  }

  // El porcentaje global manda sobre el del paso: un paso puede ir por 8/8 y quedar
  // aún media construcción por delante.
  const overall = run.overall;

  return (
    <div className="flex min-w-0 items-center gap-3">
      <button onClick={onOpen} className="flex min-w-0 items-center gap-2 text-left">
        <span className="relative flex size-2 shrink-0">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-[var(--info)] opacity-60" />
          <span className="relative inline-flex size-2 rounded-full bg-[var(--info)]" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-xs font-medium">
            {overall?.label ?? step?.label ?? run.job.label}
          </p>
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            {overall ? (
              <span className="tabular-nums">{overall.percent} %</span>
            ) : step?.total ? (
              <span className="tabular-nums">
                {step.current ?? 0}/{step.total}
              </span>
            ) : null}
            <span className="tabular-nums">{duration(elapsed)}</span>
            {stream.connected ? null : <span className="text-[var(--warning)]">reconectando…</span>}
          </div>
        </div>
      </button>
      {overall ? (
        <Progress value={overall.percent} max={100} className="hidden w-28 md:block" />
      ) : step?.total ? (
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
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("progress");
  const pipeline = usePipeline();
  const health = useHealth();
  const stream = useStream();
  const invalidate = useInvalidateChain();

  const openDrawer = (tab: DrawerTab) => {
    setDrawerTab(tab);
    setDrawerOpen(true);
  };

  useEffect(() => {
    runStore.connect();
  }, []);

  // A build rewrites the artifact behind every screen, so a finished job invalidates
  // the whole chain, not just the pipeline: otherwise the graph tab keeps showing the
  // KG it read before the build that just replaced it.
  useEffect(() => {
    if (stream.currentJobId === null) invalidate();
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

          <div className="ml-auto flex min-w-0 items-center gap-3">
            <JobIndicator onOpen={() => openDrawer("progress")} />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => openDrawer("logs")}
              title="Ver el registro completo de la sesión"
            >
              <ScrollText />
              <span className="hidden lg:inline">Registro</span>
              {stream.logs.length > 0 ? (
                <span className="tabular-nums text-muted-foreground">{stream.logs.length}</span>
              ) : null}
            </Button>
          </div>
        </div>

        {offline || missingModels.length > 0 ? (
          <div className="flex items-center gap-1.5 border-t border-border bg-[color-mix(in_oklch,var(--warning)_12%,transparent)] px-4 py-1.5 text-xs">
            {offline ? (
              <>
                <span>
                  Ollama no responde en <code className="font-mono">{health.data?.host}</code>
                </span>
                <InfoHint label="Qué implica">
                  Cualquier trabajo que necesite el modelo fallará al arrancar. La interfaz sigue
                  siendo navegable: lo ya construido se lee de disco.
                </InfoHint>
              </>
            ) : (
              <>
                <span>
                  Modelos sin instalar:{" "}
                  <code className="font-mono">{missingModels.join(", ")}</code>
                </span>
                <InfoHint label="Qué implica">
                  Los trabajos que usen esos modelos fallarán. El resto de la cadena funciona.
                </InfoHint>
              </>
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

      <RunDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        tab={drawerTab}
        onTab={setDrawerTab}
      />

      {!drawerOpen ? (
        <div className="fixed bottom-4 right-4 z-30 flex items-center overflow-hidden rounded-full border border-border bg-card text-xs font-medium shadow-lg">
          <button
            onClick={() => openDrawer("progress")}
            className="flex items-center gap-2 px-4 py-2 transition-colors hover:bg-accent"
          >
            <Activity className="size-4" />
            Ver ejecución
          </button>
          <span className="h-5 w-px bg-border" />
          <button
            onClick={() => openDrawer("logs")}
            title="Ver el registro"
            aria-label="Ver el registro"
            className="flex items-center gap-1.5 px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <ScrollText className="size-4" />
            {stream.logs.length > 0 ? (
              <span className="tabular-nums">{stream.logs.length}</span>
            ) : null}
          </button>
        </div>
      ) : null}
    </div>
  );
}

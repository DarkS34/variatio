import {
  Activity,
  FileJson,
  Library,
  Network,
  Play,
  Scale,
  ScrollText,
  Share2,
} from "lucide-react";
import { Fragment, useEffect, useState, type ReactNode } from "react";


import { RunDrawer, type DrawerTab } from "@/components/RunDrawer";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useHealth, useInvalidateChain, usePipeline, useStream } from "@/state/queries";
import { runStore } from "@/state/runStore";

/**
 * Three groups, separated on screen, because they are three different things.
 *
 * «Panel» is where the chain is watched; the middle three are the instance being
 * *prepared*, in the order they are prepared in; the last two *use* it. The separators
 * are the whole point — without them six tabs read as one flat list and nothing says
 * that the middle block has to be finished before the right one does anything.
 *
 * `qualifier` is the half of the name that only fits on a wide screen. It is dropped,
 * never abbreviated: «Grafo» and «Perfil» are already what these are called out loud.
 */
const NAV = [
  { path: "/", label: "Panel", qualifier: null, icon: Activity, artifact: null, group: "watch" },
  {
    path: "/preparar/grafo",
    label: "Grafo",
    qualifier: "de conocimiento",
    icon: Network,
    artifact: "knowledge_graph",
    group: "prepare",
  },
  {
    path: "/preparar/perfil",
    label: "Perfil",
    qualifier: "de ejemplares",
    icon: FileJson,
    artifact: "exemplars_profile",
    group: "prepare",
  },
  {
    path: "/preparar/banco",
    label: "Banco",
    qualifier: "de ejemplares",
    icon: Library,
    artifact: "exemplars_bank",
    group: "prepare",
  },
  { path: "/generar", label: "Generar", qualifier: null, icon: Play, artifact: null, group: "use" },
  { path: "/evaluar", label: "Evaluar", qualifier: null, icon: Scale, artifact: null, group: "use" },
] as const;

function NavItem({
  path,
  label,
  qualifier,
  icon: Icon,
  stage,
  active,
  accent,
}: {
  path: string;
  label: string;
  qualifier?: string | null;
  icon: typeof Activity;
  stage?: StageState;
  active: boolean;
  /** The two tabs that *use* the instance are tinted, so the working half of the app is
   *  findable without reading the labels. */
  accent?: boolean;
}) {
  const locked = Boolean(stage?.blocked_reason);
  return (
    <Link
      to={path}
      title={qualifier ? `${label} ${qualifier}` : label}
      className={cn(
        "flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition-colors",
        accent
          ? active
            ? "bg-primary/15 font-medium text-foreground ring-1 ring-inset ring-primary/40"
            : "bg-primary/[0.07] text-foreground/80 hover:bg-primary/15 hover:text-foreground"
          : active
            ? "bg-accent font-medium text-accent-foreground"
            : "text-muted-foreground hover:text-foreground",
      )}
    >
      <Icon className={cn("size-4", accent && "text-primary")} />
      {label}
      {qualifier ? <span className="hidden font-normal opacity-60 xl:inline">{qualifier}</span> : null}
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

          {/* La barra de pestañas es lo único que compite por el ancho aquí: el estado de
              la ejecución vive en el Panel, no arriba, precisamente porque lo estrujaba
              hasta hacer aparecer un scroll horizontal sobre las pestañas. Si aun así no
              cabe, se desplaza sin pintar la barra de scroll. */}
          <nav className="flex min-w-0 items-center gap-0.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {NAV.map((item, index) => (
              <Fragment key={item.path}>
                {index > 0 && NAV[index - 1].group !== item.group ? (
                  <span aria-hidden className="mx-1.5 h-5 w-px shrink-0 bg-border" />
                ) : null}
                <NavItem
                  path={item.path}
                  label={item.label}
                  qualifier={item.qualifier}
                  icon={item.icon}
                  stage={stageFor(item.artifact)}
                  active={path === item.path}
                  accent={item.group === "use"}
                />
              </Fragment>
            ))}
          </nav>

          <div className="ml-auto flex shrink-0 items-center gap-3">
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

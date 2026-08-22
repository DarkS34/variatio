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
import { useEffect, useState, type ReactNode } from "react";

import { RunDrawer, type DrawerTab } from "@/components/RunDrawer";
import { Button } from "@/components/ui/button";
import { Rail, type RailStop } from "@/components/ui/rail";
import { AccountMenu } from "@/features/auth/AccountMenu";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useHealth, useInvalidateChain, usePipeline, useStream } from "@/state/queries";
import { runStore } from "@/state/runStore";

/**
 * Three groups, separated on screen, because they are three different things.
 *
 * «Panel» is where the chain is watched; the middle three are the instance being
 * *prepared*, in the order they are prepared in; the last two *use* it. That the middle
 * block has to be finished before the right one does anything is now said by the rail
 * below, which is why the vertical separators that used to say it are gone.
 *
 * Two things are deliberately NOT here, and for the same reason — the navbar is the chain
 * and nothing else. «Variantes guardadas» is a personal archive, and «Administración» is
 * the installation seen from outside, which is not about the instance in front of you and
 * appears for one account in the whole installation. Both live in the account menu.
 *
 * `qualifier` and `icon` are kept on the entries although the rail draws neither: the
 * qualifier is still the full name for a tooltip, and dropping the icons is what buys the
 * width the labels need. They are one edit away if either is wanted back.
 */
const NAV = [
  { path: "/", label: "Panel", qualifier: null, icon: Activity, artifact: null, group: "watch" },
  // The profile leads the «prepare» group, and this order has to keep matching
  // `server/review.ARTIFACTS` — the panel's cards and their 1-2-3 badges read that tuple,
  // this array is a second copy of the same decision. The reason it is the profile: a graph
  // can be built with nothing, but its taggability review cannot run until the profile is
  // approved, so starting here is starting at a stage you cannot finish.
  {
    path: "/preparar/perfil",
    label: "Perfil",
    qualifier: "de ejemplares",
    icon: FileJson,
    artifact: "exemplars_profile",
    group: "prepare",
  },
  {
    path: "/preparar/grafo",
    label: "Grafo",
    qualifier: "de conocimiento",
    icon: Network,
    artifact: "knowledge_graph",
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

/**
 * The chain, drawn.
 *
 * The three groups survive and their order still has to match `server/review.ARTIFACTS`;
 * what goes are the vertical separators that used to mark them, because the rail already
 * tells the sequence and a hairline on top of a stretch told it twice. The break between
 * «preparar» and «usar» now reads as the dotted stretch it always was.
 *
 * A destination with no artifact has no stage status of its own. «Generar» and «Evaluar»
 * are blocked until the chain is approved and the pipeline says so; the panel never is.
 */
function navStops(
  stages: StageState[],
  path: string,
  generationUnlocked: boolean,
): RailStop[] {
  return NAV.map((item) => {
    const stage = stages.find((s) => s.artifact === item.artifact);
    const gated = item.group === "use" && !generationUnlocked;
    return {
      key: item.path,
      label: item.label,
      status: stage?.status ?? (gated ? "missing" : "approved"),
      blocked: stage ? Boolean(stage.blocked_reason) : gated,
      href: item.path,
      active: path === item.path,
    };
  });
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

  const offline = health.data && !health.data.available;
  const missingModels = health.data?.models.missing ?? [];

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-4 px-4">
          <Link to="/" className="flex shrink-0 items-center gap-2 font-semibold">
            <Share2 className="size-5 text-primary" />
            <span className="hidden 2xl:inline">Generador de variantes</span>
          </Link>

          <WorkspaceSwitcher />

          {/* The rail is the only thing competing for width here: the run's state lives in
              the panel and not up top, precisely because it squeezed this until a
              horizontal scrollbar appeared over the tabs. If it still does not fit it
              scrolls without painting one. */}
          <nav className="flex min-w-0 flex-1 items-center overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <Rail
              stops={navStops(stages, path, pipeline.data?.generation_unlocked ?? false)}
              size="sm"
              className="min-w-[34rem]"
            />
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
                <span className="nums text-muted-foreground">{stream.logs.length}</span>
              ) : null}
            </Button>
            <AccountMenu />
          </div>
        </div>

        {/* La consecuencia va en la propia frase: era lo único que decía la (i) que había
            al lado, y una advertencia que hay que abrir para entenderla no es una
            advertencia. */}
        {offline || missingModels.length > 0 ? (
          <div className="flex items-center gap-1.5 border-t border-border bg-[color-mix(in_oklch,var(--attention)_12%,transparent)] px-4 py-1.5 text-small">
            {offline ? (
              <span>
                Ollama no responde en <code className="font-mono">{health.data?.host}</code>:
                cualquier trabajo fallará al arrancar, pero lo ya construido se sigue leyendo.
              </span>
            ) : (
              <span>
                Modelos sin instalar{" "}
                <code className="font-mono">{missingModels.join(", ")}</code>: los trabajos que
                los usen fallarán, el resto de la cadena funciona.
              </span>
            )}
          </div>
        ) : null}
      </header>

      <main
        className={cn(
          "mx-auto w-full max-w-[1600px] flex-1 px-4 py-6",
          // scroll-pb as well as pb: without it a control focused while the drawer is open
          // gets scrolled to a position underneath the drawer.
          drawerOpen && "pb-[56vh] scroll-pb-[56vh]",
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
        <div className="fixed bottom-4 right-4 z-30 flex items-center overflow-hidden rounded-full border border-border bg-card text-small font-medium shadow-raised">
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
              <span className="nums">{stream.logs.length}</span>
            ) : null}
          </button>
        </div>
      ) : null}
    </div>
  );
}

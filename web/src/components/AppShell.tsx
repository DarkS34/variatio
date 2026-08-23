import { useQueryClient } from "@tanstack/react-query";
import { Activity, Play, Scale, ScrollText } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { RunDrawer, type DrawerTab } from "@/components/RunDrawer";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { Rail, type RailStop } from "@/components/ui/rail";
import { AccountMenu } from "@/features/auth/AccountMenu";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { keys, useHealth, useInvalidateChain, usePipeline, useStream } from "@/state/queries";
import { runStore } from "@/state/runStore";

/**
 * THREE BLOCKS, AND ONLY THE MIDDLE ONE IS A CHAIN.
 *
 * The rail used to run under all six destinations, which said something false: that «Panel»
 * comes before «Perfil» in the same sense that «Perfil» comes before «Banco». It does not —
 * the panel is where the chain is WATCHED, from outside it. So the rail now spans exactly
 * the three instance artifacts, which really are a sequence with dependencies, and the
 * other three destinations are pills that do not pretend to be stops on it.
 *
 * The three blocks, left to right:
 *   - «Panel» — watching. Its own pill, separated by a rule, because it is about the chain
 *     rather than a step of it.
 *   - Perfil → Grafo → Banco — the instance being PREPARED, in the order it is prepared in.
 *     This order has to keep matching `server/review.ARTIFACTS`: the panel lays its cards
 *     out in that tuple and this array is a second copy of the same decision. Neither place
 *     numbers the steps — the order is the layout, in both. The
 *     reason it starts at the profile: a graph can be built with nothing, but its taggability
 *     review cannot run until the profile is approved, so starting at the graph is starting
 *     at a stage you cannot finish.
 *   - «Generar» and «Evaluar» — USING what the middle block produced. Both are gated on the
 *     whole chain being approved, which is why they sit after the rule rather than on the
 *     rail: what gates them is the block as a whole, not the stop before them.
 *
 * «Evaluar» carries `--study`, and that is the one place in the navigation that spends a
 * colour. It is not decoration: evaluation is the only destination the palette's frontier
 * metaphor does not describe — it is not before, at or after the frontier, it is where the
 * frontier is measured — and the token exists precisely so that saying so does not require
 * borrowing a state colour that means something else. See `index.css`.
 *
 * Two destinations are deliberately NOT here, and for the reason the rail exists: the navbar
 * is the chain and the two things that consume it. «Variantes guardadas» is a personal
 * archive and «Administración» is the installation seen from outside; both live in the
 * account menu.
 */
const STAGES = [
  { path: "/preparar/perfil", label: "Perfil", artifact: "exemplars_profile" },
  { path: "/preparar/grafo", label: "Grafo", artifact: "knowledge_graph" },
  { path: "/preparar/banco", label: "Banco", artifact: "exemplars_bank" },
] as const;

function stageStops(stages: StageState[], path: string): RailStop[] {
  return STAGES.map((item) => {
    const stage = stages.find((s) => s.artifact === item.artifact);
    return {
      key: item.path,
      label: item.label,
      status: stage?.status ?? "missing",
      blocked: Boolean(stage?.blocked_reason),
      href: item.path,
      active: path === item.path,
    };
  });
}

/**
 * A destination that is not a stop on the rail.
 *
 * `tone` is what separates «Evaluar» from the other two, and it only ever takes the two
 * values below — a third would mean the navigation had started encoding something else.
 * The tint is `color-mix` over the header's own ground rather than a second token, so the
 * pill sits on the translucent header without a seam.
 */
function NavPill({
  to,
  label,
  icon: Icon,
  active,
  tone = "plain",
  disabledReason,
}: {
  to: string;
  label: string;
  icon: typeof Activity;
  active: boolean;
  tone?: "plain" | "study";
  disabledReason?: string | null;
}) {
  const study = tone === "study";
  return (
    <Link
      to={to}
      title={disabledReason ?? label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-small font-medium transition-colors",
        !study && "text-muted-foreground hover:bg-accent hover:text-foreground",
        !study && active && "bg-accent text-foreground",
        // The study pill is tinted even when it is NOT the current page: what the tint says
        // is "this destination is a different kind of thing", which is true from wherever
        // you are looking at it. Active only deepens it.
        study &&
          "text-study ring-1 ring-inset ring-[color-mix(in_oklch,var(--study)_30%,transparent)] bg-[color-mix(in_oklch,var(--study)_9%,transparent)] hover:bg-[color-mix(in_oklch,var(--study)_16%,transparent)]",
        study && active && "bg-[color-mix(in_oklch,var(--study)_18%,transparent)]",
        disabledReason && "opacity-45",
      )}
    >
      <Icon className="size-4" />
      {label}
    </Link>
  );
}

function NavRule() {
  return <span aria-hidden className="mx-1 h-5 w-px shrink-0 bg-border" />;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { path } = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("progress");
  const pipeline = usePipeline();
  const health = useHealth();
  const stream = useStream();
  const invalidate = useInvalidateChain();
  const queryClient = useQueryClient();

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
    else queryClient.invalidateQueries({ queryKey: keys.pipeline });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.currentJobId]);

  const stages = pipeline.data?.stages ?? [];

  const offline = health.data && !health.data.available;
  const missingModels = health.data?.models.missing ?? [];

  // Both "use" destinations are gated by the SAME condition — the whole chain approved —
  // so the reason is derived once and handed to both pills. They stay reachable: the
  // screens behind them explain what is missing, which a dimmed link cannot.
  const locked = (pipeline.data?.generation_unlocked ?? false)
    ? null
    : "Requiere las tres etapas aprobadas";

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
        {/* THREE COLUMNS, AND THE MIDDLE ONE IS THE CENTRE OF THE HEADER.
            The navigation used to be a `flex-1` sitting after the logo and the workspace
            switcher, so it started wherever those two happened to end: it read as pushed
            to the left, and it MOVED sideways every time the switcher changed the length
            of a workspace name. Here the two flanks are `flex-1 basis-0`, so they are
            always the same width and the nav lands on the centre line of the header
            whatever they contain.
            The nav keeps its own scroll for the narrow case, and it is the only item that
            can shrink: a flank with `basis-0` has a shrink weight of zero, so the squeeze
            lands where there is a scroller to absorb it. */}
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-4 px-4">
          <div className="flex min-w-0 flex-1 basis-0 items-center gap-4">
            <Link to="/" className="flex shrink-0 items-center gap-2 font-semibold">
              <Logo className="size-5 text-primary" />
              <span className="hidden 2xl:inline">Generador de variantes</span>
            </Link>

            <WorkspaceSwitcher />
          </div>

          <nav className="flex min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <NavPill to="/" label="Panel" icon={Activity} active={path === "/"} />

            <NavRule />

            {/* The rail gets a surface of its own so the three stages read as ONE object
                with three parts rather than as three pills that happen to be adjacent.
                That is the whole point of separating it: the line between the marks means
                a dependency, and it only means that if it is visibly bounded. */}
            <div className="shrink-0 rounded-lg border border-border/70 bg-secondary/50 px-3 py-1">
              <Rail stops={stageStops(stages, path)} size="sm" className="min-w-[15rem]" />
            </div>

            <NavRule />

            <NavPill
              to="/generar"
              label="Generar"
              icon={Play}
              active={path === "/generar"}
              disabledReason={locked}
            />
            <NavPill
              to="/evaluar"
              label="Evaluar"
              icon={Scale}
              active={path === "/evaluar"}
              tone="study"
              disabledReason={locked}
            />
          </nav>

          <div className="flex min-w-0 flex-1 basis-0 items-center justify-end gap-3">
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

        {/* The consequence goes in the sentence itself: it was all the (i) beside it said, and a
            warning one has to open in order to understand is not a warning. */}
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

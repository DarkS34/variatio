import { useQueryClient } from "@tanstack/react-query";
import { Activity, Archive, Files, Play, Scale, ScrollText, Wrench } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { RunDrawer, type DrawerTab } from "@/components/RunDrawer";
import { buttonVariants } from "@/components/ui/button";
import { Lockup } from "@/components/ui/logo";
import { Rail, type RailStop } from "@/components/ui/rail";
import { AccountMenu } from "@/features/auth/AccountMenu";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useHasWorkspace } from "@/state/auth";
import {
  keys,
  useHealth,
  useInvalidateChain,
  useMaintenance,
  usePipeline,
  useRaw,
  useStream,
} from "@/state/queries";
import { runStore } from "@/state/runStore";
import { useTranscriptionSummary } from "@/features/raw/queries";
import { useT, type Key } from "@/lib/i18n";

/**
 * FOUR BLOCKS, AND ONLY ONE OF THEM IS A CHAIN.
 *
 * The rail used to run under every destination, which said something false: that «Panel»
 * comes before «Perfil» in the same sense that «Perfil» comes before «Banco». It does not —
 * the panel is where the chain is WATCHED, from outside it. So the rail spans exactly the
 * three instance artifacts, which really are a sequence with dependencies, and everything
 * else is a pill that does not pretend to be a stop on it.
 *
 * The blocks, left to right:
 *   - «Panel» — watching. Its own pill, separated by a rule, because it is about the chain
 *     rather than a step of it, and BOUNDED rather than flat for the same reason: it is
 *     the view of the whole thing, not one more destination beside the others.
 *   - «Datos en bruto» — what the chain is MADE OF. Also its own pill, also before the
 *     rail, because the raw documents feed the stages without being one: they write no
 *     artifact, nobody approves them, and one origin feeds two stages at once. It carries
 *     a dot while something there is waiting to be transcribed.
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
 * is the chain and the two things that consume it. «Mis variantes» is a personal archive and
 * «Administración» is the installation seen from outside, so neither is a block of this
 * navigation — «Administración» lives in the account menu, and «Mis variantes» is a pill in
 * the header's RIGHT flank, beside the account it belongs to and away from the chain.
 */
const STAGES = [
  { path: "/prepare/profile", label: "nav.profile", artifact: "exemplars_profile" },
  { path: "/prepare/graph", label: "nav.graph", artifact: "knowledge_graph" },
  { path: "/prepare/bank", label: "nav.bank", artifact: "exemplars_bank" },
] as const;

function stageStops(stages: StageState[], path: string, t: (key: Key) => string): RailStop[] {
  return STAGES.map((item) => {
    const stage = stages.find((s) => s.artifact === item.artifact);
    return {
      key: item.path,
      label: t(item.label),
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
 * `tone` is what separates the three kinds, and it only ever takes the values below — a
 * fourth would mean the navigation had started encoding something else.
 *
 *   - `plain` — an ordinary destination: «Datos en bruto», «Generar».
 *   - `overview` — «Panel», and it is the only one. It is not a destination ALONGSIDE the
 *     others, it is the view of the whole chain from outside it, so it is bounded: a
 *     border, the card's own ground and one step of lift. The palette forbids saying that
 *     with a colour — structure here is achromatic and colour is evidence — so it is said
 *     with FORM, which is the same device the rail's surface already uses to mean «this is
 *     one object».
 *   - `study` — «Evaluar», tinted even when it is NOT the current page: what the tint says
 *     is "this destination is a different kind of thing", which is true from wherever you
 *     are looking at it. Active only deepens it.
 *
 * The tints are `color-mix` over the header's own ground rather than second tokens, so a
 * pill sits on the translucent header without a seam.
 */
function NavPill({
  to,
  label,
  icon: Icon,
  active,
  tone = "plain",
  disabledReason,
  mark,
}: {
  to: string;
  label: string;
  icon: typeof Activity;
  active: boolean;
  tone?: "plain" | "overview" | "study";
  disabledReason?: string | null;
  /** A dot the pill carries when the destination behind it has something waiting. */
  mark?: boolean;
}) {
  const study = tone === "study";
  const overview = tone === "overview";
  return (
    <Link
      to={to}
      title={disabledReason ?? label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-small font-medium transition-colors",
        !study && !overview && "text-muted-foreground hover:bg-accent hover:text-foreground",
        !study && !overview && active && "bg-accent text-foreground",
        overview &&
          "border border-border bg-card px-3 font-semibold text-foreground shadow-raised hover:bg-accent",
        overview && active && "bg-accent",
        study &&
          "text-study ring-1 ring-inset ring-[color-mix(in_oklch,var(--study)_30%,transparent)] bg-[color-mix(in_oklch,var(--study)_9%,transparent)] hover:bg-[color-mix(in_oklch,var(--study)_16%,transparent)]",
        study && active && "bg-[color-mix(in_oklch,var(--study)_18%,transparent)]",
        disabledReason && "opacity-45",
      )}
    >
      <Icon className="size-4" />
      {label}
      {mark ? <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-attention" /> : null}
    </Link>
  );
}

function NavRule() {
  return <span aria-hidden className="mx-1 h-5 w-px shrink-0 bg-border" />;
}

/**
 * The four blocks, once, rendered in one of two places.
 *
 * Above `xl` it sits on the header's centre line, between the two flanks. Below it, the
 * flanks alone fill the row — a workspace name plus an avatar is already most of a phone's
 * width — so the same navigation moves to a line of its own underneath and scrolls
 * sideways there. What it deliberately does NOT do is collapse into a menu: the rail IS
 * the state of the chain, and hiding it behind a button hides the one thing this bar is
 * for. A strip you can push with a thumb keeps it readable at 360 px and identical at
 * 1600.
 *
 * `xl` and not `lg`, because at `lg` it does not fit. Measured with the switcher at its
 * `max-w-44` cap: the row needs 1194 px in Spanish and 1196 in English, so between 1024 and
 * ~1195 the inline nav either painted over the flanks or — once they stopped collapsing —
 * had «Generar» clipped mid-word with no scrollbar to say so. 1280 leaves 85 px of slack,
 * which is what absorbs a language whose labels are longer.
 */
function MainNav({
  path,
  stages,
  locked,
  rawWaiting,
  className,
}: {
  path: string;
  stages: StageState[];
  locked: string | null;
  /** Why the rail is dimmed, or null. See the surface below — it is a hint, not a gate. */
  rawWaiting: string | null;
  className?: string;
}) {
  const { t } = useT();
  return (
    <nav
      className={cn(
        "min-w-0 items-center gap-1 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
    >
      <NavPill
        to="/"
        label={t("nav.dashboard")}
        icon={Activity}
        active={path === "/"}
        tone="overview"
      />

      <NavRule />

      {/* The raw material feeds the chain but is NOT a step of it: it writes no artifact,
          nobody approves it, and it is upstream of two stages at once. So it is its own
          pill before the rail rather than a fourth stop on it. */}
      <NavPill
        to="/raw"
        label={t("nav.rawData")}
        icon={Files}
        active={path === "/raw"}
        mark={Boolean(rawWaiting)}
      />

      <NavRule />

      {/* The rail gets a surface of its own so the three stages read as ONE object
          with three parts rather than as three pills that happen to be adjacent.
          That is the whole point of separating it: the line between the marks means
          a dependency, and it only means that if it is visibly bounded.

          DIMMED IS NOT DISABLED, and the distinction is a closed decision rather than a
          nicety. Transcribing the raw documents is an accelerator and never a gate — every
          builder keeps its own conversion phase — so with documents still untranscribed
          the block recedes and says why, and every stop stays clickable and buildable.

          WHAT RECEDES IS THE SURFACE, NOT THE TEXT, and that was measured rather than
          preferred. The obvious `opacity-45` puts the stops' own labels — `text-micro` at
          `--muted-foreground`, already the lowest tier the palette has — at about 1.6:1
          against the header, and there is NO opacity that both reads as attenuated and
          clears 3:1: full strength is 4.7 and 0.8 is already down to 2.7. So the SURFACE
          carries it and every label keeps the contrast it was verified at.

          The surface is tinted with `--attention` rather than drained to grey, and that is
          a claim and not a decoration. Grey is what this palette says about things that are
          merely downstream, and it read as switched-off — which is the one thing this state
          is not. What is true here is that the block is waiting on the frontier, and the
          frontier is exactly what `--attention` names: the wash rhymes with the dot on
          «Datos en bruto» two pills to the left, so the state and the thing to do about it
          are visibly the same fact. The border stays dashed, which is the rail's own idiom
          for «not resolved yet», now in the hue that says why. */}
      <div
        title={rawWaiting ?? undefined}
        className={cn(
          "shrink-0 rounded-lg border px-2 py-1 transition-colors sm:px-3",
          rawWaiting
            ? "border-dashed border-[color-mix(in_oklch,var(--attention)_45%,transparent)] bg-[color-mix(in_oklch,var(--attention)_7%,transparent)]"
            : "border-border/70 bg-secondary/50",
        )}
      >
        <Rail stops={stageStops(stages, path, t)} size="sm" className="min-w-[12.5rem] sm:min-w-[15rem]" />
      </div>

      <NavRule />

      <NavPill
        to="/generate"
        label={t("nav.generate")}
        icon={Play}
        active={path === "/generate"}
        disabledReason={locked}
      />
      <NavPill
        to="/evaluate"
        label={t("nav.evaluate")}
        icon={Scale}
        active={path === "/evaluate"}
        tone="study"
        disabledReason={locked}
      />
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useT();
  const { path } = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("progress");
  const pipeline = usePipeline();
  const health = useHealth();
  const maintenance = useMaintenance();
  const raw = useRaw();
  const stream = useStream();
  const hasWorkspace = useHasWorkspace();
  const invalidate = useInvalidateChain();
  const queryClient = useQueryClient();

  const openDrawer = (tab: DrawerTab) => {
    setDrawerTab(tab);
    setDrawerOpen(true);
  };

  // Not opened while the account is in no workspace: the handshake resolves a membership
  // like every route does, so it would only be refused — and a refusal reads as «la
  // sesión ha caducado», which is the one thing that is not happening here.
  useEffect(() => {
    if (hasWorkspace) runStore.connect();
  }, [hasWorkspace]);

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
    : t("nav.needsApproved");

  // A HINT AND NOT A GATE, which is the whole reason it is a tooltip on a dimmed surface
  // rather than a `disabledReason`: the sentence says the builds will run anyway. Only
  // asked while the account is in a workspace — with none, the two queries behind it would
  // just 403.
  const rawSlots = raw.data?.slots ?? [];
  const rawSummary = useTranscriptionSummary(hasWorkspace ? rawSlots : []);
  const rawWaiting =
    rawSummary.todo > 0 ? t("nav.rawWaiting", { n: rawSummary.todo }) : null;

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
            may shrink: a flank with `basis-0` absorbs no negative free space, so the
            squeeze lands where there is a scroller to absorb it.
            The flanks carry NO `min-w-0`, and that is the load-bearing half. `flex-1`
            makes them grow into whatever the nav leaves, and with `min-width: 0` they
            grow to nothing and their contents simply paint OUTSIDE the box — measured
            between 1024 and 1152 px, «Panel» was drawn on top of the workspace name and
            «Evaluar» on top of «Mis variantes». Letting `min-width: auto` stand holds each
            flank at its own min-content, which is bounded: the lockup is fixed, the
            switcher is `max-w-44` and truncates. */}
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-2 px-3 sm:gap-4 sm:px-4">
          {/* THE LOCKUP AND THE INSTANCE ARE TWO DIFFERENT FACTS, so a rule separates them.
              Side by side with only a gap between, the workspace name read as part of the
              product's own name. The lockup itself is `ui/logo.tsx`'s, and `compact` is
              what drops the wordmark below `lg`. */}
          <div className="flex flex-1 basis-0 items-center gap-2 sm:gap-3">
            <Link
              to="/"
              aria-label="Variatio" // i18n-exempt: es el nombre del producto
              className="shrink-0"
            >
              <Lockup compact />
            </Link>

            <span aria-hidden className="h-6 w-px shrink-0 bg-border" />

            <WorkspaceSwitcher />
          </div>

          <MainNav
            path={path}
            stages={stages}
            locked={locked}
            rawWaiting={rawWaiting}
            className="hidden xl:flex"
          />

          <div className="flex flex-1 basis-0 items-center justify-end gap-1 sm:gap-3">
            {/* THE LOG GAVE THIS CORNER UP TO «Mis variantes» (2026-08-28, explicit user
                request), and nothing was lost by it: the log is diagnostics and is already
                one press away in the floating «Ver ejecución» pill, WITH its unread count,
                which is also where a person is already looking while a job runs. The saved
                variants are the product of every run and were reachable only by opening a
                menu — the one destination of the four in that menu that is used daily.

                It is a pill and not a stop on the rail, for the rail's own reason: the
                variants are a personal archive, they write no artifact and nothing
                downstream depends on them. It reuses `buttonVariants` rather than
                restating a ghost button, so it cannot drift from the one the header had. */}
            <Link
              to="/account/variants"
              title={t("nav.myVariants")}
              aria-current={path === "/account/variants" ? "page" : undefined}
              className={cn(
                buttonVariants({ variant: "ghost", size: "sm" }),
                // Below `lg` it is the icon alone: the word is the first thing to give up
                // when the row is 360 px wide and the workspace name is the one piece of
                // it nobody can guess.
                "px-2 text-muted-foreground hover:text-foreground sm:px-2.5",
                path === "/account/variants" && "bg-accent text-foreground",
              )}
            >
              <Archive />
              <span className="hidden lg:inline">{t("nav.myVariants")}</span>
            </Link>
            <AccountMenu />
          </div>
        </div>

        {/* The same navigation, on its own line, for everything narrower than a laptop. */}
        <MainNav
          path={path}
          stages={stages}
          locked={locked}
          rawWaiting={rawWaiting}
          className="flex border-t border-border px-3 py-1.5 xl:hidden"
        />

        {/* Whoever is seeing this while the door is closed is the account that closed it —
            everybody else is looking at the notice — so the strip is a reminder rather than
            a warning: the risk is forgetting it is on, not failing to notice. */}
        {maintenance.data?.active ? (
          <div className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1 border-t border-border bg-[color-mix(in_oklch,var(--destructive)_12%,transparent)] px-3 py-1.5 text-center text-small sm:px-4">
            <Wrench className="size-3.5 shrink-0" />
            <span>{t("shell.maintenance")}</span>
            <Link to="/admin" className="font-medium underline underline-offset-4">
              {t("shell.reopen")}
            </Link>
          </div>
        ) : null}

        {/* The consequence goes in the sentence itself: it was all the (i) beside it said, and a
            warning one has to open in order to understand is not a warning. */}
        {offline || missingModels.length > 0 ? (
          <div className="flex items-start justify-center gap-1.5 border-t border-border bg-[color-mix(in_oklch,var(--attention)_12%,transparent)] px-3 py-1.5 text-center text-small sm:items-center sm:px-4">
            {/* Neither the host nor the model names belong here: the strip says what does
                not work and what still does, and where the engine lives and which model is
                missing are «Administración → Motor»'s, which is where one acts on them. */}
            <span>{offline ? t("shell.engineOffline") : t("shell.missingModels")}</span>
          </div>
        ) : null}
      </header>

      <main
        className={cn(
          // The bottom padding is not symmetric with the top, and that is the floating
          // «Ver ejecución» pill: fixed to the corner, it covers whatever the page happens
          // to end on. It is 36 px tall over a 12/16 px offset, so the reservation has to
          // clear ~52 px AT EVERY WIDTH — `sm:pb-6` cleared 24 and the pill swallowed the
          // CSV button of «Administración → Evaluaciones» whole: measured, a real click on
          // its centre opened the run drawer instead of downloading anything.
          "mx-auto w-full max-w-[1600px] flex-1 px-3 pb-20 pt-4 sm:px-4 sm:pb-16 sm:pt-6",
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
        <div className="fixed bottom-3 right-3 z-30 flex items-center overflow-hidden rounded-full border border-border bg-card text-small font-medium shadow-raised sm:bottom-4 sm:right-4">
          <button
            onClick={() => openDrawer("progress")}
            className="flex items-center gap-2 px-4 py-2 transition-colors hover:bg-accent"
          >
            <Activity className="size-4" />
            {t("shell.viewRun")}
          </button>
          <span className="h-5 w-px bg-border" />
          <button
            onClick={() => openDrawer("logs")}
            title={t("shell.viewLog")}
            aria-label={t("shell.viewLog")}
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

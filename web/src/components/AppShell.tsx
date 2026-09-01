import { useQueryClient } from "@tanstack/react-query";
import { Check, Play, Scale, Wrench } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Lockup } from "@/components/ui/logo";
import { AccountMenu } from "@/features/auth/AccountMenu";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";
import { Link, useRouter } from "@/lib/router";
import { STEPS, stepStates, type StepState } from "@/lib/steps";
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

const STATE_KEY: Record<StepState, Key> = {
  done: "nav.state.done",
  now: "nav.state.now",
  later: "nav.state.later",
};

/**
 * ONE PATH, FOUR NUMBERED STOPS, AND TWO THINGS TO DO WITH WHAT THEY PRODUCE.
 *
 * The bar used to be four blocks — an overview pill, the raw material, a rail of three
 * stages, and the two consumers — and each of the four said something true about the
 * architecture. What it did not say was where a person is supposed to go NEXT, which is
 * the only question somebody opening this for the first time actually has.
 *
 * So the bar IS the path now. «Panel» is gone: it was the view of a chain from outside
 * it, and there is nothing left to watch from outside once the chain is the navigation.
 * The raw material stops being a pill of its own and becomes step 1 — it writes no
 * artifact and nobody approves it, which is exactly why it was excluded before, but a
 * teacher does not care what writes an artifact: they care that uploading their notes is
 * the first thing they do. And the rail goes with them, because what the rail encoded —
 * a dependency between stops — is now said by the numbers and by the one state word
 * under each name.
 *
 * WHAT REPLACES IT IS THE FRONTIER, WHICH IS WHAT THE PALETTE ALREADY MEANS. A counter
 * filled with `--settled` is behind you, one filled with `--attention` is where you act,
 * and a dashed outline is not reachable yet. That is the same calculation the generator
 * performs on every prompt (assumed known / target / not yet taught) and the same one the
 * mark draws in three squares, so the bar spends no colour it was not already spending.
 *
 * THE NUMBERS ARE A REVERSAL, and a deliberate one (2026-08-31, explicit user request).
 * The register says no stage carries an ordinal, and the reason it gave was that the app
 * shipped TWO contradictory numberings of one chain — `review.ARTIFACTS` reads profile,
 * graph, bank while the screen titles numbered it graph, profile, bank. There is one
 * numbering now, it is this one, and the tutorial promises it in the same order.
 *
 * The order is `review.ARTIFACTS` with the raw material in front, and it must stay so:
 * the profile leads because finishing the graph needs an APPROVED profile —
 * `routers/jobs.NEEDS_APPROVED` gates the taggability review on it — so starting at the
 * graph is starting at a stage you cannot finish.
 */
/**
 * The step's number, or a bare tick once it is behind you.
 *
 * A square and not a circle, because `--radius` is 0 and the corner is where this grid
 * either holds or does not. The fills are the palette's own frontier and not a traffic
 * light: attention for where you act, an outline for what is not reachable yet.
 *
 * A DONE STEP CARRIES NO BOX AT ALL (2026-09-01, explicit user request). It used to be a
 * filled `--settled` square with a white tick, which drew the eye to the three stops
 * there is nothing left to do on — the loudest mark on the bar sat on the finished work.
 * The tick alone says the same thing and recedes, which is what «behind you, resolved» is
 * supposed to look like. The 22 px box stays as empty space so the four names still line
 * up on one column.
 */
function StepCounter({ state, n }: { state: StepState; n: number }) {
  const box = "flex size-[22px] shrink-0 items-center justify-center";
  if (state === "done") {
    return (
      <span className={cn(box, "text-settled")}>
        <Check className="size-4" strokeWidth={3} />
      </span>
    );
  }
  return (
    <span
      className={cn(
        box,
        "nums font-condensed text-small font-semibold",
        state === "now"
          ? "bg-attention text-[oklch(0.99_0.003_262)]"
          : "border border-dashed border-input text-muted-foreground",
      )}
    >
      {n}
    </span>
  );
}

/**
 * One stop of the path: its number, its name, and one word saying where you are.
 *
 * Two lines rather than one, and that is the «píldora bien explicada»: the name alone is
 * a destination, while the name with «te toca ahora» under it is an instruction. It costs
 * the header 16 px of height and saves every screen a paragraph explaining the order.
 */
function StepPill({
  step,
  state,
  n,
  active,
  title,
}: {
  step: (typeof STEPS)[number];
  state: StepState;
  n: number;
  active: boolean;
  title?: string;
}) {
  const { t } = useT();
  return (
    <Link
      to={step.path}
      title={title ?? t(step.labelKey)}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex shrink-0 flex-col gap-0.5 rounded-md px-2.5 py-1.5 transition-colors hover:bg-accent",
        state === "now" && "bg-[color-mix(in_oklch,var(--attention)_8%,transparent)]",
        active && "bg-accent",
      )}
    >
      <span
        className={cn(
          "flex items-center gap-2 whitespace-nowrap text-body",
          state === "later" ? "text-muted-foreground" : "text-foreground",
          state === "now" ? "font-semibold" : "font-medium",
        )}
      >
        <StepCounter state={state} n={n} />
        {t(step.labelKey)}
      </span>
      <span
        className={cn(
          "pl-[30px] text-micro",
          state === "done" && "text-settled",
          state === "now" && "text-attention",
          state === "later" && "text-muted-foreground",
        )}
      >
        {t(STATE_KEY[state])}
      </span>
    </Link>
  );
}

/**
 * What you do with the path once it is walked: ask for an exercise, or compare three.
 *
 * Both are gated on the whole chain being approved, which is why they sit after the rule
 * rather than among the steps — what gates them is the path as a whole, not the stop
 * before them. They stay reachable: the screens behind them explain what is missing,
 * which a dimmed link cannot.
 *
 * «Comparar» carries `--study`, tinted even when it is not the current page: what the
 * tint says is «this is a different kind of thing», which is true from wherever you look
 * at it. It is the one place in the navigation that spends a colour on identity.
 */
function UsePill({
  to,
  label,
  icon: Icon,
  active,
  study = false,
  disabledReason,
}: {
  to: string;
  label: string;
  icon: typeof Play;
  active: boolean;
  study?: boolean;
  disabledReason?: string | null;
}) {
  return (
    <Link
      to={to}
      title={disabledReason ?? label}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-body font-medium transition-colors",
        !study && "text-muted-foreground hover:bg-accent hover:text-foreground",
        !study && active && "bg-accent text-foreground",
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
  return <span aria-hidden className="mx-1.5 h-8 w-px shrink-0 bg-border" />;
}

/**
 * The path, once, rendered in one of two places.
 *
 * Above `xl` it sits on the header's centre line, between the two flanks. Below it, the
 * flanks alone fill the row — a workspace name plus an avatar is already most of a
 * phone's width — so the same navigation moves to a line of its own underneath and
 * scrolls sideways there. What it deliberately does NOT do is collapse into a menu: the
 * bar IS the state of the path, and hiding it behind a button hides the one thing it is
 * for.
 */
function MainNav({
  path,
  stages,
  locked,
  rawStocked,
  rawWaiting,
  className,
}: {
  path: string;
  stages: StageState[];
  locked: string | null;
  /** Whether both origins hold documents, which is what «paso 1 hecho» means. */
  rawStocked: boolean;
  /** What is still untranscribed, or null. A hint on step 1 and never a gate. */
  rawWaiting: string | null;
  className?: string;
}) {
  const { t } = useT();
  // WHETHER THE STRIP IS CUT OFF ON THE RIGHT, so the fade below can say so. Measured at
  // 390 px: the row needs more than the screen has, the scroller works, and its bar is
  // hidden on purpose — so without this there is nothing at all to suggest the strip
  // continues, and the two destinations that consume the whole path do not exist.
  const strip = useRef<HTMLElement>(null);
  const [cut, setCut] = useState(false);
  useEffect(() => {
    const el = strip.current;
    if (!el) return;
    const measure = () => setCut(el.scrollWidth - el.clientWidth - el.scrollLeft > 4);
    measure();
    el.addEventListener("scroll", measure, { passive: true });
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => {
      el.removeEventListener("scroll", measure);
      observer.disconnect();
    };
  }, [stages.length, locked, rawWaiting, rawStocked]);

  const states = stepStates(stages, rawStocked);

  return (
    <nav
      ref={strip}
      // The fade is a mask rather than a gradient overlay: an overlay would need a
      // background colour, and this strip sits on a translucent blurred header where any
      // solid ground shows as a seam.
      style={
        cut
          ? {
              maskImage: "linear-gradient(to right, #000 calc(100% - 2rem), transparent)",
              WebkitMaskImage: "linear-gradient(to right, #000 calc(100% - 2rem), transparent)",
            }
          : undefined
      }
      className={cn(
        "min-w-0 items-center gap-0.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
    >
      {STEPS.map((step, index) => (
        <StepPill
          key={step.path}
          step={step}
          state={states[index]}
          n={index + 1}
          active={path === step.path}
          title={step.artifact === null && rawWaiting ? rawWaiting : undefined}
        />
      ))}

      <NavRule />

      <UsePill
        to="/generate"
        label={t("nav.create")}
        icon={Play}
        active={path === "/generate"}
        disabledReason={locked}
      />
      <UsePill
        to="/evaluate"
        label={t("nav.compare")}
        icon={Scale}
        active={path === "/evaluate"}
        study
        disabledReason={locked}
      />
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useT();
  const { path } = useRouter();
  const pipeline = usePipeline();
  const health = useHealth();
  const maintenance = useMaintenance();
  const raw = useRaw();
  const stream = useStream();
  const hasWorkspace = useHasWorkspace();
  const invalidate = useInvalidateChain();
  const queryClient = useQueryClient();

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

  // WHETHER THE FLOATING PILL EXISTS AT ALL, and it is not a nicety: it made a real button
  // unreachable. «Ver ejecución» is anchored to the bottom-right corner, and the CSV export
  // of «Administración → Evaluaciones» is anchored to the right of its own row — measured,
  // a real click on the centre of that button opened the run drawer and downloaded nothing.
  // `main`'s `pb-20` keeps content from ENDING underneath, which is a different problem and
  // never was this one.
  //
  // The condition is «has anything run in this session», not «is something running now»: a
  // finished run is exactly what one goes to the drawer to read, and it would be perverse
  // to hide the log the moment the job it belongs to ends. With nothing ever run there is
  // nothing behind the pill, so the corner goes back to the page.

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
  // Qué significa «paso 1 hecho»: los dos orígenes tienen algo. No la transcripción, que
  // es un acelerador y nunca una reja — un paso marcado como pendiente por algo que no
  // impide seguir sería una promesa falsa en la única barra que la gente lee.
  const rawStocked =
    rawSlots.length > 0 && rawSlots.every((slot) => slot.files.length > 0);

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

          {/* NOTHING TO NAVIGATE WITHOUT AN INSTANCE. All seven destinations render the
              same «Todavía no tienes ningún workspace», so the bar was offering seven
              doors into one room — and to a student account, five of them are the
              teacher's preparation chain. `App` already gates the routes; this stops the
              navigation from advertising them. */}
          {hasWorkspace ? (
            <MainNav
              path={path}
              stages={stages}
              locked={locked}
              rawWaiting={rawWaiting}
              rawStocked={rawStocked}
              className="hidden xl:flex"
            />
          ) : null}

          <div className="flex flex-1 basis-0 items-center justify-end gap-1 sm:gap-3">
            <AccountMenu />
          </div>
        </div>

        {/* The same navigation, on its own line, for everything narrower than a laptop. */}
        {hasWorkspace ? (
          <MainNav
            path={path}
            stages={stages}
            locked={locked}
            rawWaiting={rawWaiting}
            rawStocked={rawStocked}
            className="flex border-t border-border px-3 py-1.5 xl:hidden"
          />
        ) : null}

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
          "mx-auto w-full max-w-[1600px] flex-1 px-3 pb-8 pt-4 sm:px-4 sm:pt-6",
        )}
      >
        {children}
      </main>

    </div>
  );
}

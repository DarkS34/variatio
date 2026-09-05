import { useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Play, Scale, Wrench } from "lucide-react";
import { useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";

import { Lockup } from "@/components/ui/logo";
import { AccountMenu } from "@/features/auth/AccountMenu";
import { slideOf } from "@/features/tutorial/slides";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";
import { Link, useRouter } from "@/lib/router";
import { STEPS, USES, stepBusy, stepNumber, stepStates, type StepState } from "@/lib/steps";
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
 * The step's number, in a box whose stroke says where you stand.
 *
 * A square and not a circle, because `--radius` is 0 and the corner is where this grid
 * either holds or does not. The strokes are the palette's own frontier and not a traffic
 * light: a fill in `--attention` where you act, a dashed outline on what is not reachable
 * yet, and a solid outline in `--settled` on what is behind you.
 *
 * A DONE STEP KEEPS ITS NUMBER AND CARRIES NO FILL (2026-09-02, explicit user request; it
 * amends the bare tick of 2026-09-01). The filled `--settled` square drew the eye to the
 * stops with nothing left to do on, and the bare tick that replaced it threw the number
 * away, so a finished construction was four anonymous ticks. A solid, quiet outline keeps
 * the identity and still recedes; the tick lives in the word under the name.
 *
 * A STEP WITH WORK RUNNING ON IT SPINS A WHEEL WHERE THE NUMBER WAS (2026-09-02, explicit
 * user request). «Building» is `--primary` plus motion — the palette's own rule — so the
 * wheel is ink and the box loses its tint while it turns: the frontier has not moved, only
 * the work has started. The animation is deliberately not switched off under
 * `prefers-reduced-motion`, for the reason the pulse is not: it is the one sign in the bar
 * that a build running for an hour is still alive.
 */
export function StepCounter({
  state,
  n,
  busy = false,
}: {
  state: StepState;
  n: string;
  busy?: boolean;
}) {
  if (busy) {
    return (
      <span className={cn(COUNTER_BOX, "text-primary")}>
        <Loader2 className="size-4 animate-spin" strokeWidth={2.5} />
      </span>
    );
  }
  return (
    <span
      className={cn(
        COUNTER_BOX,
        "nums font-condensed text-small font-semibold",
        // A DONE STEP IS A BARE TICK, WITH NO BOX AROUND IT (2026-09-04, explicit user
        // request; the tick itself is 2026-09-03's, and the box it sat in was that entry's
        // other half). A box is what says «there is something here to reach»: the number
        // needs one and keeps it, in both its states, and what is behind you needs nothing
        // drawn around it. `COUNTER_BOX` stays, so the glyph keeps its 22 px of height and
        // 20 px of width and the four stops still line up — only the stroke goes.
        state === "done" && "text-settled",
        state === "now"
          // The TOKEN and not its light-mode value: `--attention` is a light ground in dark
          // mode, so the literal put a near-white number on it. This is the same defect the
          // palette pass of 2026-09-01 found in two other places, and it is invisible to
          // `check:color`, which reads `index.css` and not a class in a component.
          ? "bg-attention text-attention-foreground"
          : null,
        state === "later" && "border border-dashed border-input text-muted-foreground",
      )}
    >
      {state === "done" ? <Check className="size-3.5" strokeWidth={3} aria-hidden /> : n}
    </span>
  );
}

// `min-w` and not a fixed square: «1» and an icon are the same height, and the height is
// what keeps the names of a row on one line.
const COUNTER_BOX = "flex h-[22px] min-w-[20px] shrink-0 items-center justify-center px-1";

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
  busy = false,
}: {
  step: (typeof STEPS)[number];
  state: StepState;
  n: string;
  active: boolean;
  title?: string;
  /** Work running on this step right now: the wheel, and «Construyendo» / «Leyendo» under the name. */
  busy?: boolean;
}) {
  const { t } = useT();
  return (
    <Link
      to={step.path}
      title={title ?? t(step.labelKey)}
      aria-current={active ? "page" : undefined}
      className={cn(
        PILL,
        state === "now" && "bg-[color-mix(in_oklch,var(--attention)_8%,transparent)]",
        active && "bg-accent",
      )}
    >
      <span
        className={cn(
          PILL_NAME,
          state === "later" ? "text-muted-foreground" : "text-foreground",
          state === "now" ? "font-semibold" : "font-medium",
        )}
      >
        <StepCounter state={state} n={n} busy={busy} />
        {t(step.labelKey)}
      </span>
      <span
        className={cn(
          PILL_WORD,
          busy && "text-foreground",
          !busy && state === "done" && "text-settled",
          !busy && state === "now" && "text-attention",
          !busy && state === "later" && "text-muted-foreground",
        )}
      >
        {busy
          ? t(step.artifact === null ? "nav.state.reading" : "nav.state.building")
          : t(STATE_KEY[state])}
      </span>
    </Link>
  );
}

// The three pieces a step and a door share, so the two kinds of pill are one height and one
// shape and differ only in the mark: a number for a stop, an icon for a door.
// MEASURED AT 1280 (2026-09-02): the flanks leave the strip 881 px and, at `px-2.5`,
// `gap-2` and `text-body`, the six pills asked for 951 — the two doors grew a box and a
// word each. `px-2`, `gap-1.5` and `text-small` on the name brought it under; the word line
// keeps the micro step, so the hierarchy inside a pill is unchanged. RE-MEASURED 2026-09-04,
// when small went to 14 px and micro to 12: the flanks left 874 and the strip asked 881, so
// the pills went to `px-1.5` — 6 px per pill, 36 in all — and the phase caption's `pl`
// moved with it, since the two are one alignment.
const PILL =
  "flex shrink-0 flex-col gap-0.5 rounded-md px-1.5 py-1 transition-colors hover:bg-accent";
const PILL_NAME = "flex items-center gap-1.5 whitespace-nowrap text-small";
const PILL_WORD = "flex items-center gap-1 pl-[28px] text-micro";
/**
 * The height a step pill reaches on its own: `py-1` twice, the 22 px counter box (taller
 * than the small line beside it), the `gap-0.5`, and one micro line (0.75rem × 1.35).
 * A door with no word under its name is held to it, so the row never changes height.
 */
const PILL_HEIGHT = "min-h-[calc(0.5rem_+_22px_+_2px_+_1.0125rem)]";

/**
 * One door of the second phase: what you do with the construction once it is closed.
 *
 * The same two-line pill as a step, with an ICON where the step has its number — the two
 * doors have no order between them, and a number would have said they had one (2026-09-02,
 * explicit user request; they were `2` and `3` until then). Both are gated on the whole
 * construction being closed, which is why they sit under a caption of their own rather
 * than among the steps: what gates them is the phase as a whole, not the stop before them.
 *
 * WHILE THE CONSTRUCTION IS OPEN A DOOR IS HALF OFF AND ANSWERS NO CLICK (2026-09-02,
 * explicit user request: «el usuario no debería poder entrar a ninguna de las dos hasta
 * que no termine de construir; déjalo medio apagado y sin respuesta a la pulsación»). It is
 * a `span` and not a link, at half opacity, with the dashed box and «después» under the
 * name saying why, and the reason in its `title`. This reverses the earlier «they stay
 * reachable while locked»: a URL typed by hand still lands on `ChainGate`, which names the
 * stage in the way, so nothing is lost by the bar refusing. Closed, it is a link with no
 * word under the name at all — «cuando quieras» was tried there and rejected the same day
 * — and the name is CENTRED in a pill of the steps' own height (`PILL_HEIGHT`), so the two
 * doors stay level with the steps and nothing in the row moves when the construction
 * closes (2026-09-02, explicit user request: «el texto tiene que estar centrado»). The
 * two doors sit `gap-1` apart, the same 4 px the rule between the phases keeps on either
 * side, where the steps sit 2 px apart.
 *
 * «Evaluar el sistema» carries `--evaluation`, tinted whether locked or not: what the tint says
 * is «this is a different kind of thing», which is true from wherever you look at it. It is
 * the one place in the navigation that spends a colour on identity.
 */
function DoorPill({
  door,
  icon: Icon,
  active,
  open,
  disabledReason,
}: {
  door: (typeof USES)[number];
  icon: ComponentType<{ className?: string; strokeWidth?: number }>;
  active: boolean;
  /** Whether the whole construction is closed, which is what opens both doors at once. */
  open: boolean;
  disabledReason?: string | null;
}) {
  const { t } = useT();
  const evaluation = door.evaluation;
  const face = cn(
    PILL,
    PILL_HEIGHT,
    "justify-center",
    evaluation &&
      "text-evaluation ring-1 ring-inset ring-[color-mix(in_oklch,var(--evaluation)_30%,transparent)] bg-[color-mix(in_oklch,var(--evaluation)_9%,transparent)]",
  );
  const body = (
    <>
      <span
        className={cn(
          PILL_NAME,
          "font-medium",
          !open && "text-muted-foreground",
          open && !evaluation && "text-foreground",
        )}
      >
        <span
          className={cn(
            COUNTER_BOX,
            !open && "border border-dashed border-input text-muted-foreground",
          )}
        >
          <Icon className="size-4" strokeWidth={2.25} />
        </span>
        {t(door.labelKey)}
      </span>
      {open ? null : (
        <span className={cn(PILL_WORD, "text-muted-foreground")}>{t("nav.state.later")}</span>
      )}
    </>
  );
  if (!open) {
    return (
      <span
        role="link"
        aria-disabled="true"
        title={disabledReason ?? t(door.labelKey)}
        className={cn(face, "cursor-default opacity-50 hover:bg-transparent")}
      >
        {body}
      </span>
    );
  }
  return (
    <Link
      to={door.path}
      title={t(door.labelKey)}
      aria-current={active ? "page" : undefined}
      className={cn(
        face,
        evaluation && "hover:bg-[color-mix(in_oklch,var(--evaluation)_16%,transparent)]",
        evaluation && active && "bg-[color-mix(in_oklch,var(--evaluation)_18%,transparent)]",
        !evaluation && active && "bg-accent",
      )}
    >
      {body}
    </Link>
  );
}

/**
 * A phase: its name as a caption, and its pills under it in a row.
 *
 * The caption is what carries the phase now that its number is gone. It is micro, condensed
 * and muted, so the row still reads as pills with a label over them and not as two rows of
 * navigation. Its `pl-1.5` is the pills' own `px-1.5`, so the caption starts exactly on the
 * first pill's box edge (2026-09-02, explicit user request: it was 2 px ahead of it).
 */
function PhaseGroup({
  label,
  gap = "tight",
  children,
}: {
  label: string;
  /** `wide` is the doors' 4 px, the rule's own margin; the steps keep 2 px. */
  gap?: "tight" | "wide";
  children: ReactNode;
}) {
  return (
    <div className="flex shrink-0 flex-col gap-0.5">
      <span
        aria-hidden
        className="pl-1.5 font-condensed text-micro uppercase text-muted-foreground"
      >
        {label}
      </span>
      <div className={cn("flex items-center", gap === "wide" ? "gap-1" : "gap-0.5")}>{children}</div>
    </div>
  );
}

function NavRule() {
  return <span aria-hidden className="mx-1 h-10 w-px shrink-0 self-end bg-border" />;
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
  busy,
  locked,
  rawStocked,
  rawWaiting,
  className,
}: {
  path: string;
  stages: StageState[];
  /** One flag per step of `STEPS`: whether work is running on it right now. */
  busy: boolean[];
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
        "min-w-0 items-center overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
    >
      <PhaseGroup label={t("nav.phase.build")}>
        {STEPS.map((step, index) => (
          <StepPill
            key={step.path}
            step={step}
            state={states[index]}
            n={stepNumber(index)}
            active={path === step.path}
            title={step.artifact === null && rawWaiting ? rawWaiting : undefined}
            busy={busy[index]}
          />
        ))}
      </PhaseGroup>

      <NavRule />

      <PhaseGroup label={t("nav.phase.test")} gap="wide">
        {USES.map((door) => (
          <DoorPill
            key={door.key}
            door={door}
            icon={door.key === "generate" ? Play : Scale}
            active={path === door.path}
            open={locked === null}
            disabledReason={locked}
          />
        ))}
      </PhaseGroup>
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

  // The tutorial's slide, read from the path: which parts of this header it has explained
  // so far, and therefore which are on offer. Null everywhere else.
  const tutorialAt = slideOf(path);
  const deck = tutorialAt !== null;

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
  // Where work is running right now, for the wheel on the bar. The stream's jobs are what
  // separate a build that is running from one still in the queue.
  const busy = stepBusy(
    stages,
    Object.values(stream.runs).flatMap((run) => (run.job ? [run.job] : [])),
  );

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
    // The deck is the one screen that is a fixed layout — a head, a scrolling column and
    // a foot — so under it the wrapper is a definite height and `main` a flex column with
    // no padding, where the two rails can reach the edges.
    <div className={cn("flex flex-col", deck ? "h-full" : "min-h-full")}>
      {/* NOTHING BUT THE SLIDES UNDER THE DECK (2026-09-04, explicit user request: «borra
          toda referencia del navbar del tutorial; borra las animaciones y oculta el
          navbar»). The header is not drawn at all while the tutorial runs, which reverses
          «the deck runs under the real header and the header unlocks as the deck goes» of
          2026-09-02: the silhouettes, the `--attention` rule under the group being
          explained and the `inert` that made the whole strip unpressable are gone with it,
          and so is `reveal.ts`. What the tutorial explains, it explains in words and in
          its own figures. */}
      {deck ? null : (
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
        <div className="mx-auto flex h-[4.5rem] w-full max-w-[1600px] items-center gap-2 px-3 sm:gap-4 sm:px-4">
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
              same «Todavía no tienes ninguna asignatura», so the bar was offering seven
              doors into one room — and to a student account, five of them are the
              teacher's preparation chain. `App` already gates the routes; this stops the
              navigation from advertising them. */}
          {hasWorkspace ? (
            <MainNav
              path={path}
              stages={stages}
              busy={busy}
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
            busy={busy}
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
      )}

      <main
        className={cn(
          deck
            ? "flex min-h-0 flex-1 flex-col"
            : "mx-auto w-full max-w-[1600px] flex-1 px-3 pb-8 pt-4 sm:px-4 sm:pt-6",
        )}
      >
        {children}
      </main>

    </div>
  );
}

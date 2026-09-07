import { useQueryClient } from "@tanstack/react-query";
import { Check, ChevronLeft, ChevronRight, Loader2, Play, Scale, Wrench } from "lucide-react";
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
 * The step's number, in a box whose stroke says where you stand.
 *
 * The strokes are the palette's frontier and not a traffic light: a fill in `--attention`
 * where you act, a dashed outline on what is not reachable yet, a bare tick on what is
 * behind you. The wheel of a running step is `--primary` plus motion, and it is
 * deliberately not switched off under `prefers-reduced-motion`: it is the one sign in the
 * bar that a build running for an hour is still alive.
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
        // A box says "there is something here to reach", so what is behind you carries
        // none. `COUNTER_BOX` stays either way, or the four stops stop lining up.
        state === "done" && "text-settled",
        state === "now"
          // The TOKEN and not its light-mode value: `--attention` is a light ground in dark
          // mode, so a literal puts a near-white number on it. `check:color` cannot see
          // this — it reads `index.css`, not a class in a component.
          ? "bg-attention text-attention-foreground"
          : null,
        state === "later" && "border border-dashed border-input text-muted-foreground",
      )}
    >
      {state === "done" ? <Check className="size-3.5" strokeWidth={3} aria-hidden /> : n}
    </span>
  );
}

// `min-w` and not a fixed square: "1" and an icon are the same height, and the height is
// what keeps the names of a row on one line.
const COUNTER_BOX = "flex h-[22px] min-w-[20px] shrink-0 items-center justify-center px-1";

/**
 * One stop of the path: its number, its name, and one word saying where you are.
 *
 * Two lines rather than one, and that is the "píldora bien explicada": the name alone is
 * a destination, while the name with "te toca ahora" under it is an instruction. It costs
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
  /** Work running on this step right now: the wheel, and "Construyendo" / "Leyendo" under the name. */
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
// The paddings are measured: at 1280 the flanks leave the strip 874 px and at `px-1.5` the
// six pills ask 857. Widening them overflows the row. The phase caption's `pl` is this
// `px`, since the two are one alignment.
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
 * An ICON where a step has its number, because the two doors have no order between them.
 * Both are gated on the whole construction being closed, which is why they sit under a
 * caption of their own rather than among the steps.
 *
 * While the construction is open a door is half off and answers no click: a `span` and not
 * a link, the reason in its `title`. A URL typed by hand still lands on `ChainGate`, which
 * names the stage in the way, so nothing is lost by the bar refusing. The name is centred
 * in a pill of the steps' own height, so nothing in the row moves when the doors open.
 *
 * "Evaluar el sistema" carries `--evaluation` locked or not: the tint says "this is a
 * different kind of thing", which is true from wherever you look at it.
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
 * The caption carries the phase, which has no number. Its `pl-1.5` is the pills' own
 * `px-1.5`, so it starts exactly on the first pill's box edge.
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
 * Whether the person asked to keep the four steps on the bar once they are all done.
 *
 * A per-browser convenience and not a setting: `localStorage`, guarded like `vg.theme`,
 * absent by default — which is the folded state — and "open" once somebody unfolds them.
 */
const STEPS_KEY = "vg.buildSteps";

function readStepsPreference(): boolean {
  try {
    return localStorage.getItem(STEPS_KEY) === "open";
  } catch {
    return false;
  }
}

function writeStepsPreference(open: boolean) {
  try {
    if (open) localStorage.setItem(STEPS_KEY, "open");
    else localStorage.removeItem(STEPS_KEY);
  } catch {
    // A browser that refuses site data still gets the session's own state.
  }
}

/**
 * The construction phase, folded into one pill once its four steps are done.
 *
 * Four stops with nothing left to do were most of the bar for the whole life of a subject,
 * and at 1280 px they pushed "Evaluar el sistema" past the edge of the strip. The same
 * two-line pill as a step, so unfolding moves nothing vertically.
 */
function FoldedPhase({ onUnfold }: { onUnfold: () => void }) {
  const { t } = useT();
  return (
    <button
      type="button"
      onClick={onUnfold}
      title={t("nav.build.unfold")}
      className={cn(PILL, PILL_HEIGHT, "text-left")}
    >
      <span className={cn(PILL_NAME, "font-medium text-foreground")}>
        <StepCounter state="done" n="" />
        {t("nav.build.folded")}
      </span>
      <span className={cn(PILL_WORD, "text-muted-foreground")}>
        {t("nav.build.unfold")}
        <ChevronRight className="size-3" strokeWidth={2.5} aria-hidden />
      </span>
    </button>
  );
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
  stepsOpen,
  onSteps,
  className,
}: {
  path: string;
  stages: StageState[];
  /** One flag per step of `STEPS`: whether work is running on it right now. */
  busy: boolean[];
  locked: string | null;
  /** Whether both origins hold documents, which is what "paso 1 hecho" means. */
  rawStocked: boolean;
  /** What is still untranscribed, or null. A hint on step 1 and never a gate. */
  rawWaiting: string | null;
  /** Whether the person asked to keep the four steps on the bar. Owned by `AppShell`:
   *  this navigation is mounted twice, one instance per breakpoint, so a `useState` here
   *  would be two states over one `localStorage` key. */
  stepsOpen: boolean;
  onSteps: (open: boolean) => void;
  className?: string;
}) {
  const { t } = useT();
  // Whether the strip is cut off on the right, so the fade below can say so. Its scrollbar
  // is hidden on purpose, so without this nothing suggests the row continues.
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

  // Folded once everything is done, unless the person unfolded it or is standing on one of
  // the steps — a bar that hides the stop you are on says you are nowhere.
  const allDone = stages.length > 0 && states.every((state) => state === "done");
  const onStep = STEPS.some((step) => step.path === path);
  const folded = allDone && !stepsOpen && !onStep;

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
        {folded ? (
          <FoldedPhase onUnfold={() => onSteps(true)} />
        ) : (
          <>
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
            {/* Drawn only where pressing it folds something: with a step pending, or while
                standing on one, it would answer a press with nothing at all. */}
            {allDone && !onStep ? (
              <button
                type="button"
                onClick={() => onSteps(false)}
                title={t("nav.build.fold")}
                aria-label={t("nav.build.fold")}
                className={cn(
                  PILL_HEIGHT,
                  "flex shrink-0 items-center rounded-md px-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                )}
              >
                <ChevronLeft className="size-4" strokeWidth={2.25} aria-hidden />
              </button>
            ) : null}
          </>
        )}
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

  // The tutorial's slide, read from the path; null everywhere else.
  const tutorialAt = slideOf(path);
  const deck = tutorialAt !== null;

  // Not opened while the account is in no workspace: the handshake resolves a membership
  // like every route does, so it would only be refused — and a refusal reads as "la
  // sesión ha caducado", which is the one thing that is not happening here.
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

  const offline = health.data && !health.data.available;
  const missingModels = health.data?.models.missing ?? [];

  // Both doors are gated by the same condition — the whole chain approved — so the reason
  // is derived once and handed to both pills.
  const locked = (pipeline.data?.generation_unlocked ?? false)
    ? null
    : t("nav.needsApproved");

  // A hint and not a gate — the builds run anyway — so it is a tooltip and never a
  // `disabledReason`. Only asked inside a workspace; with none the queries would 403.
  const rawSlots = raw.data?.slots ?? [];
  const rawSummary = useTranscriptionSummary(hasWorkspace ? rawSlots : []);
  const rawWaiting =
    rawSummary.todo > 0 ? t("nav.rawWaiting", { n: rawSummary.todo }) : null;
  // What "step 1 done" means: both origins hold something. Never the transcription, which
  // is an accelerator and not a gate.
  const rawStocked =
    rawSlots.length > 0 && rawSlots.every((slot) => slot.files.length > 0);

  // One preference for both copies of the bar: `MainNav` is rendered twice, each hidden by
  // CSS at the other's breakpoint, so the state cannot live inside it.
  const [stepsOpen, setStepsOpen] = useState(readStepsPreference);
  const setSteps = (open: boolean) => {
    setStepsOpen(open);
    writeStepsPreference(open);
  };

  return (
    // The deck is the one screen that is a fixed layout — a head, a scrolling column and
    // a foot — so under it the wrapper is a definite height and `main` a flex column with
    // no padding, where the two rails can reach the edges.
    <div className={cn("flex flex-col", deck ? "h-full" : "min-h-full")}>
      {/* Nothing but the slides under the deck: the header is not drawn at all while the
          tutorial runs. What it explains, it explains in words and in its own figures. */}
      {deck ? null : (
      <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
        {/* Three columns, and the middle one is the centre of the header: the flanks are
            `flex-1 basis-0`, so they are always the same width and the nav lands on the
            centre line whatever they contain. The nav is the only item that may shrink,
            being the only one with a scroller to absorb the squeeze.
            The flanks carry NO `min-w-0`, and that is load-bearing: with `min-width: 0`
            they grow to nothing and their contents paint OUTSIDE the box, one flank over
            the other. `min-width: auto` holds each at its own min-content, which is
            bounded — the lockup is fixed and the switcher is `max-w-44` and truncates. */}
        <div className="mx-auto flex h-[4.5rem] w-full max-w-[1600px] items-center gap-2 px-3 sm:gap-4 sm:px-4">
          {/* `compact` drops the wordmark below `lg`. The rule that separates the product's
              name from the subject's is the SWITCHER's own, and goes with it: with nothing
              to switch between there is nothing to separate. */}
          <div className="flex flex-1 basis-0 items-center gap-2 sm:gap-3">
            <Link
              to="/"
              aria-label="Variatio" // i18n-exempt: es el nombre del producto
              className="shrink-0"
            >
              <Lockup compact />
            </Link>

            <WorkspaceSwitcher />
          </div>

          {/* Nothing to navigate without a subject: all six destinations render the same
              "Todavía no tienes ninguna asignatura". `App` already gates the routes; this
              stops the navigation from advertising them. */}
          {hasWorkspace ? (
            <MainNav
              path={path}
              stages={stages}
              busy={busy}
              locked={locked}
              rawWaiting={rawWaiting}
              rawStocked={rawStocked}
              stepsOpen={stepsOpen}
              onSteps={setSteps}
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
            stepsOpen={stepsOpen}
            onSteps={setSteps}
            className="flex border-t border-border px-3 py-1.5 xl:hidden"
          />
        ) : null}

        {/* Whoever sees this is the account that closed the door — everybody else is
            looking at the notice — so it is a reminder, not a warning. */}
        {maintenance.data?.active ? (
          <div className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1 border-t border-border bg-[color-mix(in_oklch,var(--destructive)_12%,transparent)] px-3 py-1.5 text-center text-small sm:px-4">
            <Wrench className="size-3.5 shrink-0" />
            <span>{t("shell.maintenance")}</span>
            <Link to="/admin" className="font-medium underline underline-offset-4">
              {t("shell.reopen")}
            </Link>
          </div>
        ) : null}

        {/* The consequence goes in the sentence itself: a warning one has to open in order
            to understand is not a warning. */}
        {offline || missingModels.length > 0 ? (
          <div className="flex items-start justify-center gap-1.5 border-t border-border bg-[color-mix(in_oklch,var(--attention)_12%,transparent)] px-3 py-1.5 text-center text-small sm:items-center sm:px-4">
            {/* Neither the host nor the model names belong here: the strip says what does
                not work, and the detail is "Administración → Motor"'s, where one acts. */}
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

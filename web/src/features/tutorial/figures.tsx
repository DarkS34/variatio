import { ArrowRight, Check, ChevronDown, FileText, Sparkles, User } from "lucide-react";
import { Fragment } from "react";

import { Logo } from "@/components/ui/logo";
import { useT, type Key } from "@/lib/i18n";
import { STEPS, stepNumber } from "@/lib/steps";
import { cn } from "@/lib/utils";

/**
 * THE PICTURES THE TUTORIAL EXPLAINS ITSELF WITH.
 *
 * Two rules, and they are the palette's own. Everything here is drawn in the ink — boxes,
 * rules, arrows, labels — and the ONE thing a slide is about is the only thing carrying
 * `--attention`. A figure with two coloured elements has stopped pointing at anything.
 *
 * And they are drawn out of the app's own sources, never hand-copied: the bar is built
 * from `STEPS` and numbered with `stepNumber`, the same list and the same numbering the
 * real navigation draws, so the picture of the path cannot promise an order the path does
 * not have. That is what makes it worth drawing at all — somebody is about to look for
 * these four names on a screen they have never seen.
 *
 * A FIGURE HAS TO READ ON ITS OWN, and where it does the paragraph under it says
 * something else. A drawing that enumerates and a paragraph that enumerates the same
 * things is one thing said twice, which is what the flow and the two document piles used
 * to be — so their labels are full sentences now and the prose beside them is shorter.
 */

/** A labelled box: the unit every figure here is made of. */
function Box({
  children,
  marked = false,
  className,
}: {
  children: React.ReactNode;
  marked?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        // `justify-center` y no sólo `items-center`: las cajas de una fila se estiran a la
        // altura de la más alta, así que una con menos dentro dejaba su texto pegado
        // arriba. Es lo que se veía en la diapositiva de «los cuatro terminan igual».
        "flex min-w-0 flex-col items-center justify-center gap-1.5 border px-3 py-2.5 text-center",
        marked
          ? "border-attention bg-[color-mix(in_oklch,var(--attention)_8%,transparent)]"
          : "border-border bg-card",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * A CHAIN OF BOXES: down the page on a phone, across it once there is room.
 *
 * The labels are sentences now, and three or four of them squeezed into columns 90 px wide
 * are a stack of single words — which is what a narrow screen does to a row of `flex-1`
 * cells. Stacked, each sentence gets the whole width, and the arrow turns with the layout
 * so the chain still reads as a chain rather than as a list.
 */
function Chain({ children }: { children: React.ReactNode[] }) {
  return (
    <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:gap-2.5">
      {children.map((box, index) => (
        <Fragment key={index}>
          {index > 0 ? (
            <span className="flex shrink-0 items-center justify-center">
              <ArrowRight
                aria-hidden
                className="size-4 rotate-90 text-muted-foreground sm:rotate-0"
              />
            </span>
          ) : null}
          <div className="flex min-w-0 sm:flex-1">{box}</div>
        </Fragment>
      ))}
    </div>
  );
}

/**
 * THE BAR, WITH ONE STOP MARKED.
 *
 * It is doing the work of a sentence that would otherwise have to be written on every
 * slide: «this is where you will find it». The marked stop is the step the slide is
 * about; with `active` unset nothing is marked and it is the whole path at once, which is
 * the index slide's own picture.
 *
 * The numbers are `stepNumber`'s, so they read 1.1 to 1.4 — the four are one phase, and a
 * figure numbering them 1 to 4 would promise a shape the navigation does not have.
 */
export function NavFigure({ active }: { active?: number }) {
  const { t } = useT();
  return (
    <div
      // A drawing of a control, not a control: nothing here is reachable, and a screen
      // reader that walked it would announce four destinations that go nowhere.
      aria-hidden
      className="flex items-stretch gap-px overflow-hidden border border-border bg-card"
    >
      <div className="flex shrink-0 items-center gap-1.5 border-r border-border px-2.5 py-2">
        <Logo className="size-3.5 text-foreground" />
      </div>
      {STEPS.map((step, index) => {
        const marked = active === index + 1;
        return (
          <div
            key={step.path}
            className={cn(
              "flex min-w-0 flex-1 items-center gap-1.5 px-2 py-2",
              marked && "bg-[color-mix(in_oklch,var(--attention)_10%,transparent)]",
            )}
          >
            <span
              className={cn(
                // `min-w` and not a square: «1.1» is wider than «1», exactly as the real
                // bar's own counter had to become.
                "nums flex h-[18px] min-w-[18px] shrink-0 items-center justify-center px-1 font-condensed text-[10px] font-semibold",
                marked
                  ? "bg-attention text-attention-foreground"
                  : "border border-dashed border-input text-muted-foreground",
              )}
            >
              {stepNumber(index)}
            </span>
            <span
              className={cn(
                "min-w-0 truncate text-small",
                marked ? "font-semibold text-foreground" : "text-muted-foreground",
              )}
            >
              {t(step.labelKey)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * WHO DOES WHAT: the whole product in one line.
 *
 * The three labels are SENTENCES WITH A SUBJECT and not noun phrases, because the first
 * question somebody has here is who is expected to do what — «tus apuntes» does not say
 * whether they are wanted or produced. The person is drawn in the first box for the same
 * reason: the pile of documents is theirs, and it is the only box the reader has to act on.
 */
export function FlowFigure() {
  const { t } = useT();
  return (
    <Chain>
      {[
        <Box key="yours" className="w-full">
          <span aria-hidden className="flex items-center gap-1 text-muted-foreground">
            <User className="size-4" />
            <FileText className="size-4" />
          </span>
          <span className="text-small">{t("tutorial.fig.yours")}</span>
        </Box>,
        <Box key="learns" className="w-full">
          <Logo className="size-4 text-foreground" />
          <span className="text-small">{t("tutorial.fig.learns")}</span>
        </Box>,
        <Box key="new" marked className="w-full">
          <Sparkles aria-hidden className="size-4 text-attention" />
          <span className="text-small font-medium">{t("tutorial.fig.new")}</span>
        </Box>,
      ]}
    </Chain>
  );
}

/**
 * The two piles of documents, side by side, because they are two answers to one question.
 *
 * Each box is titled with the NAME OF THE DROP ZONE it will be dropped into, from
 * `raw.slot.*` — the same string the screen of step 1.1 draws — so the figure is already
 * pointing at where the files go rather than describing them a second time.
 */
export function SourcesFigure() {
  const { t } = useT();
  const piles: { title: Key; body: Key }[] = [
    { title: "raw.slot.corpus", body: "tutorial.fig.notes" },
    { title: "raw.slot.exemplars", body: "tutorial.fig.exercises" },
  ];
  return (
    <div className="grid gap-2.5 sm:grid-cols-2">
      {piles.map(({ title, body }) => (
        <Box key={title} className="items-start gap-2 text-left">
          <span className="flex items-center gap-1.5 text-small font-semibold">
            <FileText aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            {t(title)}
          </span>
          <span className="text-small text-muted-foreground">{t(body)}</span>
        </Box>
      ))}
    </div>
  );
}

/**
 * THE HINGE BETWEEN THE TWO PHASES: three things given as good, and then you can ask.
 *
 * The three names are read from `artifact.*`, which is what the stage headers and the bar
 * call them, so the picture of «what you have to have validated» cannot drift from the
 * screens where the validating happens. Step 1.1 is deliberately not among them: it is
 * the one step nobody approves — you either have documents or you do not.
 */
export function PhasesFigure() {
  const { t } = useT();
  const validated: Key[] = ["artifact.profile", "artifact.graph", "artifact.bank"];
  return (
    <Chain>
      {[
        <Box key="phase1" className="w-full items-start gap-2 text-left">
          <span className="text-small text-muted-foreground">{t("tutorial.fig.phase1")}</span>
          <span className="flex flex-col gap-1">
            {validated.map((key) => (
              <span key={key} className="flex items-center gap-1.5 text-small">
                <Check aria-hidden className="size-3.5 shrink-0 text-settled" strokeWidth={3} />
                {t(key)}
              </span>
            ))}
          </span>
        </Box>,
        <Box key="phase2" marked className="w-full">
          <Sparkles aria-hidden className="size-4 text-attention" />
          <span className="text-small font-medium">{t("tutorial.fig.phase2")}</span>
        </Box>,
      ]}
    </Chain>
  );
}

/**
 * HOW EVERY STEP GOES, in four beats.
 *
 * The marked one is «lo valoras», which is the only beat the reader is being asked for:
 * the other three are what the step does around it. It is the contract the tutorial states
 * once — each step announces this before it happens — rather than repeating it four times.
 */
export function CloseFigure() {
  const { t } = useT();
  const beats: { key: Key; marked?: boolean }[] = [
    { key: "tutorial.fig.build" },
    { key: "tutorial.fig.review" },
    { key: "tutorial.fig.rate", marked: true },
    { key: "tutorial.fig.next" },
  ];
  return (
    <Chain>
      {beats.map(({ key, marked }) => (
        <Box key={key} marked={marked} className="w-full px-2">
          {marked ? <Check aria-hidden className="size-4 text-attention" /> : null}
          <span className={cn("text-small", marked && "font-medium")}>{t(key)}</span>
        </Box>
      ))}
    </Chain>
  );
}

/**
 * The header's right flank, with «Mis variantes» marked.
 *
 * Drawn because the pill is the one destination in the whole application that is not on
 * the path and not in a menu, so the only way somebody finds it is by having been shown
 * where it is.
 */
export function VariantsFigure() {
  const { t } = useT();
  return (
    <div aria-hidden className="flex items-center justify-end gap-2 border border-border bg-card p-2">
      <span className="mr-auto text-small text-muted-foreground">
        {t("tutorial.fig.headerRight")}
      </span>
      <span className="border border-attention bg-[color-mix(in_oklch,var(--attention)_10%,transparent)] px-2.5 py-1 text-small font-medium">
        {t("nav.myVariants")}
      </span>
      <span className="flex size-7 items-center justify-center rounded-full border border-border text-muted-foreground">
        <span className="size-3 rounded-full border border-current" />
      </span>
    </div>
  );
}

/** Three proposals, none of them named until you have chosen. */
export function BlindFigure() {
  const { t } = useT();
  return (
    <div className="grid gap-2.5 sm:grid-cols-3">
      {["A", "B", "C"].map((letter) => (
        <Box key={letter} className="items-start gap-2 text-left">
          <span className="text-micro text-muted-foreground">
            {t("tutorial.fig.proposal", { letter })}
          </span>
          <span className="flex w-full flex-col gap-1" aria-hidden>
            <span className="h-1 w-full bg-border" />
            <span className="h-1 w-4/5 bg-border" />
            <span className="h-1 w-2/3 bg-border" />
          </span>
        </Box>
      ))}
    </div>
  );
}

/**
 * The header's LEFT flank, with the workspace control marked.
 *
 * The last slide asks somebody to pick the subject they are going to work with, and the
 * control that does it is a button they have never seen carrying a caption they have
 * never read. Drawing it is cheaper than a sentence describing where to look, and the
 * caption is `workspace.switcher.label` — the same string the real control paints, so a
 * rename cannot leave the tutorial pointing at a word that is no longer there.
 */
export function WorkspaceFigure() {
  const { t } = useT();
  return (
    <div aria-hidden className="flex items-center gap-2 border border-border bg-card p-2">
      <Logo className="size-4 shrink-0 text-foreground" />
      <span className="flex min-w-0 items-center gap-1.5 border border-attention bg-[color-mix(in_oklch,var(--attention)_10%,transparent)] px-2 py-1">
        <span className="min-w-0 text-left">
          <span className="block truncate text-[11px] font-medium uppercase leading-none tracking-wide text-muted-foreground">
            {t("workspace.switcher.label")}
          </span>
          <span className="mt-1 block truncate text-small font-medium leading-tight">
            {t("tutorial.fig.workspace")}
          </span>
        </span>
        <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
      </span>
      <span className="ml-auto text-small text-muted-foreground">
        {t("tutorial.fig.headerLeft")}
      </span>
    </div>
  );
}

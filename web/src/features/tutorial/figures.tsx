import {
  ArrowRight,
  Check,
  ChevronDown,
  FileText,
  Sparkles,
  User,
  UserRound,
} from "lucide-react";
import { Fragment } from "react";

import { Lockup, Logo } from "@/components/ui/logo";
import { useT, type Key } from "@/lib/i18n";
import { COMPARE_PHASE, GENERATE_PHASE, STEPS, stepNumber } from "@/lib/steps";
import { useSession } from "@/state/auth";
import { cn } from "@/lib/utils";

/**
 * THE SIZE EVERY SENTENCE OF THE TUTORIAL IS SET AT, and the face it is set in.
 *
 * It lives here rather than in the screen because a figure contains sentences too — the
 * two piles of documents on slide 2 are described in prose, not labelled — and the rule
 * they follow is the one that separates this whole file from the screen beside it: a
 * LABEL QUOTED FROM THE APP is drawn in the app's own face at the app's own size, because
 * it is a picture of something the reader is about to go and look at; a SENTENCE WRITTEN
 * FOR THE READER is set in the reading face at the reading size, wherever it happens to
 * sit. Mixing those two up is what made slide 2 read as a diagram with a caption when it
 * is two answers to one question — and what made the first slide's three moments and the
 * last slide's four beats read as footnotes to their own paragraph (2026-09-02): they
 * were sentences for the reader drawn at 12 and 14 px under 21 px of prose.
 */
export const PROSE = "font-reading text-[1.1875rem] leading-[1.65] sm:text-[1.3125rem]";

/** A sentence inside a figure: the reading face, set a little tighter because it wraps in a box. */
const FIGURE_PROSE = "font-reading text-[1.1875rem] leading-[1.4] sm:text-[1.3125rem]";

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

/**
 * A labelled box: the unit every figure here is made of.
 *
 * `bare` drops the frame and the ground and keeps only the layout. A box says «this is a
 * thing with an edge» — a drop zone, a card, a proposal — and where there is no edge in
 * the product there should be none in the drawing either: the first slide's three moments
 * are a story, not three containers, and framing them made the opening picture read as a
 * form. What still separates them there is the arrow, which is the only thing that was
 * ever doing the work.
 */
function Box({
  children,
  marked = false,
  bare = false,
  className,
}: {
  children: React.ReactNode;
  marked?: boolean;
  bare?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        // `justify-center` y no sólo `items-center`: las cajas de una fila se estiran a la
        // altura de la más alta, así que una con menos dentro dejaba su texto pegado
        // arriba. Es lo que se veía en la diapositiva de «los cuatro terminan igual».
        "flex min-w-0 flex-col items-center justify-center gap-2 text-center",
        !bare && "border px-3 py-4",
        !bare && marked
          ? "border-attention bg-[color-mix(in_oklch,var(--attention)_8%,transparent)]"
          : null,
        !bare && !marked && "border-border bg-card",
        bare && "px-2 py-2",
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
    <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:gap-3">
      {children.map((box, index) => (
        <Fragment key={index}>
          {index > 0 ? (
            <span className="flex shrink-0 items-center justify-center">
              <ArrowRight
                aria-hidden
                className="size-5 rotate-90 text-muted-foreground sm:rotate-0"
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
              "flex min-w-0 flex-1 items-center gap-1.5 px-2 py-2.5",
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
                // Numbers only on a phone: four names truncated to their first letter say
                // nothing, and the header figure already draws the row that way.
                "hidden min-w-0 truncate text-small sm:inline",
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
    <div className="py-4">
      <Chain>
        {[
          <Box key="yours" bare className="w-full gap-3">
            <span aria-hidden className="flex items-center gap-1.5 text-muted-foreground">
              <User className="size-7" />
              <FileText className="size-7" />
            </span>
            <span className={cn(FIGURE_PROSE, "text-muted-foreground")}>
              {t("tutorial.fig.yours")}
            </span>
          </Box>,
          <Box key="learns" bare className="w-full gap-3">
            <Logo className="size-7 text-foreground" />
            <span className={cn(FIGURE_PROSE, "text-muted-foreground")}>
              {t("tutorial.fig.learns")}
            </span>
          </Box>,
          <Box key="new" bare marked className="w-full gap-3">
            <Sparkles aria-hidden className="size-7 text-attention" />
            <span className={cn(FIGURE_PROSE, "font-semibold text-foreground")}>
              {t("tutorial.fig.new")}
            </span>
          </Box>,
        ]}
      </Chain>
    </div>
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
    <div className="grid gap-3 sm:grid-cols-2">
      {piles.map(({ title, body }) => (
        <Box key={title} className="items-start justify-start gap-3 p-4 text-left">
          <span className="flex items-center gap-1.5 text-small font-semibold uppercase tracking-wide text-muted-foreground">
            <FileText aria-hidden className="size-4 shrink-0" />
            {t(title)}
          </span>
          <span className={PROSE}>{t(body)}</span>
        </Box>
      ))}
    </div>
  );
}

/**
 * WHAT ASKING FOR AN EXERCISE ACTUALLY LOOKS LIKE.
 *
 * It replaces a drawing of the hinge — three ticked artifacts with «Fase 2» beside them —
 * which said in a picture exactly what the slide's own title now says in words, and left
 * the reader's real question unanswered: «and what do I have to give it?». Three chips and
 * an arrow. The three are the generate form's OWN questions, read from `form.*.title`, so
 * they are the words on the screen the reader is about to open and cannot drift from it.
 */
export function AskFigure() {
  const { t } = useT();
  const asked: Key[] = ["form.type.title", "form.practise.title", "form.difficulty.title"];
  return (
    <Chain>
      {[
        <Box key="ask" className="w-full items-start gap-3 p-5 text-left">
          <span className="text-small font-semibold uppercase tracking-wide text-muted-foreground">
            {t("tutorial.fig.youAsk")}
          </span>
          <span className="flex flex-wrap gap-2">
            {asked.map((key) => (
              <span key={key} className="border border-input px-2.5 py-1.5 text-body">
                {t(key)}
              </span>
            ))}
          </span>
        </Box>,
        <Box key="item" marked className="w-full gap-3 p-5">
          <Sparkles aria-hidden className="size-7 text-attention" />
          <span className={cn(FIGURE_PROSE, "font-semibold")}>{t("tutorial.fig.written")}</span>
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
 * The prose beside it therefore does NOT walk the four beats again (2026-09-02): it says
 * what the picture cannot, that correcting is optional and that a hand correction wins.
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
        <Box key={key} marked={marked} className="w-full px-3 py-5">
          {marked ? <Check aria-hidden className="size-5 text-attention" /> : null}
          <span className={cn(FIGURE_PROSE, marked && "font-semibold")}>{t(key)}</span>
        </Box>
      ))}
    </Chain>
  );
}

/**
 * Three proposals, none of them named until you have chosen.
 *
 * The label is `grid.proposal`, the comparison screen's own, so the card the reader will
 * see is headed with the very words drawn here.
 */
export function BlindFigure() {
  const { t } = useT();
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {["A", "B", "C"].map((letter) => (
        <Box key={letter} className="items-start gap-3 p-4 text-left">
          <span className="text-small font-semibold uppercase tracking-wide text-muted-foreground">
            {t("grid.proposal", { letter })}
          </span>
          <span className="flex w-full flex-col gap-1.5" aria-hidden>
            <span className="h-1.5 w-full bg-border" />
            <span className="h-1.5 w-4/5 bg-border" />
            <span className="h-1.5 w-2/3 bg-border" />
          </span>
        </Box>
      ))}
    </div>
  );
}

/**
 * THE HEADER, DRAWN AS IT ACTUALLY IS, with the one control the last slide asks for marked.
 *
 * It replaces two figures that each drew half of this row, and one of them had gone false:
 * «Mis variatios» was a pill in the right flank when it was drawn and is an entry of the
 * account menu now, so the tutorial was pointing at a button that is not there. Drawing
 * the whole row fixes that by construction — there is one picture of the header and it is
 * the header — and it answers the two questions the closing slide leaves: where the
 * subject is chosen, and where everything the reader will need afterwards lives.
 *
 * THE TWO NAMES ARE THE READER'S OWN, read out of the session the gate already filled.
 * Somebody who has just redeemed an invitation is being shown where their subject and
 * their account are, and a drawing of somebody else's is a worse picture than a drawing of
 * theirs. An account that is a member of nothing falls back to `workspace.none`, which is
 * the string its real header is showing at that very moment — so this is not an
 * illustration of the header, it is the header.
 *
 * ONE `--attention`, on the subject switcher: it is the only thing on the row the reader
 * has to act on now. The account pill is drawn in its own ink and named in the prose.
 */
export function HeaderFigure() {
  const { t } = useT();
  const session = useSession().data;
  const username = session?.user.username;
  const workspace = session?.workspaces.find((row) => row.active)?.name;
  return (
    <div
      aria-hidden
      className="flex items-center gap-2 overflow-hidden border border-border bg-card px-2.5 py-2"
    >
      <Lockup compact className="shrink-0" />
      <span className="h-6 w-px shrink-0 bg-border" />
      <span className="flex min-w-0 shrink items-center gap-1.5 border border-attention bg-[color-mix(in_oklch,var(--attention)_10%,transparent)] px-2 py-1">
        <span className="min-w-0 text-left">
          <span className="block truncate text-[11px] font-medium uppercase leading-none tracking-wide text-muted-foreground">
            {t("workspace.switcher.label")}
          </span>
          <span className="mt-1 block truncate text-small font-medium leading-tight">
            {workspace ?? t("workspace.none")}
          </span>
        </span>
        <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
      </span>
      <span className="mx-auto hidden shrink items-center gap-2.5 md:flex">
        {[...STEPS.map((_, index) => stepNumber(index)), `${GENERATE_PHASE}`, `${COMPARE_PHASE}`].map(
          (label) => (
            <span
              key={label}
              className="nums font-condensed text-small font-semibold text-muted-foreground"
            >
              {label}
            </span>
          ),
        )}
      </span>
      <span className="ml-auto flex h-8 shrink-0 items-center gap-1.5 rounded-full border border-border bg-secondary pl-0.5 pr-0.5 sm:pr-3">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <UserRound aria-hidden className="size-4" />
        </span>
        <span className="hidden truncate text-small font-medium sm:block">
          {username ?? t("tutorial.fig.you")}
        </span>
      </span>
    </div>
  );
}

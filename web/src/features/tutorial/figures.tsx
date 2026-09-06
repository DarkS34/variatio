import { ArrowRight, Check, FileText, Sparkles, User } from "lucide-react";
import { Fragment } from "react";

import { Logo } from "@/components/ui/logo";
import { useT, type Key } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * The size every sentence of the tutorial is set at, and the face it is set in.
 *
 * It lives here and not in the screen because a figure contains sentences too, and the rule
 * is what separates this file from the screen beside it: a LABEL QUOTED FROM THE APP is
 * drawn in the app's own face at its own size, being a picture of something the reader is
 * about to go and look at, while a SENTENCE WRITTEN FOR THE READER is set in the reading
 * face wherever it sits. Mixing the two makes a figure's own prose read as a footnote to
 * the paragraph beside it.
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
 * `bare` drops the frame and the ground and keeps only the layout. A box says "this is a
 * thing with an edge" — a drop zone, a card, a proposal — and where there is no edge in
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
        // `justify-center` and not only `items-center`: the boxes of a row stretch to the
        // height of the tallest, so one with less inside leaves its text against the top.
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
 * WHO DOES WHAT: the whole product in one line.
 *
 * The three labels are SENTENCES WITH A SUBJECT and not noun phrases, because the first
 * question somebody has here is who is expected to do what — "tus apuntes" does not say
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
 * `raw.slot.*` — the same string the screen of step 1 draws — so the figure is already
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
 * It replaces a drawing of the hinge — three ticked artifacts with "Fase 2" beside them —
 * which said in a picture exactly what the slide's own title now says in words, and left
 * the reader's real question unanswered: "and what do I have to give it?". Three chips and
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
 * How every step goes, in four beats.
 *
 * The marked one is "lo valoras", the only beat the reader is being asked for; the other
 * three are what the step does around it. The prose beside it does NOT walk the four beats
 * again — it says what the picture cannot, that correcting is optional and that a hand
 * correction wins.
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


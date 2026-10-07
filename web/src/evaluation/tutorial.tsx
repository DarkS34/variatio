import "./i18n";

import { Check } from "lucide-react";

import { Box, Chain, FIGURE_PROSE } from "@/features/tutorial/figures";
import type { Slide, SlideIdOf } from "@/features/tutorial/slides";
import { useT, type Key } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * The tutorial's two slides about the study: what evaluating is, and the part a participant
 * plays in it.
 *
 * The evaluation's own code, so the tutorial fetches them only for an account the evaluation
 * is open to (`TutorialScreen`'s `useStudySlides`), and their figures and their prose arrive
 * with them. The deck's shape stays in `features/tutorial/slides.ts`, which types this table
 * by the ids it gives the evaluation.
 */
export const SLIDES: Record<SlideIdOf<"evaluation">, Slide> = {
  s5: {
    title: "tutorial.s5.title",
    body: "tutorial.s5.body",
    figure: <BlindFigure />,
    points: ["tutorial.s5.b1", "tutorial.s5.b3"],
    aside: "tutorial.s5.aside",
  },
  // What correcting a step means is the construction's slide (`tutorial.s3.b1`), which every
  // account is shown: here it would be said only to the study's participants.
  s6: {
    title: "tutorial.s6.title",
    body: "tutorial.s6.body",
    figure: <CloseFigure />,
  },
};

/**
 * How every step goes, in four beats.
 *
 * The marked one is "lo valoras", the only beat the reader is being asked for; the other
 * three are what the step does around it. The prose beside it does NOT walk the four beats
 * again.
 */
function CloseFigure() {
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
 * The two proposals, neither of them named until you have chosen.
 *
 * Two and not three, because a session IS two cards: the system's proposal and the one
 * rival the seed draws. The label is `grid.proposal`, the comparison screen's own, so the
 * card the reader will see is headed with the very words drawn here.
 */
function BlindFigure() {
  const { t } = useT();
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {["A", "B"].map((letter) => (
        <Box key={letter} className="items-start gap-3 p-4 text-left">
          <span className="text-micro font-condensed uppercase text-muted-foreground">
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

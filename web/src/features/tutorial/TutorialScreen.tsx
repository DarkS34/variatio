import { ArrowRight } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { useT, type Key } from "@/lib/i18n";
import { Link, useRouter } from "@/lib/router";
import { STEPS, stepNumber } from "@/lib/steps";
import { cn } from "@/lib/utils";

import {
  BlindFigure,
  CloseFigure,
  FlowFigure,
  NavFigure,
  PhasesFigure,
  SourcesFigure,
  VariantsFigure,
  WorkspaceFigure,
} from "./figures";

/**
 * EIGHT SCREENS, AND THEY ARE THE MANUAL.
 *
 * Somebody who has just redeemed an invitation has never seen this and does not know what
 * the thing is called, so the first sentence is a definition — name, category, what it is
 * for — and every negation comes after it. Leaving here they have to be able to use the
 * whole thing without asking anybody: what it is, what it needs from them before they
 * start, the four steps of preparing a subject, what having finished them buys, how an
 * exercise is asked for, how the blind comparison works, and what is being asked of them
 * as an evaluator.
 *
 * ONE PASS OVER THE PATH, NOT TWO. The deck used to show the four steps as an index and
 * then again as one slide each, which is the same content twice with the second copy
 * adding a sentence apiece. The index is the only pass now: with the four numbered 1.1 to
 * 1.4 inside one phase, what a person needs is the shape of the phase and not four
 * paragraphs about its parts. What the individual slides carried that the index did not is
 * folded into the index entries.
 *
 * AND THE DECK ENDS BY TURNING INTO THE STUDY. Slides one to six explain the product;
 * seven says that what comes next is an evaluation and states the one contract that
 * governs every step — it tells you what is about to happen, it happens, you look at it,
 * you rate it, and you can always correct — and eight is the door: pick a subject, start
 * at 1.1.
 *
 * Every slide carries a FIGURE. They are in `figures.tsx`, drawn in the ink with a single
 * `--attention` on the one thing the slide is about, and the bar is built from `STEPS` and
 * numbered with `stepNumber` — the same list and the same numbering the navigation reads —
 * so the picture cannot promise an order the path does not have. Where a figure enumerates,
 * the prose beside it does not: a drawing and a paragraph listing the same two things is
 * one thing said twice.
 *
 * The content is vertically centred rather than pinned to the top: a slide is two
 * paragraphs and a drawing, and hung from the top of a tall window it reads as a page that
 * failed to finish loading. It centres only while it FITS — the column scrolls when it does
 * not, which is normal now that everything is set at one size.
 *
 * ONE SIZE FOR EVERY SENTENCE (2026-09-01, explicit user request). The lead was `heading`,
 * the points `body` and the aside `small`, so three sentences that are equally true were
 * drawn at three sizes and read as three degrees of importance. They are all `heading` at
 * normal weight now; only the title above them is larger, because it is a title. The slides
 * got taller and that is the accepted cost — «no pasa nada que ocupe un poco más».
 *
 * AND THE NAV NEVER MOVES. It is a footer of its own, outside the scrolling column, so the
 * two buttons sit at the same pixel on every slide: measured before, the primary button
 * wandered between y=575 and y=789 because it followed the content, «Atrás» was missing on
 * the first slide, and the last slide's label is longer than «Siguiente» so it shifted
 * sideways too. «Atrás» is now always rendered (invisible on the first) and both buttons
 * have a floor on their width.
 *
 * It is not a gate. «Saltar la explicación» is on every slide and the account menu leads
 * back, because a person who has understood should not have to page through it and one who
 * skipped too fast should be able to return. Nothing is recorded about whether it was
 * read: making it a state to track would make it a chore to finish.
 */

interface Slide {
  title: Key;
  /** The lead, set one step larger than body text: it is the sentence of the slide. */
  body: Key;
  figure?: ReactNode;
  /** Short paragraphs under the figure, each its own point. */
  points?: Key[];
  /** One aside, set apart: the thing that is true but is not an instruction. */
  aside?: Key;
  /** Only the index slide: the four steps of the first phase, as a numbered list. */
  steps?: boolean;
}

const STEP_BODIES: Key[] = [
  "tutorial.s3.step1",
  "tutorial.s3.step2",
  "tutorial.s3.step3",
  "tutorial.s3.step4",
];

const SLIDES: Slide[] = [
  { title: "tutorial.s1.title", body: "tutorial.s1.body", figure: <FlowFigure /> },
  {
    title: "tutorial.s2.title",
    body: "tutorial.s2.body",
    figure: <SourcesFigure />,
    aside: "tutorial.s2.aside",
  },
  {
    title: "tutorial.s3.title",
    body: "tutorial.s3.body",
    figure: <NavFigure />,
    steps: true,
  },
  {
    title: "tutorial.s4.title",
    body: "tutorial.s4.body",
    figure: <PhasesFigure />,
    points: ["tutorial.s4.b1"],
  },
  {
    title: "tutorial.s5.title",
    body: "tutorial.s5.body",
    figure: <VariantsFigure />,
    points: ["tutorial.s5.b1", "tutorial.s5.b2"],
  },
  {
    title: "tutorial.s6.title",
    body: "tutorial.s6.body",
    figure: <BlindFigure />,
    points: ["tutorial.s6.b1", "tutorial.s6.b2"],
    aside: "tutorial.s6.aside",
  },
  {
    title: "tutorial.s7.title",
    body: "tutorial.s7.body",
    figure: <CloseFigure />,
    points: ["tutorial.s7.b1", "tutorial.s7.b2", "tutorial.s7.b3"],
    aside: "tutorial.s7.aside",
  },
  {
    title: "tutorial.s8.title",
    body: "tutorial.s8.body",
    figure: <WorkspaceFigure />,
    aside: "tutorial.s8.aside",
  },
];

/** The index: the four steps of the first phase, numbered exactly as the bar numbers them. */
function Steps() {
  const { t } = useT();
  return (
    <ol className="border border-border bg-card">
      {STEPS.map((step, index) => (
        <li
          key={step.path}
          className={cn("flex gap-3.5 p-3.5", index < STEPS.length - 1 && "border-b border-border")}
        >
          <span className="nums flex h-[26px] min-w-[26px] shrink-0 items-center justify-center bg-primary px-1 font-condensed text-small font-semibold text-primary-foreground">
            {stepNumber(index)}
          </span>
          <div className="min-w-0 space-y-0.5">
            <p className="text-body font-semibold">
              {t("tutorial.stepName", { n: stepNumber(index), name: t(step.labelKey) })}
            </p>
            <p className="text-small text-muted-foreground">{t(STEP_BODIES[index])}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function TutorialScreen() {
  const { t } = useT();
  const { navigate } = useRouter();
  const [at, setAt] = useState(0);

  const slide = SLIDES[at];
  const last = at === SLIDES.length - 1;
  // The path starts at step 1.1, which is the only one of the four that needs nothing built
  // to be useful. Leaving lands there and so does finishing.
  const leave = () => navigate("/raw");

  return (
    // `h-full` and not `min-h-full`: the footer is pinned to the bottom of the viewport and
    // the column between scrolls, which only works if this box has a height to divide.
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center gap-2.5 px-4 py-5 sm:px-6">
        <Link
          to="/raw"
          aria-label="Variatio" // i18n-exempt: es el nombre del producto
          className="flex items-center gap-2.5"
        >
          <Logo className="size-5 text-foreground" />
          <span className="font-display font-expanded text-body font-bold tracking-tight">
            Variatio
          </span>
        </Link>
        <button
          onClick={leave}
          className="ml-auto text-small text-muted-foreground underline-offset-4 hover:underline"
        >
          {t("tutorial.skip")}
        </button>
      </div>

      {/* CENTRADO MIENTRAS QUEPA, con scroll cuando no. `min-h-full` sobre el hijo es lo
          que mantiene el `justify-center`: sin él la columna mide lo que mide su contenido
          y se pega arriba en cuanto la diapositiva es corta. */}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 sm:px-6">
        <div className="mx-auto flex min-h-full w-full max-w-[46rem] flex-col justify-center gap-7 py-8">
          <div className="space-y-3">
            <p className="text-micro text-muted-foreground">
              {t("tutorial.of", { n: at + 1, total: SLIDES.length })}
            </p>
            <h1 className="font-display font-expanded text-title">{t(slide.title)}</h1>
            <p className="text-heading font-normal leading-relaxed text-muted-foreground">
              {t(slide.body)}
            </p>
          </div>

          {slide.figure}

          {slide.steps ? <Steps /> : null}

          {/* The points are a ruled column and not a bulleted list: they are sentences,
              and a dot in front of a sentence makes it look like an item in an inventory
              rather than a thing that is true. The rule on the left is the same device the
              rest of the app uses to say «these belong together». */}
          {slide.points ? (
            <div className="space-y-4 border-l-2 border-border pl-5">
              {slide.points.map((point) => (
                <p key={point} className="text-heading font-normal leading-relaxed">
                  {t(point)}
                </p>
              ))}
            </div>
          ) : null}

          {slide.aside ? (
            <p className="border border-[color-mix(in_oklch,var(--settled)_35%,transparent)] bg-[color-mix(in_oklch,var(--settled)_10%,transparent)] p-4 text-heading font-normal leading-relaxed">
              {t(slide.aside)}
            </p>
          ) : null}
        </div>
      </div>

      {/* THE NAV, IN THE SAME PLACE ON EVERY SLIDE. Outside the scrolling column and pinned
          to the bottom, so it never follows the content — and both buttons keep their box
          whatever word is in them, because the last slide's label is longer than
          «Siguiente» and the first slide has nothing to go back to. The dashes are a
          position and not a control: eight clickable dots would make this a menu, and what
          it is is a sequence with one obvious next move. */}
      <div className="shrink-0 border-t border-border px-4 py-4 sm:px-6">
        <div className="mx-auto flex w-full max-w-[46rem] items-center gap-4">
          <div aria-hidden className="flex flex-1 flex-wrap gap-1.5">
            {SLIDES.map((_, index) => (
              <span
                key={index}
                className={cn(
                  "h-[3px] w-5",
                  index < at && "bg-settled",
                  index === at && "bg-attention",
                  index > at && "bg-border",
                )}
              />
            ))}
          </div>
          <Button
            variant="ghost"
            className="min-w-[6rem]"
            // Rendered on every slide and merely INVISIBLE on the first: dropping it there
            // moved «Siguiente» sideways on the one slide everybody sees first.
            aria-hidden={at === 0}
            tabIndex={at === 0 ? -1 : undefined}
            disabled={at === 0}
            onClick={() => setAt((n) => n - 1)}
          >
            <span className={cn(at === 0 && "invisible")}>{t("tutorial.back")}</span>
          </Button>
          <Button
            variant="attention"
            size="lg"
            // 240px: el suelo tiene que ser mayor que la etiqueta más ancha o el botón se
            // ensancha en la última y salta hacia la izquierda. Era 13.5rem para «Empezar
            // por el Paso 1»; el paso pasó a llamarse «1.1» y la etiqueta creció con él.
            className="min-w-[15rem] justify-center"
            onClick={() => (last ? leave() : setAt((n) => n + 1))}
          >
            {t(last ? "tutorial.start" : "tutorial.next")}
            <ArrowRight />
          </Button>
        </div>
      </div>
    </div>
  );
}

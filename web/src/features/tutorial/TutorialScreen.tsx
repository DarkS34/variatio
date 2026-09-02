import { ChevronRight } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { useT, type Key } from "@/lib/i18n";
import { Link, useRouter } from "@/lib/router";
import { STEPS, stepNumber } from "@/lib/steps";
import { cn } from "@/lib/utils";

import {
  AskFigure,
  BlindFigure,
  CloseFigure,
  FlowFigure,
  HeaderFigure,
  NavFigure,
  PROSE,
  SourcesFigure,
} from "./figures";

/**
 * SIX SCREENS, AND THEY ARE THE MANUAL.
 *
 * Somebody who has just redeemed an invitation has never seen this and does not know what
 * the thing is called, so the first sentence is a definition — name, category, what it is
 * for — and every negation comes after it. Leaving here they have to be able to use the
 * whole thing without asking anybody: what it is, what it needs from them before they
 * start, and then the three phases of the product in the order they happen, ending with
 * what is being asked of them as an evaluator and the door into the first step.
 *
 * THE DECK IS THE PHASES (2026-09-02, explicit user request). It was eight slides and the
 * shape was invisible: one slide said «con eso el sistema ya está preparado» and the next
 * said «pedir ejercicios», which is one hinge told twice — and comparing, the third thing
 * the product does, was not presented as a phase at all. The three are named on their own
 * titles now, «Fase 1 / 2 / 3», the hinge is the opening sentence of Fase 2 instead of a
 * slide of its own, and the closing pair — what the study asks, and where to start —
 * became one slide, because a slide whose whole content is «press the button below» says
 * what the button says. `COMPARE_PHASE` was added to `lib/steps.ts` in the same change:
 * the bar numbers «Comparar» 3, or this deck would be promising a shape the navigation
 * does not have.
 *
 * Every slide carries a FIGURE. They are in `figures.tsx`, drawn in the ink with a single
 * `--attention` on the one thing the slide is about, and the bar is built from `STEPS` and
 * numbered with `stepNumber` — the same list and the same numbering the navigation reads —
 * so the picture cannot promise an order the path does not have. Where a figure
 * enumerates, the prose beside it does not: a drawing and a paragraph listing the same two
 * things is one thing said twice. That rule was applied a second time on 2026-09-02, to
 * the two slides that still broke it — Fase 2's lead walked the three questions its own
 * figure draws as chips, and the closing slide walked the four beats of its own figure.
 *
 * IT IS READ, NOT OPERATED, SO IT IS SET LIKE SOMETHING TO READ (2026-09-02, explicit user
 * request). The reading face is Literata and it is declared in `index.css` for this screen
 * alone — see the `@font-face` there for why a serif, why it is self-hosted and why it
 * costs every other screen nothing. Prose is `PROSE`, exported from `figures.tsx` because
 * a figure contains sentences too; the app's own grotesque survives inside the figures,
 * which are pictures of screens the reader is about to go and look at.
 *
 * ONE SIZE FOR EVERY SENTENCE (2026-09-01, explicit user request, and still the rule). The
 * lead, the points and the aside are equally true and are drawn the same; only the title
 * above them is larger, because it is a title.
 *
 * AND THE TITLE NEVER MOVES. It is its own row, outside the scrolling column, with a floor
 * of two lines — so the eyebrow, the title and the first line of prose land on the same
 * pixel of every slide, whatever is under them. Before this the whole column was centred
 * and the title rode up and down with the length of the slide. Two things follow from the
 * column being the only thing that scrolls (2026-09-02): it is SCROLLED BACK TO THE TOP on
 * every page turn, because the container outlives the slide and a reader who had scrolled
 * down slide 3 landed halfway into slide 4, mid-sentence; and its foot FADES, so a slide
 * taller than the window says «there is more» instead of cutting a heading in half.
 */

interface Slide {
  title: Key;
  /** The lead: the sentence of the slide. */
  body: Key;
  figure?: ReactNode;
  /** Short paragraphs under the figure, each its own point. */
  points?: Key[];
  /** One aside, set apart: the thing that is true but is not an instruction. */
  aside?: Key;
  /** Only the index slide: the four steps of the first phase, as a numbered list. */
  steps?: boolean;
  /** Only the last slide: the door, drawn under a rule. */
  outro?: Key;
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
    points: ["tutorial.s2.b1", "tutorial.s2.b2"],
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
    figure: <AskFigure />,
    points: ["tutorial.s4.b1", "tutorial.s4.b2", "tutorial.s4.b3"],
  },
  {
    title: "tutorial.s5.title",
    body: "tutorial.s5.body",
    figure: <BlindFigure />,
    points: ["tutorial.s5.b1", "tutorial.s5.b2"],
    aside: "tutorial.s5.aside",
  },
  {
    title: "tutorial.s6.title",
    body: "tutorial.s6.body",
    figure: <CloseFigure />,
    points: ["tutorial.s6.b1"],
    outro: "tutorial.s6.outro",
  },
];

/**
 * The column the whole deck is set in, so the head and the body cannot drift apart.
 *
 * The horizontal padding is applied OUTSIDE it, on the two wrappers, and never inside:
 * with the head carrying its own `px` inside the column the title started 24 px to the
 * right of the prose under it, on every slide (2026-09-02).
 */
const COLUMN = "mx-auto w-full max-w-[46rem]";

/**
 * The index: the four steps of the first phase, numbered exactly as the bar numbers them.
 *
 * Each row is the number, the step's own name and one paragraph. The name is not prefixed
 * «Paso 1.1:» — the counter beside it already says so, and with the bar drawn just above
 * that made four names read three times each.
 */
function Steps() {
  const { t } = useT();
  return (
    <ol className="border border-border bg-card">
      {STEPS.map((step, index) => (
        <li
          key={step.path}
          className={cn(
            "flex gap-4 p-5",
            index < STEPS.length - 1 && "border-b border-border",
          )}
        >
          <span className="nums mt-1 flex h-[26px] min-w-[26px] shrink-0 items-center justify-center bg-primary px-1 font-condensed text-small font-semibold text-primary-foreground">
            {stepNumber(index)}
          </span>
          <div className="min-w-0 space-y-1.5">
            <p className={cn(PROSE, "font-semibold")}>{t(step.labelKey)}</p>
            <p className={cn(PROSE, "text-muted-foreground")}>{t(STEP_BODIES[index])}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

/**
 * THE NEXT SLIDE, AS AN EDGE (2026-09-02, explicit user request).
 *
 * «Que sea medio difuminado, estirado verticalmente para que se entienda bien que ese es
 * el siguiente slide.» It is a page edge, not a button in a toolbar: full height of the
 * slide, faded into the right margin, so what it says is «there is more over there» rather
 * than «here is a control». The word runs vertically for the same reason — the shape is
 * doing the explaining, and a horizontal label in a tall strip would be a button that
 * happens to be tall.
 *
 * THE LAST ONE IS NOT FADED. Everywhere else the rail is the quiet continuation of a
 * sequence; on the last slide it is the one action of the whole screen — leaving for step
 * 1.1 — so it takes the `--attention` the palette spends on «act here», which no other
 * element of this deck is using. Its accessible name is the full sentence («Empezar por el
 * Paso 1.1»), never the vertical word alone.
 */
function NextRail({ label, name, last, onClick }: {
  label: string;
  name: string;
  last: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={name}
      aria-label={name}
      className="group relative flex w-14 shrink-0 items-center justify-center border-l border-border sm:w-20 lg:w-24"
    >
      <span
        aria-hidden
        className={cn(
          "absolute inset-0 transition-opacity",
          last ? "opacity-100" : "opacity-70 group-hover:opacity-100",
        )}
        style={{
          background: last
            ? "linear-gradient(to right, transparent, color-mix(in oklch, var(--attention) 30%, transparent))"
            : "linear-gradient(to right, transparent, var(--accent))",
        }}
      />
      <span className="relative flex flex-col items-center gap-5">
        <span
          style={{ writingMode: "vertical-rl" }}
          className={cn(
            "text-small uppercase tracking-[0.12em]",
            last
              ? "font-semibold text-attention"
              : "text-muted-foreground transition-colors group-hover:text-foreground",
          )}
        >
          {label}
        </span>
        <ChevronRight
          aria-hidden
          className={cn(
            "size-6 transition-transform group-hover:translate-x-0.5",
            last ? "text-attention" : "text-muted-foreground group-hover:text-foreground",
          )}
        />
      </span>
    </button>
  );
}

export function TutorialScreen() {
  const { t } = useT();
  const { navigate } = useRouter();
  const [at, setAt] = useState(0);
  const column = useRef<HTMLDivElement>(null);

  const slide = SLIDES[at];
  const last = at === SLIDES.length - 1;
  // The path starts at step 1.1, which is the only one of the four that needs nothing built
  // to be useful. Leaving lands there and so does finishing.
  const leave = () => navigate("/raw");
  const forward = () => (last ? leave() : setAt((n) => n + 1));

  // A deck is paged with the arrow keys by everybody who has ever seen one, and there is no
  // input on this screen for them to be stolen from.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") forward();
      if (event.key === "ArrowLeft") setAt((n) => Math.max(0, n - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // The scrolling column is the same element on every slide, so a page turn keeps whatever
  // scroll the previous slide left — measured: after reading slide 3 to the end, slide 4
  // opened on its third line. Every slide starts at its first.
  useEffect(() => {
    column.current?.scrollTo({ top: 0 });
  }, [at]);

  return (
    // `h-full` and not `min-h-full`: the head and the footer are pinned and the column
    // between them scrolls, which only works if this box has a height to divide.
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

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          {/* LA CABECERA DE LA DIAPOSITIVA, FUERA DEL SCROLL. El suelo de dos líneas es lo
              que fija también el arranque del texto: sin él, una diapositiva de título
              corto empieza a leerse cuarenta píxeles más arriba que la siguiente. */}
          <div className="shrink-0 px-4 pt-2 sm:px-6 sm:pt-6">
            <div className={COLUMN}>
              <p className="text-small text-muted-foreground">
                {t("tutorial.of", { n: at + 1, total: SLIDES.length })}
              </p>
              <h1 className="mt-4 flex min-h-[2.3em] font-reading text-[1.75rem] font-semibold leading-[1.15] tracking-[-0.01em] sm:text-[2.25rem]">
                {t(slide.title)}
              </h1>
            </div>
          </div>

          <div className="relative min-h-0 flex-1">
            <div ref={column} className="h-full overflow-y-auto px-4 sm:px-6">
              <div className={cn(COLUMN, "flex flex-col gap-8 pb-12 pt-2")}>
                {/* The lead is in the ink and the aside is not: the lead is the sentence of
                    the slide, and greying it under points drawn in full ink inverted the
                    emphasis (2026-09-02) — on the first slide, which is a lead and a figure,
                    every word was grey. */}
                <p className={PROSE}>{t(slide.body)}</p>

                {slide.figure}

                {slide.steps ? <Steps /> : null}

                {/* The points are a ruled column and not a bulleted list: they are
                    sentences, and a dot in front of a sentence makes it look like an item
                    in an inventory rather than a thing that is true. The rule on the left
                    is the same device the rest of the app uses to say «these belong
                    together». */}
                {slide.points ? (
                  <div className="flex flex-col gap-6 border-l-2 border-border pl-6 sm:pl-7">
                    {slide.points.map((point) => (
                      <p key={point} className={PROSE}>
                        {t(point)}
                      </p>
                    ))}
                  </div>
                ) : null}

                {/* No box (2026-09-02, explicit user request). What sets an aside apart is
                    that it is not an instruction, and muted ink says that without drawing
                    a container around one paragraph of a page made of paragraphs. */}
                {slide.aside ? (
                  <p className={cn(PROSE, "text-muted-foreground")}>{t(slide.aside)}</p>
                ) : null}

                {slide.outro ? (
                  <div className="flex flex-col gap-6 border-t border-border pt-9">
                    <HeaderFigure />
                    <p className={PROSE}>{t(slide.outro)}</p>
                  </div>
                ) : null}
              </div>
            </div>
            {/* The foot of the column fades into the page. On a slide that fits it covers
                nothing but the column's own bottom padding, so it is invisible; on one
                that does not it is what says «sigue abajo» instead of a heading cut in
                half at the window's edge. */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 bottom-0 h-14"
              style={{ background: "linear-gradient(to top, var(--background), transparent)" }}
            />
          </div>
        </div>

        <NextRail
          label={t(last ? "tutorial.railStart" : "tutorial.next")}
          name={t(last ? "tutorial.start" : "tutorial.next")}
          last={last}
          onClick={forward}
        />
      </div>

      {/* EL PIE, IGUAL EN TODAS. «Atrás» se dibuja siempre y sólo se vuelve invisible en la
          primera: quitarlo movía de sitio lo único que queda en la fila. Las rayas son una
          posición y no un control — ocho puntos pulsables convertirían esto en un menú, y
          lo que es es una secuencia con un siguiente evidente, que además está dibujado a
          la derecha a lo alto de la pantalla. */}
      <div className="shrink-0 border-t border-border px-4 py-4 sm:px-6">
        <div className={cn(COLUMN, "flex items-center gap-4")}>
          <Button
            variant="ghost"
            className="min-w-[6rem]"
            aria-hidden={at === 0}
            tabIndex={at === 0 ? -1 : undefined}
            disabled={at === 0}
            onClick={() => setAt((n) => n - 1)}
          >
            <span className={cn(at === 0 && "invisible")}>{t("tutorial.back")}</span>
          </Button>
          <div aria-hidden className="flex flex-1 flex-wrap justify-end gap-1.5">
            {SLIDES.map((_, index) => (
              <span
                key={index}
                className={cn(
                  "h-[3px] w-6",
                  index < at && "bg-settled",
                  index === at && "bg-attention",
                  index > at && "bg-border",
                )}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

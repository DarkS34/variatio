import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import { useT, type Key } from "@/lib/i18n";
import { useRouter } from "@/lib/router";
import { STEPS, stepNumber } from "@/lib/steps";
import { cn } from "@/lib/utils";
import { useHasWorkspace } from "@/state/auth";

import { AskFigure, FlowFigure, PROSE, SourcesFigure } from "./figures";
import { SLIDE_COUNT, slidePath } from "./slides";

/**
 * Four screens, and they are the manual.
 *
 * Somebody who has just redeemed an invitation does not know what the thing is called, so
 * the first sentence is a definition and every negation comes after it. Leaving here they
 * must be able to use the whole product without asking anybody.
 *
 * The construction's four steps are numbered because they go in order, and generating is
 * what they lead to; the bar draws the same shape (`lib/steps.ts`), or the deck would
 * promise one the navigation does not have.
 *
 * The shell draws NO header under this route, so the deck is the whole window and may not
 * point at parts of a bar that is not on screen. The slide is the PATH, which is what lets
 * the browser's back button leave rather than step through four slides.
 *
 * It is read and not operated, so it is set like something to read: the reading face is
 * Literata, declared in `index.css` for this screen alone, and prose is `PROSE` from
 * `figures.tsx`, because a figure contains sentences too. One size for every sentence —
 * lead, points and aside are equally true — and only the title above them is larger.
 *
 * The title is its own row outside the scrolling column, with a floor of two lines, so the
 * head of every slide lands on the same pixel. The column is scrolled back to the top on
 * every page turn: it outlives the slide, so otherwise a reader who had scrolled down one
 * lands halfway into the next. Its foot fades, so a tall slide says "there is more"
 * instead of cutting a heading in half.
 */

interface Slide {
  title: Key;
  /** The lead: the sentence of the slide. */
  body: Key;
  figure?: ReactNode;
  /** Short paragraphs under the figure, each its own point. */
  points?: Point[];
  /** One aside, set apart: the thing that is true but is not an instruction. */
  aside?: Key;
  /** Only the index slide: the four steps of the construction, as a numbered list. */
  steps?: boolean;
  /** The aside under the steps: what is true of every one of them. */
  stepsAside?: Key;
  /**
   * Only the last slide: the door, drawn under a rule. Two sentences, because the reader
   * either has a subject to pick or has none and must create one.
   */
  outro?: { create: Key; choose: Key };
}

/**
 * A point, and the one that is MARKED.
 *
 * The deck is ink on paper throughout, and exactly ONE sentence is marked: "a couple of
 * temas basta" is the line a reader who skims will get wrong, at the cost of an afternoon
 * of transcription. A second mark would undo the point of the first.
 *
 * The tint is `--destructive` at 12 % mixed into the page in `oklab`, never `oklch`: the
 * background's chroma is ~0 at hue 265, so mixing round the hue circle lands on a blue.
 * The ink is not repainted — what is marked is the sentence, not a warning label.
 */
type Point = Key | { key: Key; mark: true };

const keyOf = (point: Point) => (typeof point === "string" ? point : point.key);
const marked = (point: Point) => typeof point !== "string";

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
    points: [{ key: "tutorial.s2.b1", mark: true }, "tutorial.s2.b2"],
  },
  // No figure: the four steps are the list itself.
  {
    title: "tutorial.s3.title",
    body: "tutorial.s3.body",
    steps: true,
    stepsAside: "tutorial.s3.aside",
  },
  // The last slide: what the construction is for, and the door out of the deck.
  {
    title: "tutorial.s4.title",
    body: "tutorial.s4.body",
    figure: <AskFigure />,
    points: ["tutorial.s4.b1", "tutorial.s4.b2", "tutorial.s4.b3"],
    outro: { create: "tutorial.s4.outro.create", choose: "tutorial.s4.outro.choose" },
  },
];

// `slides.ts` owns the count, because the routes are one per slide: a deck that grew
// without telling it would leave its last slide unreachable by URL, in silence.
if (SLIDES.length !== SLIDE_COUNT) {
  throw new Error(`tutorial: ${SLIDES.length} slides against SLIDE_COUNT = ${SLIDE_COUNT}`);
}

/**
 * The column the whole deck is set in, so the head and the body cannot drift apart.
 *
 * The horizontal padding goes OUTSIDE it, on the two wrappers, and never inside: a head
 * carrying its own `px` starts 24 px right of the prose under it.
 */
const COLUMN = "mx-auto w-full max-w-[46rem]";

/**
 * A paragraph of the slide, JUSTIFIED from `sm` up and ragged below it.
 *
 * The deck is set as something to read, in one measured column of ~65 characters a line, and
 * there both edges straight make each slide read as a page. What makes it safe is the
 * hyphenation: without it a justified line with one long Spanish word stretches its spaces into
 * rivers, and `hyphens: auto` reads the language off `<html lang>`, which `lib/i18n/locale.ts`
 * stamps with the reader's own. On a phone a line holds ~35 characters, too few to spread
 * evenly, so there the text stays ragged. Only paragraphs: a title, a label quoted from the app
 * and the sentences inside a figure keep their own alignment.
 */
const READING = `${PROSE} sm:text-justify sm:hyphens-auto`;

/**
 * The index: the four steps of the construction, numbered exactly as the bar numbers them.
 *
 * The name is never prefixed "Paso 1:" — the counter beside it already says so.
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
            <p className={cn(READING, "text-muted-foreground")}>{t(STEP_BODIES[index])}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

/**
 * A slide's edge, on either side.
 *
 * A page edge and not a button in a toolbar: full height, faded into the margin, the word
 * running vertically, so the shape says "there is more over there". On the left it reads
 * upwards, the way a spine does, so the two edges mirror.
 *
 * The LAST forward one is not faded: it is the one action of the whole screen, so it takes
 * the `--attention` the palette spends on "act here". Its accessible name is the full
 * sentence, never the vertical word alone.
 *
 * On the first slide the back rail is drawn for its width alone, invisible and unreachable:
 * removing it would move the column sideways on one slide out of four.
 */
function Rail({
  side,
  label,
  name,
  tone,
  hidden = false,
  onClick,
}: {
  side: "left" | "right";
  label: string;
  name: string;
  tone: "quiet" | "attention";
  hidden?: boolean;
  onClick: () => void;
}) {
  const left = side === "left";
  const Chevron = left ? ChevronLeft : ChevronRight;
  const attention = tone === "attention";
  return (
    <button
      onClick={onClick}
      title={name}
      aria-label={name}
      aria-hidden={hidden || undefined}
      tabIndex={hidden ? -1 : undefined}
      disabled={hidden}
      className={cn(
        "group relative flex w-14 shrink-0 items-center justify-center border-border sm:w-20 lg:w-24",
        left ? "border-r" : "border-l",
        hidden && "invisible",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "absolute inset-0 transition-opacity",
          attention ? "opacity-100" : "opacity-70 group-hover:opacity-100",
        )}
        style={{
          background: `linear-gradient(to ${left ? "left" : "right"}, transparent, ${
            attention
              ? "color-mix(in oklch, var(--attention) 30%, transparent)"
              : "var(--accent)"
          })`,
        }}
      />
      <span className="relative flex flex-col items-center gap-5">
        <span
          style={{ writingMode: "vertical-rl", transform: left ? "rotate(180deg)" : undefined }}
          className={cn(
            "text-small uppercase tracking-[0.12em]",
            attention
              ? "font-semibold text-attention"
              : "text-muted-foreground transition-colors group-hover:text-foreground",
          )}
        >
          {label}
        </span>
        <Chevron
          aria-hidden
          className={cn(
            "size-6 transition-transform",
            left ? "group-hover:-translate-x-0.5" : "group-hover:translate-x-0.5",
            attention ? "text-attention" : "text-muted-foreground group-hover:text-foreground",
          )}
        />
      </span>
    </button>
  );
}

export function TutorialScreen({ at }: { at: number }) {
  const { t } = useT();
  const { navigate } = useRouter();
  const hasWorkspace = useHasWorkspace();
  const column = useRef<HTMLDivElement>(null);

  const slide = SLIDES[at];
  const first = at === 0;
  const last = at === SLIDE_COUNT - 1;
  // Paging REPLACES the history entry rather than pushing one, so the back button leaves
  // the deck instead of stepping through four slides already turned.
  const go = (index: number) => navigate(slidePath(index), { replace: true });
  // Step 1 is the only one of the four that needs nothing built, and with no subject yet
  // the same screen is the form that creates one.
  const leave = () => navigate("/raw");
  const forward = () => (last ? leave() : go(at + 1));
  const back = () => {
    if (!first) go(at - 1);
  };

  // No input on this screen, so the arrow keys can be taken for paging.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") forward();
      if (event.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // The scrolling column is the same element on every slide, so without this a page turn
  // keeps the scroll the previous one left and opens mid-sentence.
  useEffect(() => {
    column.current?.scrollTo({ top: 0 });
  }, [at]);

  return (
    // A flex item of the shell's `main`, which is a padding-less column under the deck:
    // this box takes the height and the column inside it is what scrolls.
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 flex-1">
        <Rail
          side="left"
          label={t("tutorial.back")}
          name={t("tutorial.back")}
          tone="quiet"
          hidden={first}
          onClick={back}
        />

        <div className="flex min-w-0 flex-1 flex-col">
          {/* The counter and "Saltar" stay up top: they are the position in the deck and
              the way out, not the slide, so they do not move with it. Everything else — the
              title included — is centred in the window. The floor of two lines on the title
              keeps the rhythm between title and prose the same on a one-line title and on a
              two-line one. */}
          <div className="shrink-0 px-4 pt-5 sm:px-6 sm:pt-7">
            <div className={cn(COLUMN, "flex items-baseline justify-between gap-4")}>
              <p className="text-small text-muted-foreground">
                {t("tutorial.of", { n: at + 1, total: SLIDE_COUNT })}
              </p>
              <button
                onClick={leave}
                className="text-small text-muted-foreground underline-offset-4 hover:underline"
              >
                {t("tutorial.skip")}
              </button>
            </div>
          </div>

          <div className="relative min-h-0 flex-1">
            {/* `m-auto` and not `justify-center`: automatic margins centre the block when it
                fits and give way to the top when it does not, where a centred flex container
                clips the head of anything taller than it. */}
            <div ref={column} className="flex h-full flex-col overflow-y-auto px-4 sm:px-6">
              <div className={cn(COLUMN, "m-auto flex flex-col gap-2 py-6")}>
                <h1 className="flex min-h-[2.3em] font-reading text-[1.75rem] font-semibold leading-[1.15] tracking-[-0.01em] sm:text-[2.25rem]">
                  {t(slide.title)}
                </h1>
                <div className="flex flex-col gap-8">
                  {/* The lead is in the ink and the aside is not: greying the sentence of
                      the slide under points drawn in full ink inverts the emphasis, and on a
                      slide that is a lead and a figure it greys every word on it. */}
                  <p className={READING}>{t(slide.body)}</p>

                  {slide.figure}

                  {slide.steps ? <Steps /> : null}
                  {slide.stepsAside ? (
                    <p className={cn(PROSE, "text-muted-foreground")}>{t(slide.stepsAside)}</p>
                  ) : null}

                  {/* The points are a ruled column and not a bulleted list: they are
                      sentences, and a dot in front of a sentence makes it look like an item
                      in an inventory rather than a thing that is true. The rule on the left
                      is the same device the rest of the app uses to say "these belong
                      together". */}
                  {slide.points ? (
                    <div className="flex flex-col gap-6 border-l-2 border-border pl-6 sm:pl-7">
                      {slide.points.map((point) => (
                        <p
                          key={keyOf(point)}
                          // `box-decoration-clone` makes the ground a highlight and not a
                          // rectangle: without it a wrapped sentence paints one box across
                          // every line, over the gaps. The negative side padding keeps the
                          // ink starting on the column's own left edge.
                          className={cn(
                            READING,
                            marked(point) &&
                              "box-decoration-clone -mx-1.5 rounded-sm bg-[color-mix(in_oklab,var(--destructive)_12%,var(--background))] px-1.5 py-0.5",
                          )}
                        >
                          {t(keyOf(point))}
                        </p>
                      ))}
                    </div>
                  ) : null}

                  {/* No box: what sets an aside apart is that it is not an instruction, and
                      muted ink says so without drawing a container around one paragraph of a
                      page made of paragraphs. */}
                  {slide.aside ? (
                    <p className={cn(READING, "text-muted-foreground")}>{t(slide.aside)}</p>
                  ) : null}

                  {slide.outro ? (
                    <div className="border-t border-border pt-9">
                      <p className={READING}>
                        {t(hasWorkspace ? slide.outro.choose : slide.outro.create)}
                      </p>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
            {/* The foot of the column fades into the page. On a slide that fits it covers
                nothing but the column's own bottom padding, so it is invisible; on one
                that does not it is what says "sigue abajo" instead of a heading cut in
                half at the window's edge. */}
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 bottom-0 h-14"
              style={{ background: "linear-gradient(to top, var(--background), transparent)" }}
            />
          </div>
        </div>

        <Rail
          side="right"
          label={t(
            last ? (hasWorkspace ? "tutorial.railStart" : "tutorial.railCreate") : "tutorial.next",
          )}
          name={t(
            last ? (hasWorkspace ? "tutorial.start" : "noWorkspace.createMine") : "tutorial.next",
          )}
          tone={last ? "attention" : "quiet"}
          onClick={forward}
        />
      </div>

      {/* The foot: the dashes, centred, and each one leads to its slide — "Atrás" is the
          left edge, so nothing but the index is left here. The dash is 3 px and the button
          around it is not: the hit area is the whole row, which is what makes four thin
          marks four destinations. */}
      <div className="shrink-0 border-t border-border px-4 py-2.5 sm:px-6">
        <div
          role="group"
          aria-label={t("tutorial.slides")}
          className="flex items-center justify-center gap-1"
        >
          {SLIDES.map((entry, index) => (
            <button
              key={entry.title}
              onClick={() => go(index)}
              title={t(entry.title)}
              aria-label={t("tutorial.goTo", { n: index + 1 })}
              aria-current={index === at ? "step" : undefined}
              className="group px-1 py-2.5"
            >
              <span
                className={cn(
                  "block h-[3px] w-7 transition-colors",
                  index < at && "bg-settled group-hover:bg-foreground",
                  index === at && "bg-attention",
                  index > at && "bg-border group-hover:bg-muted-foreground",
                )}
              />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

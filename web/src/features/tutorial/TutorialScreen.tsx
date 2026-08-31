import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { useT, type Key } from "@/lib/i18n";
import { Link, useRouter } from "@/lib/router";
import { STEPS } from "@/lib/steps";
import { cn } from "@/lib/utils";

/**
 * NINE SCREENS, AND THEY ARE THE MANUAL.
 *
 * Somebody who has just redeemed an invitation has never seen this, and what the app used
 * to show them first was a panel with three artifacts on it. Leaving here they have to be
 * able to use the whole thing without asking anybody: what it does, what it needs from
 * them, the four steps, how long they take, how each one ends, that a hand correction
 * always wins, how an exercise is asked for, how the comparison works and why it is blind,
 * and that nothing is irreversible.
 *
 * That is a different thing from the guide, and the two do not overlap by accident: the
 * guide is a REFERENCE, one page per screen, reached from that screen when a particular
 * question comes up. This is the ROUTE, end to end, read once before anything exists.
 *
 * It is not a gate. «Saltar la explicación» is on every screen and the account menu leads
 * back, because a person who has understood should not have to page through it and one who
 * skipped too fast should be able to return. Nothing is recorded about whether it was
 * read: making it a state to track would make it a chore to finish.
 *
 * The four steps are named from `lib/steps.ts`, the same list the bar draws, so the
 * promise made here cannot drift from the path a person then walks.
 */

interface Slide {
  title: Key;
  body: Key;
  /** Short paragraphs under the body, each its own point. */
  points?: Key[];
  /** One aside, set apart: the thing that is true but is not an instruction. */
  aside?: Key;
  /** Only the third slide: the four steps as a numbered list. */
  steps?: boolean;
}

const SLIDES: Slide[] = [
  { title: "tutorial.s1.title", body: "tutorial.s1.body" },
  {
    title: "tutorial.s2.title",
    body: "tutorial.s2.body",
    points: ["tutorial.s2.b1", "tutorial.s2.b2"],
    aside: "tutorial.s2.aside",
  },
  { title: "tutorial.s3.title", body: "tutorial.s3.body", steps: true },
  {
    title: "tutorial.s4.title",
    body: "tutorial.s4.body",
    points: ["tutorial.s4.b1", "tutorial.s4.b2", "tutorial.s4.b3"],
  },
  {
    title: "tutorial.s5.title",
    body: "tutorial.s5.body",
    points: ["tutorial.s5.b1", "tutorial.s5.b2"],
    aside: "tutorial.s5.aside",
  },
  {
    title: "tutorial.s6.title",
    body: "tutorial.s6.body",
    points: ["tutorial.s6.b1", "tutorial.s6.b2", "tutorial.s6.b3", "tutorial.s6.b4"],
  },
  {
    title: "tutorial.s7.title",
    body: "tutorial.s7.body",
    points: ["tutorial.s7.b1", "tutorial.s7.b2", "tutorial.s7.b3"],
  },
  {
    title: "tutorial.s8.title",
    body: "tutorial.s8.body",
    points: ["tutorial.s8.b1", "tutorial.s8.b2"],
    aside: "tutorial.s8.aside",
  },
  {
    title: "tutorial.s9.title",
    body: "tutorial.s9.body",
    points: ["tutorial.s9.b1", "tutorial.s9.b2"],
  },
];

const STEP_BODIES: Key[] = [
  "tutorial.s3.step1",
  "tutorial.s3.step2",
  "tutorial.s3.step3",
  "tutorial.s3.step4",
];

function Steps() {
  const { t } = useT();
  return (
    <ol className="border border-border bg-card">
      {STEPS.map((step, index) => (
        <li
          key={step.path}
          className={cn("flex gap-3.5 p-4", index < STEPS.length - 1 && "border-b border-border")}
        >
          <span className="nums flex size-[26px] shrink-0 items-center justify-center bg-primary font-condensed text-small font-semibold text-primary-foreground">
            {index + 1}
          </span>
          <div className="min-w-0 space-y-0.5">
            <p className="text-body font-semibold">{t(step.labelKey)}</p>
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
  // The path starts at step 1, which is the only one of the four that needs nothing built
  // to be useful. Leaving lands there and so does finishing.
  const leave = () => navigate("/raw");

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex items-center gap-2.5 px-4 py-5 sm:px-6">
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

      <div className="flex flex-1 justify-center px-4 pb-16 pt-4 sm:px-6">
        <div className="w-full max-w-[44rem] space-y-6">
          <div className="space-y-2.5">
            <p className="text-micro text-muted-foreground">
              {t("tutorial.of", { n: at + 1, total: SLIDES.length })}
            </p>
            <h1 className="font-display font-expanded text-display">{t(slide.title)}</h1>
            <p className="max-w-[62ch] text-body text-muted-foreground">{t(slide.body)}</p>
          </div>

          {slide.steps ? <Steps /> : null}

          {/* The points are a ruled column and not a bulleted list: they are sentences,
              and a dot in front of a sentence makes it look like an item in an inventory
              rather than a thing that is true. The rule on the left is the same device the
              rest of the app uses to say «these belong together». */}
          {slide.points ? (
            <div className="space-y-3 border-l-2 border-border pl-4">
              {slide.points.map((point) => (
                <p key={point} className="max-w-[62ch] text-body">
                  {t(point)}
                </p>
              ))}
            </div>
          ) : null}

          {slide.aside ? (
            <p className="max-w-[62ch] border border-[color-mix(in_oklch,var(--settled)_35%,transparent)] bg-[color-mix(in_oklch,var(--settled)_10%,transparent)] p-3 text-small">
              {t(slide.aside)}
            </p>
          ) : null}

          {/* The dashes are a position and not a control: nine clickable dots would make
              this a menu, and what it is is a sequence with one obvious next move. */}
          <div className="flex items-center gap-4 pt-2">
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
            {at > 0 ? (
              <Button variant="ghost" onClick={() => setAt((n) => n - 1)}>
                {t("tutorial.back")}
              </Button>
            ) : null}
            <Button
              variant="attention"
              size="lg"
              onClick={() => (last ? leave() : setAt((n) => n + 1))}
            >
              {t(last ? "tutorial.start" : "tutorial.next")}
              <ArrowRight />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

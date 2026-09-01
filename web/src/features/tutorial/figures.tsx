import { ArrowRight, Check, FileText, Sparkles } from "lucide-react";

import { Logo } from "@/components/ui/logo";
import { useT, type Key } from "@/lib/i18n";
import { STEPS } from "@/lib/steps";
import { cn } from "@/lib/utils";

/**
 * THE PICTURES THE TUTORIAL EXPLAINS ITSELF WITH.
 *
 * Two rules, and they are the palette's own. Everything here is drawn in the ink — boxes,
 * rules, arrows, labels — and the ONE thing a slide is about is the only thing carrying
 * `--attention`. A figure with two coloured elements has stopped pointing at anything.
 *
 * And they are drawn out of the app's own sources, never hand-copied: the bar is built
 * from `STEPS`, the same list the real navigation draws, so the picture of the path cannot
 * promise an order the path does not have. That is what makes it worth drawing at all —
 * somebody is about to look for these four names on a screen they have never seen.
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

function Arrow() {
  return <ArrowRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />;
}

/**
 * THE BAR, WITH ONE STOP MARKED.
 *
 * It is the figure four of the ten slides share, and it is doing the work of a sentence
 * that would otherwise have to be written ten times: «this is where you will find it». The
 * marked stop is the step the slide is about; with `active` unset nothing is marked and it
 * is the whole path at once, which is the index slide's own picture.
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
                "nums flex size-[18px] shrink-0 items-center justify-center font-condensed text-[10px] font-semibold",
                marked
                  ? "bg-attention text-[oklch(0.99_0.003_262)]"
                  : "border border-dashed border-input text-muted-foreground",
              )}
            >
              {index + 1}
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

/** What goes in and what comes out: the whole product in one line. */
export function FlowFigure() {
  const { t } = useT();
  return (
    <div className="flex items-center justify-center gap-2.5">
      <Box className="flex-1">
        <FileText aria-hidden className="size-4 text-muted-foreground" />
        <span className="text-small">{t("tutorial.fig.yours")}</span>
      </Box>
      <Arrow />
      <Box className="flex-1">
        <Logo className="size-4 text-foreground" />
        <span className="text-small">{t("tutorial.fig.learns")}</span>
      </Box>
      <Arrow />
      <Box marked className="flex-1">
        <Sparkles aria-hidden className="size-4 text-attention" />
        <span className="text-small font-medium">{t("tutorial.fig.new")}</span>
      </Box>
    </div>
  );
}

/** The two piles of documents, side by side, because they are two answers to one question. */
export function SourcesFigure() {
  const { t } = useT();
  return (
    <div className="grid gap-2.5 sm:grid-cols-2">
      {(["tutorial.fig.notes", "tutorial.fig.exercises"] as Key[]).map((key) => (
        <Box key={key} className="items-start text-left">
          <FileText aria-hidden className="size-4 text-muted-foreground" />
          <span className="text-small">{t(key)}</span>
        </Box>
      ))}
    </div>
  );
}

/** How a step ends: three marks, and only the last one is yours to press. */
export function CloseFigure() {
  const { t } = useT();
  const stages: { key: Key; marked?: boolean }[] = [
    { key: "tutorial.fig.build" },
    { key: "tutorial.fig.review" },
    { key: "tutorial.fig.approve", marked: true },
  ];
  return (
    <div className="flex items-center justify-center gap-2.5">
      {stages.map(({ key, marked }, index) => (
        <div key={key} className="flex min-w-0 flex-1 items-center gap-2.5">
          <Box marked={marked} className="w-full">
            {marked ? <Check aria-hidden className="size-4 text-attention" /> : null}
            <span className={cn("text-small", marked && "font-medium")}>{t(key)}</span>
          </Box>
          {index < stages.length - 1 ? <Arrow /> : null}
        </div>
      ))}
    </div>
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

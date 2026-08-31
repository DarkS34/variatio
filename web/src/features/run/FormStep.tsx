import { Check, Pencil } from "lucide-react";
import { useId, type ReactNode } from "react";

import { InfoHint } from "@/components/ui/hint";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

/**
 * One question of the form: open while it is being answered, one line once it is.
 *
 * The collapsed line is not decoration — it is what keeps four questions on screen at
 * once without four cards' worth of chrome, so going back to change the concepts costs
 * one click and no scrolling.
 */
export function FormStep({
  index,
  title,
  hint,
  optional = false,
  open,
  answered,
  summary,
  onOpen,
  children,
}: {
  index: number;
  title: string;
  hint?: ReactNode;
  optional?: boolean;
  open: boolean;
  answered: boolean;
  summary: ReactNode;
  onOpen: () => void;
  children: ReactNode;
}) {
  const { t } = useT();
  const id = useId();
  const names = [
    `${id}-title`,
    optional ? `${id}-optional` : null,
    open ? null : `${id}-summary`,
  ].filter(Boolean) as string[];

  return (
    <section
      className={cn(
        "animate-slide-up rounded-xl border transition-colors",
        open ? "border-border bg-card shadow-sm" : "border-transparent",
      )}
    >
      {/* THE WHOLE ROW OPENS THE STEP, AND THE (i) IS NOT PART OF IT. It used to be — an
          `InfoHint` nested inside this button — which is invalid HTML, stuttered the step's
          accessible name («1 ¿Qué tipo de ítem? ¿Qué tipo de ítem?») and, because the click
          reached the header underneath, made tapping the (i) navigate the form instead of
          explaining it. On a touch screen `onClick` is the only way to read a hint at all,
          so that was the one path guaranteed to interrupt itself.

          An overlay button keeps both: the row stays one big target, and the hint is a
          sibling that sits above it and takes its own clicks. */}
      <div className="group relative">
        <button
          type="button"
          onClick={onOpen}
          aria-expanded={open}
          aria-labelledby={names.join(" ")}
          className={cn(
            "absolute inset-0 rounded-xl transition-colors",
            !open && "hover:bg-accent/40",
          )}
        />

        <div className="pointer-events-none relative flex w-full items-center gap-2.5 px-3 py-2.5 text-left">
          {/* THE ORDINAL STAYS, AND THE CHECK GOES BESIDE IT (2026-08-31).
              The mark used to REPLACE the number once a step was answered and closed, so
              a half-filled form read «✓ · 2 · ✓ · 4 · 5»: two of the five steps had no
              number at all, and the ones that did no longer described a sequence. Measured
              on the real form — choose a modality and two concepts and that is exactly what
              is on screen.
              A number that disappears is not an ordinal. The step keeps it for as long as
              it exists, and «answered» is said by the tint plus a small check on the
              corner, which is additive rather than substitutive. */}
          <span
            className={cn(
              "relative flex size-6 shrink-0 items-center justify-center rounded-full text-small font-semibold nums transition-colors",
              answered
                ? "bg-primary/12 text-primary"
                : open
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground",
            )}
          >
            {index}
            {answered && !open ? (
              <span className="absolute -bottom-0.5 -right-0.5 flex size-3 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Check className="size-2 stroke-[4]" />
              </span>
            ) : null}
          </span>

          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1.5">
              <span
                id={`${id}-title`}
                className={cn("text-body font-medium", !open && !answered && "text-muted-foreground")}
              >
                {title}
              </span>
              {optional ? (
                <span
                  id={`${id}-optional`}
                  className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase"
                >
                  {t("common.optional")}
                </span>
              ) : null}
              {hint ? <InfoHint label={title}>{hint}</InfoHint> : null}
            </span>
            {!open ? (
              <span
                id={`${id}-summary`}
                className="mt-0.5 block truncate text-small text-muted-foreground"
              >
                {summary}
              </span>
            ) : null}
          </span>

          {!open ? (
            <Pencil className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          ) : null}
        </div>
      </div>

      {open ? <div className="animate-fade-in space-y-3 px-3 pb-3">{children}</div> : null}
    </section>
  );
}

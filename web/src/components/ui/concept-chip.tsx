import { X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A concept, drawn as a pill: the name whole, in the reading size, in its own case.
 *
 * ONE drawing for every list of concepts, so a concept looks the same wherever it is read.
 * Never a `Badge`: micro, condensed, uppercase with tracking is the drawing of a STATE word
 * ("aprobado", "remoto") and not of a name somebody chose, and a syllabus's names run to
 * "Análisis sintáctico descendente recursivo".
 *
 * The name is never truncated — one wider than its container wraps INSIDE the pill, which
 * is rare and reads as what it is, where an ellipsis reads as a different name. `tone` is
 * the only thing that varies: where the concept sits relative to the choice, or what the
 * graph made of it.
 */
const TONES = {
  default: "border-border bg-card text-foreground",
  primary: "border-primary bg-primary text-primary-foreground",
  prerequisite: "border-dashed border-primary/50 bg-primary/10 text-primary",
  attention:
    "border-[color-mix(in_oklch,var(--attention)_45%,transparent)] bg-[color-mix(in_oklch,var(--attention)_8%,transparent)] text-attention",
} as const;

export type ConceptChipTone = keyof typeof TONES;

export function ConceptChip({
  tone = "default",
  colour,
  title,
  onRemove,
  removeLabel,
  className,
  children,
}: {
  tone?: ConceptChipTone;
  /** The domain's colour, drawn as a dot before the name. */
  colour?: string;
  title?: string;
  /** Drawn as a × after the name; the chip is read-only without it. */
  onRemove?: () => void;
  removeLabel?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-small leading-5",
        TONES[tone],
        onRemove && "pr-1",
        className,
      )}
    >
      {colour ? (
        <span aria-hidden className="size-1.5 shrink-0 rounded-full" style={{ background: colour }} />
      ) : null}
      <span className="min-w-0 break-words">{children}</span>
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          aria-label={removeLabel}
          className="shrink-0 rounded-full p-0.5 hover:bg-background/60"
        >
          <X className="size-3" />
        </button>
      ) : null}
    </span>
  );
}

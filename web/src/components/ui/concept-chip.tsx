import { X } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";
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

/**
 * A concept where a `ConceptChip` does not fit: uppercase, condensed, on one line.
 *
 * THERE ARE TWO DRAWINGS OF A CONCEPT AND ONLY TWO, and which one is used is decided by the
 * room available, never by the meaning. The chip above is the reading one; this is the badge
 * the BANK'S ROW needs — its two-line badge box measures 50 px and a chip is 26, so two
 * chips do not fit in it — and the two feeds that read the same tagging: the tagger's live
 * decisions and the exemplars a generation was shown.
 *
 * The primary concept is FILLED in both, which is the one thing they must never disagree on.
 *
 * IT IS NEVER BROKEN OVER TWO LINES. A concept's name is written by a teacher, so it is as
 * long as they like — measured over the 474 distinct names of the reference graphs, a badge
 * runs from a median of 139 px to 353 ("Eliminación de la recursividad por la izquierda") —
 * and with `--radius: 0` the only shapes there are are the pill and the square rectangle, so
 * a two-line pill is a lozenge whose round corners eat its own text, in a row whose height is
 * fixed. It is cut with an ellipsis and the whole name goes in the `title`: what is trimmed
 * is named, never hidden, which is the rule the `+N` beside it already follows.
 *
 * `max-w-64` is measured and not chosen: it is exactly the width of the bank's concepts cell,
 * and over those 474 names it cuts 21 — 4.4 %, so the ellipsis stays the exception, which is
 * what justifies answering it with a `title` at all. It bounds the two feeds as well, where
 * the container is far wider and a 353 px badge would otherwise sit there whole.
 *
 * The `truncate` goes on a CHILD and not on the badge, because `text-overflow` does not act
 * on the items of a flex container and a badge is `inline-flex`.
 */
export function ConceptBadge({
  primary = false,
  /** What the OTHER concepts are drawn as. `outline` where the ground is too close to
   *  `--secondary` for a filled grey to read as a pill of its own. */
  rest = "secondary",
  children,
}: {
  primary?: boolean;
  rest?: "secondary" | "outline";
  children: string;
}) {
  const { t } = useT();
  return (
    <Badge
      variant={primary ? "primary" : rest}
      className="max-w-64"
      // The NAME is on every one of them, and the label only on the primary. That narrows
      // the rule that the others carry no `title` — a repeated label is noise, but any of
      // these can be the one that is cut, and a clipped name is information lost.
      title={primary ? `${children} · ${t("concept.isPrimary")}` : children}
    >
      <span className="truncate">{children}</span>
    </Badge>
  );
}

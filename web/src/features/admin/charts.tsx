import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The one figure the panel is built from: a stat tile.
 *
 * Hand-rolled, like the graph viewer: a charting library would arrive with its own
 * palette, its own type scale and its own idea of a tooltip.
 */

/* Stat tiles ------------------------------------------------------------------------ */

export function StatTile({
  label,
  value,
  hint,
  tone = "plain",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "plain" | "accent";
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2.5">
      <p className="text-small text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-0.5 text-title nums",
          tone === "accent" && "text-primary",
        )}
      >
        {value}
      </p>
      {hint ? <p className="text-small text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

/* Horizontal bars ------------------------------------------------------------------- */

export interface BarRow {
  key: string;
  label: string;
  value: number;
  /** The mark's colour. Identity, never rank: the same entity keeps it across filters. */
  colour?: string;
  /** What the tooltip says instead of the bare number. */
  detail?: string;
}

/**
 * One named row per category, sorted by nothing — the caller's order is the palette's.
 *
 * A reference line is drawn where a null hypothesis lives (1/3 for a three-way blind
 * choice). It is the whole point of the chart: "ganó 12 veces" means nothing until you
 * can see it against what pure chance would have produced.
 */

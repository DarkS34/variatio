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

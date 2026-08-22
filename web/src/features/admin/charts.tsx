import { useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The chart pieces this panel is built from.
 *
 * Hand-rolled and deliberately few, like the graph viewer: a charting library would
 * arrive with its own palette, its own type scale and its own idea of a tooltip, and the
 * three things worth getting right here — the arm colours, the 33 % reference line and
 * the fact that every mark is named — are exactly the three a library would take over.
 *
 * The specs are fixed, not per chart: bars cap at 20 px and round only their data end,
 * the baseline stays square, touching fills are separated by 2 px of surface rather than
 * by a stroke, gridlines are hairline and recessive, and no text ever wears a series
 * colour — identity comes from the swatch beside it.
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
      {hint ? <p className="text-micro text-muted-foreground">{hint}</p> : null}
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
 * choice). It is the whole point of the chart: «ganó 12 veces» means nothing until you
 * can see it against what pure chance would have produced.
 */
export function BarRows({
  rows,
  total,
  reference,
  referenceLabel,
  labelWidth = "10rem",
}: {
  rows: BarRow[];
  total: number;
  reference?: number;
  referenceLabel?: string;
  labelWidth?: string;
}) {
  const [hover, setHover] = useState<string | null>(null);

  if (total <= 0) {
    return <p className="text-small text-muted-foreground">Todavía no hay datos que resumir.</p>;
  }

  return (
    <div className="space-y-1.5">
      {rows.map((row) => {
        const share = row.value / total;
        return (
          <div
            key={row.key}
            className="relative flex items-center gap-2"
            onMouseEnter={() => setHover(row.key)}
            onMouseLeave={() => setHover(null)}
          >
            <span
              className="shrink-0 truncate text-small text-muted-foreground"
              style={{ width: labelWidth }}
              title={row.label}
            >
              {row.label}
            </span>

            <div className="relative h-2.5 flex-1 overflow-hidden rounded-[2px] bg-muted">
              <div
                className="h-full rounded-r-[4px] transition-[width] duration-300"
                style={{
                  width: `${Math.max(0, share) * 100}%`,
                  backgroundColor: row.colour ?? "var(--primary)",
                }}
              />
              {reference !== undefined ? (
                <span
                  aria-hidden
                  title={referenceLabel}
                  className="absolute inset-y-0 w-px bg-foreground/35"
                  style={{ left: `${reference * 100}%` }}
                />
              ) : null}
            </div>

            <span className="w-20 shrink-0 text-right text-small nums">
              {row.value}
              <span className="ml-1 text-muted-foreground">{Math.round(share * 100)} %</span>
            </span>

            {hover === row.key && row.detail ? (
              <div className="pointer-events-none absolute -top-7 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-popover px-2 py-1 text-micro shadow-md">
                {row.detail}
              </div>
            ) : null}
          </div>
        );
      })}
      {reference !== undefined && referenceLabel ? (
        <p className="text-micro text-muted-foreground">{referenceLabel}</p>
      ) : null}
    </div>
  );
}

/* Columns over time ----------------------------------------------------------------- */

export interface DayPoint {
  day: string;
  sessions: number;
  decided: number;
}

/**
 * How many comparisons happened each day, and how many of them were judged.
 *
 * Two steps of ONE hue rather than two categorical slots: «decidida» and «pendiente» are
 * not two entities, they are one thing in two states, and colouring them with the arm
 * scale would spend the identity channel on something that has no identity.
 *
 * A legend is present because there are two series; the gap between the two segments is
 * 2 px of surface, which is what separates them — no stroke.
 */
export function DayColumns({ points, height = 96 }: { points: DayPoint[]; height?: number }) {
  const [hover, setHover] = useState<number | null>(null);

  if (points.length === 0) {
    return (
      <p className="text-small text-muted-foreground">
        Ninguna comparación registrada todavía.
      </p>
    );
  }

  const peak = Math.max(...points.map((p) => p.sessions), 1);
  const showEvery = Math.ceil(points.length / 8);

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-micro text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-[2px] bg-primary" />
          Decididas
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-[2px] bg-primary/25" />
          Sin decidir
        </span>
        <span className="ml-auto nums">máx. {peak}/día</span>
      </div>

      <div className="relative">
        {/* Hairline, solid, one step off the surface: it has to be readable and not
            compete with the data. A dashed grid is decoration that reads as data. */}
        <span aria-hidden className="absolute inset-x-0 top-0 h-px bg-border" />
        <span aria-hidden className="absolute inset-x-0 bottom-0 h-px bg-border" />

        <div className="flex items-end gap-[2px]" style={{ height }}>
          {points.map((point, index) => {
            const pending = point.sessions - point.decided;
            return (
              <div
                key={point.day}
                className="relative flex min-w-[3px] flex-1 flex-col justify-end gap-[2px]"
                style={{ maxWidth: 20 }}
                onMouseEnter={() => setHover(index)}
                onMouseLeave={() => setHover(null)}
              >
                {pending > 0 ? (
                  <div
                    className="rounded-t-[4px] bg-primary/25"
                    style={{ height: `${(pending / peak) * (height - 4)}px` }}
                  />
                ) : null}
                {point.decided > 0 ? (
                  <div
                    className={cn("bg-primary", pending > 0 ? "" : "rounded-t-[4px]")}
                    style={{ height: `${(point.decided / peak) * (height - 4)}px` }}
                  />
                ) : null}

                {hover === index ? (
                  <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-popover px-2 py-1 text-micro shadow-md">
                    <span className="font-medium">{point.day}</span>
                    <span className="ml-2 nums text-muted-foreground">
                      {point.decided}/{point.sessions} decididas
                    </span>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex justify-between text-micro nums text-muted-foreground">
        {points
          .filter((_, index) => index % showEvery === 0)
          .map((point) => (
            <span key={point.day}>{point.day.slice(5)}</span>
          ))}
      </div>
    </div>
  );
}

/* A share, inline in a table row ----------------------------------------------------- */

/** A meter, not a chart: one ratio against its own limit, small enough to sit in a cell. */
export function ShareMeter({
  value,
  total,
  reference,
  title,
}: {
  value: number;
  total: number;
  reference?: number;
  title?: string;
}) {
  const share = total > 0 ? value / total : 0;
  return (
    <span className="flex items-center gap-2" title={title}>
      <span className="relative h-1.5 w-16 shrink-0 overflow-hidden rounded-[2px] bg-muted">
        <span
          className="absolute inset-y-0 left-0 rounded-r-[4px] bg-primary"
          style={{ width: `${share * 100}%` }}
        />
        {reference !== undefined ? (
          <span
            aria-hidden
            className="absolute inset-y-0 w-px bg-foreground/35"
            style={{ left: `${reference * 100}%` }}
          />
        ) : null}
      </span>
      <span className="w-10 text-right nums">
        {total > 0 ? `${Math.round(share * 100)} %` : "—"}
      </span>
    </span>
  );
}

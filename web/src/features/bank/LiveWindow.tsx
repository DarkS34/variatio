import { useEffect, useState, type ReactNode } from "react";

import { truncate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { purge, slide, type WindowRow } from "./window";

export const VISIBLE = 8;
const EXIT_MS = 260;

/**
 * The sliding window itself: what is on screen, and what is still leaving it.
 *
 * Replacing the list wholesale on every update said only "these are the last eight", and
 * the eight changed between two blinks with nothing to read the movement by. Here the row
 * that arrives opens its own space at the top and pushes the rest down, and the one that no
 * longer fits closes its own on the way out — which is why the returned list is longer than
 * `VISIBLE` for as long as an exit lasts, and why the row that is leaving is still rendered.
 */
export function useSlidingWindow<T extends { id: string }>(
  items: T[] | undefined,
): WindowRow<T>[] {
  const [rows, setRows] = useState<WindowRow<T>[]>([]);

  useEffect(() => {
    if (!items) return;
    setRows((current) => slide(current, items));
  }, [items]);

  useEffect(() => {
    if (!rows.some((row) => row.leaving)) return;
    const timer = window.setTimeout(() => setRows(purge), EXIT_MS);
    return () => window.clearTimeout(timer);
  }, [rows]);

  return rows;
}

export function SlidingList<T>({
  rows,
  children,
}: {
  rows: WindowRow<T>[];
  children: (item: T) => ReactNode;
}) {
  return (
    <ul>
      {rows.map((row) => (
        <li
          key={row.id}
          aria-hidden={row.leaving || undefined}
          className={cn("grid", row.leaving ? "animate-row-out" : "animate-row-in")}
        >
          <div className="overflow-hidden">
            <div className="mt-2 rounded-lg border border-border p-2.5">{children(row.item)}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function FeedRow({
  id,
  text,
  children,
}: {
  id: string;
  text: string;
  children: ReactNode;
}) {
  return (
    <>
      <div className="flex items-baseline gap-2">
        <code className="shrink-0 font-mono text-small text-muted-foreground">{id}</code>
        <p className="min-w-0 flex-1 text-body">{truncate(text, 180)}</p>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-1">{children}</div>
    </>
  );
}

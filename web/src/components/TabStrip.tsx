import { useRef } from "react";

import { cn } from "@/lib/utils";

/** One tab of a `TabStrip`: the value it chooses, its label and its count. */
export interface TabStripItem<T extends string> {
  value: T;
  label: string;
  /** Drawn beside the label when above zero; zero and unknown draw nothing. */
  count?: number;
}

/**
 * The ids that tie the tab `value` of the strip `strip` to the panel it shows.
 *
 * A screen that draws its panels passes the same `strip` to `TabStrip` as `id` and gives
 * each panel `panel` as its id and `tab` as its `aria-labelledby`.
 */
export function tabIds(strip: string, value: string): { tab: string; panel: string } {
  return { tab: `${strip}-tab-${value}`, panel: `${strip}-panel-${value}` };
}

/**
 * A row of tabs under a screen's header, each with an optional count, that tie each tab to
 * the panel it shows (`tabIds`).
 *
 * DRAWN AS EVERY TAB OF THE APP IS (user's request, 2026-10-07): the pill of `ui/tabs`, the
 * chosen one the sunk tint. These were underlined, on a rule across the screen, and the app
 * had two kinds of tab for one job — «Generar» / «Mis ejercicios» beside «Conversaciones» /
 * «Criterios». What stays of their own is the panel ids and the focus moving with the arrows.
 * Arrows, Home and End move the choice and the focus with it; only the chosen tab is in the
 * tab order.
 */
export function TabStrip<T extends string>({
  items,
  value,
  onChange,
  label,
  id,
  className,
}: {
  items: TabStripItem<T>[];
  value: T;
  onChange: (next: T) => void;
  /** What the row of tabs is, for a screen reader: the screen's own title reads well. */
  label: string;
  /** Names each tab and the panel it controls (`tabIds`); without it the tabs name none. */
  id?: string;
  className?: string;
}) {
  const buttons = useRef(new Map<T, HTMLButtonElement>());

  const go = (next: T) => {
    onChange(next);
    buttons.current.get(next)?.focus();
  };
  const move = (delta: number) => {
    const index = items.findIndex((item) => item.value === value);
    if (index < 0) return;
    go(items[(index + delta + items.length) % items.length].value);
  };

  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 overflow-x-auto rounded-xl p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
      onKeyDown={(event) => {
        if (event.key === "ArrowRight") move(1);
        else if (event.key === "ArrowLeft") move(-1);
        else if (event.key === "Home") go(items[0].value);
        else if (event.key === "End") go(items[items.length - 1].value);
        else return;
        event.preventDefault();
      }}
    >
      {items.map((item) => {
        const chosen = item.value === value;
        const ids = id ? tabIds(id, item.value) : null;
        return (
          <button
            key={item.value}
            ref={(node) => {
              if (node) buttons.current.set(item.value, node);
              else buttons.current.delete(item.value);
            }}
            type="button"
            role="tab"
            id={ids?.tab}
            aria-controls={ids?.panel}
            aria-selected={chosen}
            tabIndex={chosen ? 0 : -1}
            onClick={() => onChange(item.value)}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              chosen ? "bg-sunk text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            {item.label}
            {/* The count as the other tabs write theirs: a quiet figure beside the name. */}
            {item.count ? <span className="nums text-small text-muted-foreground">{item.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

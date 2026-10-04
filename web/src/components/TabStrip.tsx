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
 * A row of underlined tabs under a screen's header, each with an optional count.
 *
 * The underline and not the pill of `ui/tabs`: these split ONE screen into the work and its
 * record («Encargar evaluación» / «Mis evaluaciones», «Generar» / «Mis ejercicios»), and the
 * rule they sit on is the edge of the panel they switch. Arrows, Home and End move the
 * choice and the focus with it; only the chosen tab is in the tab order.
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
      className={cn("flex border-b border-border", className)}
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
              "-mb-px flex items-center gap-2 border-b-2 px-4 pt-2.5 pb-3 text-body transition-colors",
              chosen
                ? "border-primary font-semibold text-foreground"
                : "border-transparent font-medium text-muted-foreground hover:text-foreground",
            )}
          >
            {item.label}
            {item.count ? (
              // A count is a fact, not an action: it wears the ink. The one "act here"
              // colour is the screen's to spend on the thing to do.
              <span className="inline-grid h-[18px] min-w-5 place-items-center rounded-full bg-ink px-1.5 text-[12px] font-semibold text-ink-foreground nums">
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

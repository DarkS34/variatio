import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

import type { FeatureTone } from "./tone";

export interface TabItem {
  value: string;
  label: ReactNode;
  badge?: ReactNode;
  /** Drawn in that function's own colour, as the navbar draws its door. */
  tone?: FeatureTone;
  /** A vertical rule before the tab, setting it apart from the ones on its left. */
  separated?: boolean;
}

/** A tab in its function's colour, chosen and not: literal strings, so Tailwind finds them.
 *  Chosen is the sunk tint warmed with the colour, never a relief: a tab is a small thing. */
const TAB_TONE: Record<FeatureTone, { chosen: string; idle: string }> = {
  evaluation: {
    chosen:
      "bg-[color-mix(in_oklab,var(--evaluation)_12%,var(--sunk))] text-evaluation",
    idle: "text-evaluation hover:bg-[color-mix(in_oklab,var(--evaluation)_8%,transparent)]",
  },
  tutor: {
    chosen:
      "bg-[color-mix(in_oklab,var(--tutor)_12%,var(--sunk))] text-tutor",
    idle: "text-tutor hover:bg-[color-mix(in_oklab,var(--tutor)_8%,transparent)]",
  },
};

export function Tabs({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem[];
  value: string;
  onChange: (next: string) => void;
  className?: string;
}) {
  const move = (delta: number) => {
    const index = items.findIndex((item) => item.value === value);
    if (index < 0) return;
    // Wrapping, which is what the pattern specifies: from the last one, -> returns to the
    // first.
    onChange(items[(index + delta + items.length) % items.length].value);
  };

  return (
    <div
      role="tablist"
      // `max-w-full` plus the scroller is what keeps six tabs usable on a phone without
      // making the pill span the width of a desktop: it still shrinks to its content, it
      // simply stops growing past the parent and scrolls sideways from there.
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 overflow-x-auto rounded-xl p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        className,
      )}
      // The roles were here without any of the behaviour they promise. Someone navigating
      // by keyboard expects the arrows to move between tabs, and instead had to Tab
      // through all of them to reach the content: a role that lies is worse than no role,
      // because the screen reader announces a contract that does not exist.
      onKeyDown={(event) => {
        if (event.key === "ArrowRight") {
          event.preventDefault();
          move(1);
        } else if (event.key === "ArrowLeft") {
          event.preventDefault();
          move(-1);
        } else if (event.key === "Home") {
          event.preventDefault();
          onChange(items[0].value);
        } else if (event.key === "End") {
          event.preventDefault();
          onChange(items[items.length - 1].value);
        }
      }}
    >
      {items.map((item) => [
        item.separated ? (
          <span
            key={`${item.value}-rule`}
            aria-hidden="true"
            className="mx-1 h-5 w-px shrink-0 self-center bg-border"
          />
        ) : null,
        <button
          key={item.value}
          role="tab"
          aria-selected={value === item.value}
          // Only the active tab is in the tab order; the rest are reached with the arrows.
          // That is the other half of the pattern, and without it a bar of six tabs is
          // six stops before the content.
          tabIndex={value === item.value ? 0 : -1}
          onClick={() => onChange(item.value)}
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            item.tone
              ? value === item.value
                ? TAB_TONE[item.tone].chosen
                : TAB_TONE[item.tone].idle
              : value === item.value
                ? "bg-sunk text-foreground"
                : "text-muted-foreground hover:text-foreground",
          )}
        >
          {item.label}
          {item.badge}
        </button>,
      ])}
    </div>
  );
}

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface TabItem {
  value: string;
  label: ReactNode;
  badge?: ReactNode;
}

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
      // `max-w-full` plus the scroller is what keeps five tabs usable on a phone without
      // making the pill span the width of a desktop: it still shrinks to its content, it
      // simply stops growing past the parent and scrolls sideways from there.
      className={cn(
        "inline-flex max-w-full items-center gap-1 overflow-x-auto rounded-lg bg-muted p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
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
      {items.map((item) => (
        <button
          key={item.value}
          role="tab"
          aria-selected={value === item.value}
          // Only the active tab is in the tab order; the rest are reached with the arrows.
          // That is the other half of the pattern, and without it a bar of five tabs is
          // five stops before the content.
          tabIndex={value === item.value ? 0 : -1}
          onClick={() => onChange(item.value)}
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            value === item.value
              ? "bg-background text-foreground shadow-raised"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {item.label}
          {item.badge}
        </button>
      ))}
    </div>
  );
}

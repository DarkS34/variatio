import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A switch, and the text beside it is part of it.
 *
 * THE LABEL IS A CHILD, NOT A STRING PROPERTY, and that is what the callers were missing.
 * This used to be a bare `<button aria-label={label}>` with no children, so every screen
 * wrote the words a second time in a `<span>` next to it — and that span was not a
 * `<label>`, so it did nothing. Measured before the fix: clicking "Restringir a un
 * currículo" left `aria-checked` at `false`, and the accessible name was announced twice
 * because the visible text repeated the `aria-label` verbatim.
 *
 * With `children` the whole row is the target — 36×20 px becomes the width of the
 * sentence — and the name comes from the text itself, so nothing is said twice. `label`
 * survives for the switches that genuinely have no visible text beside them (a table
 * row's own control), and is ignored when children are given.
 */
export function Switch({
  checked,
  onCheckedChange,
  disabled,
  label,
  children,
  className,
}: {
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
  children?: ReactNode;
  className?: string;
}) {
  const control = (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      // Only when there is no visible text: with children the `<label>` names it, and a
      // second name here is what the screen reader read twice.
      aria-label={children ? undefined : label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50",
        checked ? "bg-ink" : "bg-muted",
      )}
    >
      <span
        className={cn(
          "block size-4 rounded-full bg-card ring-1 ring-border transition-transform",
          checked ? "translate-x-4" : "translate-x-0.5",
        )}
      />
    </button>
  );

  if (!children) return control;

  return (
    <label
      className={cn(
        "inline-flex cursor-pointer items-center gap-2",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      {control}
      <span className="min-w-0">{children}</span>
    </label>
  );
}

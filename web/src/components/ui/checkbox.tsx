import { Check, Minus } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * A checkbox that belongs to this app's palette instead of to the browser's.
 *
 * `<input type="checkbox">` is unstyleable past a point and renders differently in every
 * engine, which is what made the bank's selection column look pasted in. This is a plain
 * button carrying the ARIA role, so it also gets the focus ring, the hover state and the
 * transition every other control here has.
 *
 * `indeterminate` is what a select-all needs: "some, not all" is a third state, and a
 * header box that shows it as unchecked lies about the selection below it.
 */
export function Checkbox({
  checked,
  indeterminate,
  onCheckedChange,
  disabled,
  label,
  className,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onCheckedChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
  className?: string;
}) {
  const marked = checked || Boolean(indeterminate);
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={indeterminate ? "mixed" : checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={(event) => {
        event.stopPropagation();
        onCheckedChange(!checked);
      }}
      className={cn(
        "relative inline-flex size-4 shrink-0 items-center justify-center rounded-[5px] border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-40",
        // The same 24 px target the (i) gets, and for the same reason: the bank draws 41
        // of these in a column sized to the box, so growing the box would re-space every
        // row of a forty-row table. The pseudo-element is only hit testing.
        "before:absolute before:-inset-1 before:content-['']",
        marked
          ? "border-ink bg-ink text-ink-foreground"
          : "border-input bg-transparent hover:border-primary/70 hover:bg-accent",
        className,
      )}
    >
      {indeterminate ? (
        <Minus className="size-3 stroke-[3.5]" />
      ) : checked ? (
        <Check className="size-3 stroke-[3.5]" />
      ) : null}
    </button>
  );
}

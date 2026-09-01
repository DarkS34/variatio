import { useLayoutEffect, useRef } from "react";
import type { InputHTMLAttributes, LabelHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

// The vertical padding is NOT shared. It used to be `py-2` here, on all three, while the
// two fixed-height controls also declared `h-9`: 36 px minus 2 of border minus 16 of
// padding leaves 18 px for a `text-body` line that needs 20, so every input and every select
// in the app clipped its own text by a pixel top and bottom — and the h-8 selects of the
// admin panel, with 14 px of room, clipped it by six. Height and padding are one decision
// and belong to whichever component fixes the height; only the textarea, which fixes none,
// keeps padding as its way of making room.
const field =
  "flex w-full rounded-md border border-input bg-background px-3 text-body shadow-none transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 read-only:cursor-default read-only:bg-muted/40";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(field, "h-9 py-1", className)} {...props} />;
}

/**
 * `autoGrow` makes the box the height of its own text, with no inner scrollbar.
 *
 * Opt-in and not the default, which is the whole design: a textarea holding a whole
 * transcribed page would grow to several thousand pixels and take the screen's scrollbar
 * with it. Where it IS right is a box being READ as much as written — the profile's field
 * descriptions and its writing rules, four to six lines each, which arrived clipped at two
 * with a scrollbar of their own, so reviewing what the builder wrote meant scrolling
 * inside every one of a dozen little windows (2026-09-01, explicit user request).
 *
 * `resize-none` goes with it: a handle that fights an effect resetting the height on every
 * keystroke is a control that does not work.
 */
export function Textarea({
  className,
  autoGrow = false,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { autoGrow?: boolean }) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Measured from `scrollHeight`, which needs the box collapsed first or it only ever
  // grows. It runs on `value` so a draft loaded from the server sizes itself on arrival,
  // not only once somebody types.
  useLayoutEffect(() => {
    const node = ref.current;
    if (!autoGrow || !node) return;
    const fit = () => {
      node.style.height = "auto";
      node.style.height = `${node.scrollHeight}px`;
    };
    fit();
    // AND ON EVERY CHANGE OF WIDTH, because the height of a paragraph is a function of it.
    // Sized once at one width and then narrowed — the stage screens do exactly that when
    // the verdict drawer opens beside them — the box keeps a height for a wrap that no
    // longer happens and clips its own last line, with `overflow-hidden` making sure
    // nothing says so.
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(fit);
    observer.observe(node);
    return () => observer.disconnect();
  }, [autoGrow, props.value]);

  return (
    <textarea
      ref={ref}
      className={cn(
        field,
        "min-h-20 py-2 leading-relaxed",
        autoGrow ? "resize-none overflow-hidden" : "resize-y",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(field, "h-9 cursor-pointer py-1 pr-8", className)} {...props} />;
}

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn("text-micro font-condensed uppercase text-muted-foreground", className)}
      {...props}
    />
  );
}

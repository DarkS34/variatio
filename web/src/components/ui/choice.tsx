import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "@/lib/utils";

/**
 * THE ONE PILL FOR CHOOSING ONE OPTION OF A FEW WORDS — who may use a function, whom an
 * invitation is for, the profile of an account, the language, the kind of account a reading
 * counts (user's request, 2026-10-07: the same choice was drawn five ways, from a filled button
 * to a pill with no mark at all).
 *
 * A square mark in front, filled on the one chosen, and the chosen pill in the ink border over
 * the sunk tint, as the type picker draws its choice. The ink of a WORD (`--primary`), not of
 * a fill: in dark `--ink` is a deep tile, and the chosen pill's edge and mark vanished. 36 px tall, the height of a field, so a
 * row of pills sits level with the selects beside it. An option that needs a sentence to explain
 * itself is a card (`CARD_CHOICE`), not a pill.
 *
 * Spread `useRadioGroup`'s `radio(value)` on it, inside a `role="radiogroup"`.
 */
export function ChoicePill({
  chosen,
  className,
  children,
  ref,
  ...props
}: Omit<ButtonHTMLAttributes<HTMLButtonElement>, "role"> & {
  chosen: boolean;
  ref?: Ref<HTMLButtonElement> | ((node: HTMLElement | null) => void);
}) {
  return (
    <button
      ref={ref as Ref<HTMLButtonElement>}
      type="button"
      role="radio"
      aria-checked={chosen}
      className={cn(
        "flex h-9 items-center gap-2 rounded-lg border px-3 text-left text-body transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "disabled:cursor-not-allowed disabled:opacity-60",
        chosen ? "border-primary bg-sunk" : "border-input hover:border-primary",
        className,
      )}
      {...props}
    >
      <ChoiceMark chosen={chosen} />
      {children}
    </button>
  );
}

/** The square a choice is marked with: filled on the one chosen. Pills and cards share it. */
export function ChoiceMark({ chosen, className }: { chosen: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("size-3 shrink-0 border-[1.5px]", chosen ? "border-primary bg-primary" : "border-input", className)}
    />
  );
}

/**
 * THE CARD FOR AN OPTION THAT TAKES A SENTENCE — the type of an exercise, a rung, the engine,
 * how a course ends. `.raised`, because it can be pressed; the chosen one pressed into its
 * block (`CARD_CHOSEN`) and marked with the square of `ChoiceMark` before its name, the same
 * mark the pills carry. Each list adds its padding and, where it is measured, its height.
 * The border stays, transparent: the generate form measured its cards' height with it.
 */
export const CARD_CHOICE =
  "raised border border-transparent text-left transition-[box-shadow,background-color] hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60";
export const CARD_CHOSEN = "shadow-well hover:bg-transparent";

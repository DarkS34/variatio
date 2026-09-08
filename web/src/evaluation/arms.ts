import type { Key } from "@/lib/i18n";

import type { EvaluationArm } from "./types";

/**
 * What each arm is, in the evaluator's words, and the colour it wears once revealed.
 *
 * The colours are `--arm-*`, the app's only categorical scale, and they are measured
 * rather than chosen — see the note beside them in `index.css`. They used to borrow the
 * state tokens (muted-foreground, success, primary), which told a nice story — the system
 * wearing the app's own colour, the commercial model a neutral outsider — and failed as an
 * encoding: gray against teal is ΔE 7.5 in normal vision, half the readable floor.
 *
 * `ARMS` order is also the order the palette was validated on, so anything that draws the
 * three arms side by side draws them in it. A SESSION holds two of them — the system and
 * one rival drawn by its seed — but the palette stays per arm, never per card: a recorded
 * session read beside a fresh one has to draw its arms the same way.
 *
 * They appear ONLY after the reveal. Before it the cards are deliberately
 * colourless, because a card wearing a colour is a card carrying information.
 */
export const ARM_META: Record<
  EvaluationArm,
  { labelKey: Key; shortKey: Key; colour: string; descriptionKey: Key }
> = {
  naive: {
    labelKey: "arm.naive",
    shortKey: "arm.naive.short",
    colour: "var(--arm-naive)",
    descriptionKey: "arm.naive.description",
  },
  rag: {
    labelKey: "arm.rag",
    shortKey: "arm.rag.short",
    colour: "var(--arm-rag)",
    descriptionKey: "arm.rag.description",
  },
  system: {
    labelKey: "arm.system",
    shortKey: "arm.system.short",
    colour: "var(--arm-system)",
    descriptionKey: "arm.system.description",
  },
};

/** Two letters since 2026-09-08; the third is what a session recorded with three still reads. */
export const POSITION_LETTERS = ["A", "B", "C"] as const;

export function letterFor(position: number): string {
  return POSITION_LETTERS[position - 1] ?? String(position);
}

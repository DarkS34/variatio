import type { Features } from "@/lib/types";

/**
 * An optional function, named by its own colour: the study's `--evaluation`, the tutor's
 * `--tutor`. A destination, not a state: a state's tone is `lib/status`'s `Tone`.
 */
export type FeatureTone = keyof Features;

/**
 * A door of the testing phase in its function's colour: the face (the colour as text, on the
 * bar's own ground — a door is a word, not a block) and the hover and active steps over it.
 * The active step is the bar's chosen tint (`--sunk`) warmed with the function's colour.
 *
 * One copy for the bar and for the guide's figure of the bar, so the figure cannot drift
 * from what it draws. Literal strings, one set per function, because Tailwind finds a class
 * only where the source spells it out: a `var(--${tone})` built at run time draws nothing.
 */
export const DOOR_TONE: Record<FeatureTone, { face: string; hover: string; active: string }> = {
  evaluation: {
    face: "text-evaluation",
    hover: "hover:bg-[color-mix(in_oklab,var(--evaluation)_8%,transparent)]",
    active: "bg-[color-mix(in_oklab,var(--evaluation)_12%,var(--sunk))]",
  },
  tutor: {
    face: "text-tutor",
    hover: "hover:bg-[color-mix(in_oklab,var(--tutor)_8%,transparent)]",
    active: "bg-[color-mix(in_oklab,var(--tutor)_12%,var(--sunk))]",
  },
};

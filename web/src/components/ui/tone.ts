import type { Features } from "@/lib/types";

/**
 * An optional function, named by its own colour: the study's `--evaluation`, the tutor's
 * `--tutor`. A destination, not a state: a state's tone is `lib/status`'s `Tone`.
 */
export type FeatureTone = keyof Features;

/**
 * A door of the testing phase in its function's colour: the face (text, inset ring and a
 * 9 % tint) and the hover and active steps over it.
 *
 * One copy for the bar and for the guide's figure of the bar, so the figure cannot drift
 * from what it draws. Literal strings, one set per function, because Tailwind finds a class
 * only where the source spells it out: a `var(--${tone})` built at run time draws nothing.
 */
export const DOOR_TONE: Record<FeatureTone, { face: string; hover: string; active: string }> = {
  evaluation: {
    face: "text-evaluation ring-1 ring-inset ring-[color-mix(in_oklab,var(--evaluation)_30%,transparent)] bg-[color-mix(in_oklab,var(--evaluation)_9%,transparent)]",
    hover: "hover:bg-[color-mix(in_oklab,var(--evaluation)_16%,transparent)]",
    active: "bg-[color-mix(in_oklab,var(--evaluation)_18%,transparent)]",
  },
  tutor: {
    face: "text-tutor ring-1 ring-inset ring-[color-mix(in_oklab,var(--tutor)_30%,transparent)] bg-[color-mix(in_oklab,var(--tutor)_9%,transparent)]",
    hover: "hover:bg-[color-mix(in_oklab,var(--tutor)_16%,transparent)]",
    active: "bg-[color-mix(in_oklab,var(--tutor)_18%,transparent)]",
  },
};

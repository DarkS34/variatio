/**
 * EVERY FUNCTION IN ONE COLOUR (`--function`), wherever something outside its screen names it:
 * a door of the bar, a card of «Funciones», a badge, a tab, a button that opens it. The face
 * (the colour as text, on the ground it sits on) and the hover and active steps over it; the
 * active step is the chosen tint (`--sunk`) warmed with the colour.
 *
 * One colour for the four since 2026-11-04 (the user's request): the evaluation's green and the
 * tutor's blue beside two doors in ink read as four kinds of thing, and an administrator sees
 * all four. What tells one function from another is its icon (`function-mark.tsx`).
 *
 * Literal strings, because Tailwind finds a class only where the source spells it out: a
 * `var(--${tone})` built at run time draws nothing.
 */
export const FUNCTION_TONE = {
  face: "text-function",
  hover: "hover:bg-[color-mix(in_oklab,var(--function)_8%,transparent)]",
  active: "bg-[color-mix(in_oklab,var(--function)_12%,var(--sunk))]",
} as const;

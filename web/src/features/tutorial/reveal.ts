/**
 * WHICH PART OF THE HEADER THE TUTORIAL HAS REACHED.
 *
 * The tutorial runs INSIDE the shell (2026-09-02, explicit user request), and the header
 * above it is the real one: as the deck advances, the elements it has explained are
 * unlocked and the one it is explaining is pointed at. The deck explains them in the order
 * they sit on the path — the four steps, then «Crear ejercicios», then «Comparar», and
 * last the two flanks, where the reader chooses or creates a subject and finds the account
 * menu — so the header fills in from the middle outwards, one slide at a time.
 *
 * Pure, and read from three places: the screen (to page), the shell (to draw the header)
 * and `App` (to route). The slide is the URL — `/tutorial` is the first and `/tutorial/N`
 * the Nth — so the header needs no store to know where the deck is.
 */

/** How many slides the deck has. `TutorialScreen`'s `SLIDES` must be this long. */
export const SLIDE_COUNT = 6;

export type NavGroup = "subject" | "prepare" | "generate" | "compare" | "account";

/** The slide (0-based) on which each part of the header is unlocked and pointed at. */
export const UNLOCK_AT: Record<NavGroup, number> = {
  prepare: 2,
  generate: 3,
  compare: 4,
  subject: 5,
  account: 5,
};

export interface Reveal {
  /** Whether the reader has been told what this is: before that it is a dim silhouette. */
  unlocked: boolean;
  /** Whether this slide is the one about it. */
  pointed: boolean;
}

export function revealOf(at: number, group: NavGroup): Reveal {
  const slide = UNLOCK_AT[group];
  return { unlocked: at >= slide, pointed: at === slide };
}

/** The slide a path names, 0-based, or null when the path is not the tutorial's. */
export function slideOf(path: string): number | null {
  if (path === "/tutorial") return 0;
  const match = /^\/tutorial\/(\d+)$/.exec(path);
  if (!match) return null;
  const n = Number(match[1]);
  return Math.min(SLIDE_COUNT, Math.max(1, n)) - 1;
}

/** The path of a slide, 0-based: the first is bare, the rest carry their number. */
export function slidePath(index: number): string {
  const n = Math.min(SLIDE_COUNT, Math.max(1, index + 1));
  return n === 1 ? "/tutorial" : `/tutorial/${n}`;
}

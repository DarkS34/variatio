/**
 * WHICH SLIDE OF THE DECK A PATH NAMES.
 *
 * The slide IS the URL — `/tutorial` is the first and `/tutorial/N` the Nth — so nothing
 * needs a store to know where the deck is: the screen pages by navigating, and `App`
 * routes by asking here. Pure, and the only home of the deck's length.
 *
 * IT USED TO SAY MORE (`reveal.ts`, 2026-09-02 to 2026-09-04). The deck ran under the real
 * header and unlocked its parts as it explained them, so this module also held the slide
 * each part was revealed on. The header is not drawn under the deck at all now (explicit
 * user request), so `UNLOCK_AT`, `NavGroup` and `revealOf` went with it and the file was
 * renamed after what is left.
 */

/** How many slides the deck has. `TutorialScreen`'s `SLIDES` must be this long. */
export const SLIDE_COUNT = 6;

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

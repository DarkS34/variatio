import type { DocumentOriginal, DocumentPages, Unpaired } from "../types";

/**
 * Where a pane of the reader stands, how to bring a page under its top edge, and what the
 * payload says of the original.
 *
 * The two panes of the reader — the original's pages and the transcription's — scroll each
 * in its own box. Where they pair page to page, the page one of them stands on is the page
 * the other is brought to; these are the measures both sides use.
 */

/** A4 upright, for a page whose shape the server did not send. */
const DEFAULT_RATIO = 297 / 210;
const UNPAIRED: Unpaired[] = ["moved", "source", "count"];

/**
 * What the payload says of the original, or null: an older API sends none, and a document
 * the server cannot draw sends null. Then the transcription is all the reader has. A payload
 * that does not say the two pair is read as not pairing.
 */
export function originalOf(listing: DocumentPages): DocumentOriginal | null {
  const sent = listing.original;
  const pages = sent?.pages;
  const version = sent?.version;
  if (typeof pages !== "number" || pages < 1 || typeof version !== "string") return null;
  const ratios = Array.from({ length: pages }, (_, index) => {
    const ratio = Array.isArray(sent?.ratios) ? sent.ratios[index] : undefined;
    return typeof ratio === "number" && ratio > 0 ? ratio : DEFAULT_RATIO;
  });
  const paired = sent?.paired === true;
  const why = UNPAIRED.find((reason) => reason === sent?.unpaired) ?? null;
  return { pages, version, ratios, paired, unpaired: paired ? null : (why ?? "count") };
}

/** How far down what is visible the reader's eye is taken to be: the page there is the page read. */
export const READING_LINE = 0.25;
/** Between a pane's top edge and the page a jump lands on, in pixels. */
export const LANDING_GAP = 8;
/** A page must stay near the screen this long to be asked for, so dragging past it costs nothing. */
export const NEAR_DELAY_MS = 150;

/**
 * The page a reader scrolling the document stands on: the last one whose top edge has
 * passed `line`, the first while none has. `tops` are the pages' top edges in order.
 */
export function pageAt(tops: number[], line: number): number {
  let page = 1;
  for (let index = 0; index < tops.length; index += 1) {
    if (tops[index] <= line) page = index + 1;
  }
  return page;
}

/** A page number kept inside a document of `count` pages; the first page for anything unreadable. */
export function clampPage(page: number, count: number): number {
  if (!Number.isFinite(page) || count < 1) return 1;
  return Math.min(Math.max(Math.round(page), 1), count);
}

/**
 * The next page that needs looking at after `from`, going round to the start; null when no
 * page does. `needs` is one flag per page, the first page first.
 */
export function nextToReview(needs: boolean[], from: number): number | null {
  const count = needs.length;
  for (let step = 1; step <= count; step += 1) {
    const page = ((from - 1 + step) % count) + 1;
    if (needs[page - 1]) return page;
  }
  return null;
}

/**
 * The page a pane stands on: the one at its reading line, and the last once it is scrolled
 * to its end — a short last page never reaches the line.
 */
export function pageIn(box: HTMLElement, slots: Map<number, HTMLElement>, count: number): number {
  const scrolled = box.scrollTop > 0;
  if (scrolled && box.scrollTop + box.clientHeight >= box.scrollHeight - 2) return count;
  const line = box.getBoundingClientRect().top + box.clientHeight * READING_LINE;
  const tops = Array.from(
    { length: count },
    (_, at) => slots.get(at + 1)?.getBoundingClientRect().top ?? Infinity,
  );
  return pageAt(tops, line);
}

/** Scroll a pane so page `number` starts just under its top edge; true when it moved. */
export function scrollToPage(
  box: HTMLElement | null,
  slots: Map<number, HTMLElement>,
  number: number,
): boolean {
  const slot = slots.get(number);
  if (!box || !slot) return false;
  const before = box.scrollTop;
  // The first page is the top of the pane, its padding included.
  if (number <= 1) box.scrollTop = 0;
  else box.scrollTop += slot.getBoundingClientRect().top - box.getBoundingClientRect().top - LANDING_GAP;
  return box.scrollTop !== before;
}

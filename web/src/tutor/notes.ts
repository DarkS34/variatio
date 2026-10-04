import type { NotesDocument, NotesSection, Place } from "./types";

/** A4 upright, for a page whose shape the server did not send. */
const DEFAULT_RATIO = 297 / 210;

/**
 * The document itself, when the server can draw its pages: how many, of which version, and
 * each page's height over its width, which lays the document out before a page arrives.
 */
export interface Original {
  pages: number;
  version: string;
  ratios: number[];
}

/**
 * What the payload says of the original, or null: an older API sends none, and a document
 * the server cannot draw sends null. Then the transcription is all the reader has.
 */
export function originalOf(notes: NotesDocument): Original | null {
  const pages = notes.original?.pages;
  const version = notes.original?.version;
  if (typeof pages !== "number" || pages < 1 || typeof version !== "string") return null;
  const sent = notes.original?.ratios;
  const ratios = Array.from({ length: pages }, (_, index) => {
    const ratio = Array.isArray(sent) ? sent[index] : undefined;
    return typeof ratio === "number" && ratio > 0 ? ratio : DEFAULT_RATIO;
  });
  return { pages, version, ratios };
}

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

/**
 * The section a place points at: the one with its exact path, else the first one under it
 * (a unit's heading has no text of its own), else the start of the document.
 */
export function sectionOf(notes: NotesDocument, location: string): number {
  if (!location) return 0;
  const exact = notes.sections.findIndex((section) => section.location === location);
  if (exact >= 0) return exact;
  const under = notes.sections.findIndex((section) => section.location.startsWith(`${location} > `));
  return under >= 0 ? under : 0;
}

/** The page a section starts on, kept inside the document; the first page when it names none. */
export function pageOf(sections: NotesSection[], index: number, pages: number): number {
  const page = sections[index]?.page;
  return typeof page === "number" ? Math.min(Math.max(page, 1), pages) : 1;
}

/**
 * The section the reader stands on at `page`: the one it held if that one starts there,
 * else the first that starts on the page, else the last that started before it.
 *
 * Held first, because several sections may start on one page and the one the student chose
 * must not change under them. The first of the page next, because a reader who scrolls onto
 * a page meets its first heading before any other.
 */
export function sectionAtPage(sections: NotesSection[], page: number, held: number): number {
  const start = (index: number) => sections[index]?.page ?? 1;
  if (held >= 0 && held < sections.length && start(held) === page) return held;
  let before = 0;
  for (let index = 0; index < sections.length; index += 1) {
    if (start(index) === page) return index;
    if (start(index) < page) before = index;
  }
  return before;
}

/** What names a place in the list of sections: its path, or the document for text before any heading. */
export function sectionLabel(section: NotesSection, place: Pick<Place, "document">): string {
  return section.location || place.document;
}

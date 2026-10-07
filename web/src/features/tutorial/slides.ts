import type { ReactNode } from "react";

import type { Key } from "@/lib/i18n";
import type { Features } from "@/lib/types";

/**
 * Which slide of the deck a path names, and which slides the deck has.
 *
 * The slide IS the URL — `/tutorial` is the first and `/tutorial/N` the Nth — so nothing
 * needs a store to know where the deck is: the screen pages by navigating and `App` routes
 * by asking here. Pure, and the only home of the deck's shape and so of its length.
 */

/**
 * Every slide, in order, the function it belongs to and who it speaks to.
 *
 * Two decks share the end. A teacher's opens on the construction (s1–s4); a student's on
 * what the student has to hand (st1–st4: welcome, the syllabus, generating and, when it is
 * open to them, the tutor). The last two are the study's — what evaluating is, and the part
 * a participant plays in it — shown to either when the evaluation is open to them.
 * `TutorialScreen` keeps one slide per id of the product's, and the study's two are the
 * evaluation's code (`evaluation/tutorial.tsx`), fetched only for an account it is open to;
 * the types check both halves.
 */
export const DECK = [
  { id: "s1", feature: null, audience: "teacher" },
  { id: "s2", feature: null, audience: "teacher" },
  { id: "s3", feature: null, audience: "teacher" },
  { id: "s4", feature: null, audience: "teacher" },
  { id: "st1", feature: null, audience: "student" },
  { id: "st2", feature: null, audience: "student" },
  { id: "st3", feature: null, audience: "student" },
  { id: "st4", feature: "tutor", audience: "student" },
  { id: "s5", feature: "evaluation", audience: "all" },
  { id: "s6", feature: "evaluation", audience: "all" },
] as const satisfies readonly {
  id: string;
  feature: null | keyof Features;
  audience: "teacher" | "student" | "all";
}[];

export type SlideId = (typeof DECK)[number]["id"];

/** The slides one function's folder hands the deck: the evaluation's, fetched with its code. */
export type SlideIdOf<F extends keyof Features> = Extract<
  (typeof DECK)[number],
  { feature: F }
>["id"];

/** The product's own slides: every slide the evaluation's folder does not hand the deck. */
export type CoreSlideId = Exclude<(typeof DECK)[number], { feature: "evaluation" }>["id"];

/**
 * A point of a slide, and the one that is MARKED (`TutorialScreen` says why only one is).
 */
export type Point = Key | { key: Key; mark: true };

/** What one slide draws, top to bottom; `TutorialScreen` sets it. */
export interface Slide {
  title: Key;
  /** The lead: the sentence of the slide. */
  body: Key;
  figure?: ReactNode;
  /** Short paragraphs under the figure, each its own point. */
  points?: Point[];
  /** One aside, set apart: the thing that is true but is not an instruction. */
  aside?: Key;
  /** Only the index slide: the four steps of the construction, as a numbered list. */
  steps?: boolean;
}

/** The slides this account is shown, in order: its own deck, and what is open to it. */
export function deckFor(features: Features, student = false): SlideId[] {
  return DECK.filter(
    (slide) =>
      (slide.feature === null || features[slide.feature]) &&
      (slide.audience === "all" || slide.audience === (student ? "student" : "teacher")),
  ).map((slide) => slide.id);
}

/** How many slides the deck has for this account: what every route and counter agrees on. */
export function slideCount(features: Features, student = false): number {
  return deckFor(features, student).length;
}

/**
 * The slide a path names, 0-based, or null when the path is not the tutorial's.
 *
 * A number past the end opens the last slide: an old link to `/tutorial/6` from an account
 * shown four lands where the deck ends, never on a 404.
 */
export function slideOf(path: string, count: number): number | null {
  if (path === "/tutorial") return 0;
  const match = /^\/tutorial\/(\d+)$/.exec(path);
  if (!match) return null;
  const n = Number(match[1]);
  return Math.min(count, Math.max(1, n)) - 1;
}

/** The path of a slide, 0-based: the first is bare, the rest carry their number. */
export function slidePath(index: number, count: number): string {
  const n = Math.min(count, Math.max(1, index + 1));
  return n === 1 ? "/tutorial" : `/tutorial/${n}`;
}

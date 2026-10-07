import { describe, expect, it } from "vitest";

import { DECK, deckFor, slideCount, slideOf, slidePath } from "./slides";

const ALL = { evaluation: true, tutor: true };
const NONE = { evaluation: false, tutor: false };

describe("slideOf / slidePath", () => {
  const count = slideCount(ALL);

  it("round-trips every slide", () => {
    for (let i = 0; i < count; i += 1) expect(slideOf(slidePath(i, count), count)).toBe(i);
  });

  it("the first slide is the bare path, and its numbered form means the same", () => {
    expect(slidePath(0, count)).toBe("/tutorial");
    expect(slideOf("/tutorial/1", count)).toBe(0);
  });

  it("clamps a number off either end instead of refusing it", () => {
    // An old link to a slide that no longer exists opens the last one, never a 404.
    expect(slideOf("/tutorial/0", count)).toBe(0);
    expect(slideOf("/tutorial/99", count)).toBe(count - 1);
    expect(slidePath(-3, count)).toBe("/tutorial");
    expect(slidePath(40, count)).toBe(`/tutorial/${count}`);
  });

  it("is null for anything that is not the tutorial", () => {
    expect(slideOf("/", count)).toBeNull();
    expect(slideOf("/tutorial/x", count)).toBeNull();
    expect(slideOf("/tutorials", count)).toBeNull();
    expect(slideOf("/tutorial/", count)).toBeNull();
  });
});

describe("deckFor", () => {
  it("shows a teacher the construction and, with the evaluation open, the study", () => {
    expect(deckFor(ALL)).toEqual(["s1", "s2", "s3", "s4", "s5", "s6"]);
    expect(slideCount(ALL)).toBe(6);
  });

  it("shows a student their own deck, the tutor's slide only with the tutor open", () => {
    expect(deckFor(ALL, true)).toEqual(["st1", "st2", "st3", "st4", "s5", "s6"]);
    expect(deckFor(NONE, true)).toEqual(["st1", "st2", "st3"]);
    expect(deckFor({ evaluation: false, tutor: true }, true)).toEqual(["st1", "st2", "st3", "st4"]);
  });

  it("gives every slide of the deck to somebody", () => {
    const shown = new Set([...deckFor(ALL), ...deckFor(ALL, true)]);
    expect([...shown].sort()).toEqual(DECK.map((slide) => slide.id).sort());
  });

  it("leaves the study's two slides out with the evaluation closed", () => {
    expect(deckFor(NONE)).toEqual(["s1", "s2", "s3", "s4"]);
    // The tutor has no slide of its own, so it changes nothing here.
    expect(deckFor({ evaluation: false, tutor: true })).toEqual(deckFor(NONE));
  });

  it("lands an old link to the study's slides on the last slide drawn", () => {
    const count = slideCount(NONE);
    expect(slideOf("/tutorial/5", count)).toBe(count - 1);
    expect(slideOf("/tutorial/6", count)).toBe(count - 1);
  });
});

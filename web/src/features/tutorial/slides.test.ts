import { describe, expect, it } from "vitest";

import { SLIDE_COUNT, slideOf, slidePath } from "./slides";

describe("slideOf / slidePath", () => {
  it("round-trips every slide", () => {
    for (let i = 0; i < SLIDE_COUNT; i += 1) expect(slideOf(slidePath(i))).toBe(i);
  });

  it("the first slide is the bare path, and its numbered form means the same", () => {
    expect(slidePath(0)).toBe("/tutorial");
    expect(slideOf("/tutorial/1")).toBe(0);
  });

  it("clamps a number off either end instead of refusing it", () => {
    // An old link to a slide that no longer exists opens the last one, never a 404.
    expect(slideOf("/tutorial/0")).toBe(0);
    expect(slideOf("/tutorial/99")).toBe(SLIDE_COUNT - 1);
    expect(slidePath(-3)).toBe("/tutorial");
    expect(slidePath(40)).toBe(`/tutorial/${SLIDE_COUNT}`);
  });

  it("is null for anything that is not the tutorial", () => {
    expect(slideOf("/")).toBeNull();
    expect(slideOf("/tutorial/x")).toBeNull();
    expect(slideOf("/tutorials")).toBeNull();
    expect(slideOf("/tutorial/")).toBeNull();
  });
});


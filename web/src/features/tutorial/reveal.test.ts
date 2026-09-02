import { describe, expect, it } from "vitest";

import { SLIDE_COUNT, UNLOCK_AT, revealOf, slideOf, slidePath, type NavGroup } from "./reveal";

const GROUPS = Object.keys(UNLOCK_AT) as NavGroup[];

describe("slideOf / slidePath", () => {
  it("round-trips every slide", () => {
    for (let i = 0; i < SLIDE_COUNT; i += 1) expect(slideOf(slidePath(i))).toBe(i);
  });

  it("the first slide is the bare path, and its numbered form means the same", () => {
    expect(slidePath(0)).toBe("/tutorial");
    expect(slideOf("/tutorial/1")).toBe(0);
  });

  it("clamps a number off either end instead of refusing it", () => {
    // Un enlace viejo a una diapositiva que ya no existe abre la última, no un 404.
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

describe("revealOf", () => {
  it("unlocks nothing on the first two slides, everything on the last", () => {
    for (const group of GROUPS) {
      expect(revealOf(0, group).unlocked).toBe(false);
      expect(revealOf(1, group).unlocked).toBe(false);
      expect(revealOf(SLIDE_COUNT - 1, group).unlocked).toBe(true);
    }
  });

  it("points at a group on exactly the slide that unlocks it", () => {
    for (const group of GROUPS) {
      for (let at = 0; at < SLIDE_COUNT; at += 1) {
        expect(revealOf(at, group).pointed).toBe(at === UNLOCK_AT[group]);
      }
    }
  });

  it("never points at something still locked, and never locks again", () => {
    for (const group of GROUPS) {
      let seen = false;
      for (let at = 0; at < SLIDE_COUNT; at += 1) {
        const r = revealOf(at, group);
        if (r.pointed) expect(r.unlocked).toBe(true);
        if (seen) expect(r.unlocked).toBe(true);
        seen = seen || r.unlocked;
      }
    }
  });

  it("follows the order of the path: the steps, then phase 2, then phase 3, then the flanks", () => {
    expect(UNLOCK_AT.prepare).toBeLessThan(UNLOCK_AT.generate);
    expect(UNLOCK_AT.generate).toBeLessThan(UNLOCK_AT.compare);
    expect(UNLOCK_AT.compare).toBeLessThan(UNLOCK_AT.subject);
    expect(UNLOCK_AT.subject).toBe(UNLOCK_AT.account);
    // Y la última diapositiva es la que abre las dos alas: no hay nada que explicar después.
    expect(UNLOCK_AT.subject).toBe(SLIDE_COUNT - 1);
  });
});

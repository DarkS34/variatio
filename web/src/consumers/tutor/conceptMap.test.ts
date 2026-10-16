import { describe, expect, it } from "vitest";

import { curve, isDrawable, pointsIn, rail, reviewOf, sideOf, type ConceptMapData } from "./conceptMap";

const MAP: ConceptMapData = {
  concept: "Recursividad",
  unit: "Recursividad",
  before: ["Función", "Algoritmia"],
  after: ["Subproblema"],
  links: [
    { name: "Caso base", relation: "se engloba en", direction: "in" },
    { name: "Subprograma", relation: "se engloba en", direction: "out" },
    { name: "Factorial", relation: "se relaciona con", direction: "both" },
  ],
  hidden: { before: 0, after: 2, links: 5 },
  review: null,
};

const CONCEPT = { left: 200, top: 100, right: 320, bottom: 136 };

describe("sideOf", () => {
  it("reads where the layout put a node, beside the concept or over and under it", () => {
    expect(sideOf({ left: 20, top: 40, right: 150, bottom: 70 }, CONCEPT)).toBe("left");
    expect(sideOf({ left: 380, top: 160, right: 500, bottom: 190 }, CONCEPT)).toBe("right");
    expect(sideOf({ left: 180, top: 20, right: 340, bottom: 60 }, CONCEPT)).toBe("above");
    expect(sideOf({ left: 30, top: 200, right: 260, bottom: 230 }, CONCEPT)).toBe("below");
  });
});

describe("the lines", () => {
  it("curves level out of one point and into the other", () => {
    expect(curve(150, 55, 182, 118)).toBe("M150 55C166 55 166 118 182 118");
  });

  it("runs a rail down the left and rounds both turns", () => {
    expect(rail(197, 118, 8, 30, 260)).toBe("M197 118H16Q8 118 8 126V252Q8 260 16 260H30");
  });

  it("draws on the half pixel, where a one-pixel line is crisp", () => {
    expect(curve(10.3, 20.74, 40.1, 20.74)).toBe("M10.5 20.5C25 20.5 25 20.5 40 20.5");
  });
});

describe("the map's reading", () => {
  it("puts a relation pointing into the concept on its left, every other on its right", () => {
    expect((MAP.links ?? []).map(pointsIn)).toEqual([true, false, false]);
  });

  it("names the prerequisite to go over only when the map draws it", () => {
    expect(reviewOf({ ...MAP, review: "Función" })).toBe("Función");
    expect(reviewOf({ ...MAP, review: "Pila" })).toBeNull();
    expect(reviewOf(MAP)).toBeNull();
  });

  it("draws a concept with something before or after it, and nothing else", () => {
    expect(isDrawable(MAP)).toBe(true);
    expect(isDrawable({ concept: "Sola", before: [], after: [] })).toBe(false);
    expect(isDrawable({ concept: "Sola", after: ["Otra"] })).toBe(true);
    expect(isDrawable(null)).toBe(false);
    expect(isDrawable({ concept: "" } as ConceptMapData)).toBe(false);
  });
});

import { describe, expect, it } from "vitest";

import { LabelGrid } from "./labels";

describe("LabelGrid", () => {
  it("refuses a name over one already placed and takes one beside it", () => {
    const grid = new LabelGrid(8);
    grid.reset(400, 300);
    expect(grid.place(10, 10, 110, 24)).toBe(true);
    expect(grid.place(60, 16, 160, 30)).toBe(false);
    expect(grid.place(10, 40, 110, 54)).toBe(true);
  });

  it("draws the name a person asked for whatever is under it", () => {
    const grid = new LabelGrid(8);
    grid.reset(400, 300);
    grid.place(10, 10, 110, 24);
    expect(grid.place(20, 12, 90, 22, true)).toBe(true);
    // …and what it covers is taken for the ones after it.
    expect(grid.place(95, 12, 140, 22)).toBe(false);
  });

  it("refuses a box wholly off the canvas and clips one half on it", () => {
    const grid = new LabelGrid(8);
    grid.reset(400, 300);
    expect(grid.place(-200, 10, -100, 24)).toBe(false);
    expect(grid.place(420, 10, 500, 24)).toBe(false);
    expect(grid.place(-40, 10, 40, 24)).toBe(true);
    expect(grid.place(0, 12, 30, 20)).toBe(false);
  });

  it("forgets everything on reset, at the same size or a smaller one", () => {
    const grid = new LabelGrid(8);
    grid.reset(400, 300);
    grid.place(0, 0, 399, 299);
    grid.reset(400, 300);
    expect(grid.place(100, 100, 200, 120)).toBe(true);
    grid.reset(100, 100);
    expect(grid.place(10, 10, 90, 20)).toBe(true);
  });
});

import { describe, expect, it } from "vitest";

import { clampPage, nextToReview, originalOf, pageAt } from "./sync";

describe("pageAt", () => {
  it("is the last page whose top edge has passed the line, the first while none has", () => {
    expect(pageAt([100, 900, 1700], 50)).toBe(1);
    expect(pageAt([-600, 200, 1000], 250)).toBe(2);
    expect(pageAt([-2000, -1200, -400], 250)).toBe(3);
  });

  it("reads a page not laid out yet as below the line", () => {
    expect(pageAt([-300, Infinity, Infinity], 250)).toBe(1);
  });
});

describe("clampPage", () => {
  it("keeps a page inside the document", () => {
    expect(clampPage(0, 12)).toBe(1);
    expect(clampPage(40, 12)).toBe(12);
    expect(clampPage(3.6, 12)).toBe(4);
    expect(clampPage(Number.NaN, 12)).toBe(1);
  });
});

describe("nextToReview", () => {
  it("goes to the next page that needs looking at, round to the start", () => {
    const needs = [false, true, false, false, true];
    expect(nextToReview(needs, 1)).toBe(2);
    expect(nextToReview(needs, 2)).toBe(5);
    expect(nextToReview(needs, 5)).toBe(2);
  });

  it("finds nothing in a document with nothing to review", () => {
    expect(nextToReview([false, false], 1)).toBeNull();
    expect(nextToReview([], 1)).toBeNull();
  });
});

describe("originalOf", () => {
  const listing = (original: unknown) => ({ name: "a.pdf", pages: [], original } as never);

  it("reads the pages, their shapes and whether they pair", () => {
    expect(originalOf(listing({ pages: 2, version: "v1", ratios: [1.5], paired: true, unpaired: null }))).toEqual({
      pages: 2,
      version: "v1",
      ratios: [1.5, 297 / 210],
      paired: true,
      unpaired: null,
    });
  });

  it("has no original from an older API or for a document the server cannot draw", () => {
    expect(originalOf(listing(undefined))).toBeNull();
    expect(originalOf(listing(null))).toBeNull();
    expect(originalOf(listing({ pages: 0, version: "v1" }))).toBeNull();
  });

  it("reads a payload that does not say the two pair as not pairing", () => {
    const found = originalOf(listing({ pages: 1, version: "v1", ratios: [1.4] }));
    expect(found?.paired).toBe(false);
    expect(found?.unpaired).toBe("count");
    expect(originalOf(listing({ pages: 1, version: "v1", paired: false, unpaired: "moved" }))?.unpaired).toBe("moved");
  });
});

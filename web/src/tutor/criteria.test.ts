import { describe, expect, it } from "vitest";

import { changes } from "./criteria";

describe("changes", () => {
  const rows = ["a", "b", "c", "d"].map((text) => ({ text }));

  it("counts nothing for the same rows", () => {
    expect(changes(rows, structuredClone(rows))).toBe(0);
  });

  it("counts a row taken out of the middle once", () => {
    expect(changes(rows, [rows[0], rows[2], rows[3]])).toBe(1);
  });

  it("counts a rewritten row once, and an added one beside it", () => {
    expect(changes(rows, [rows[0], { text: "B" }, rows[2], rows[3]])).toBe(1);
    expect(changes(rows, [rows[0], { text: "B" }, rows[2], rows[3], { text: "" }])).toBe(2);
  });

  it("tells two equal rows from one", () => {
    expect(changes([rows[0], rows[0]], [rows[0]])).toBe(1);
  });
});

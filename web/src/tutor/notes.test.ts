import { describe, expect, it } from "vitest";

import { originalOf, pageAt, pageOf, sectionAtPage, sectionOf } from "./notes";
import type { NotesDocument } from "./types";

const NOTES: NotesDocument = {
  document: "apuntes.pdf",
  original: { pages: 9, version: "abc" },
  sections: [
    { location: "Tema 1 > Variables", text: "…", page: 2 },
    { location: "Tema 1 > Tipos", text: "…", page: 2 },
    { location: "Tema 2 > Funciones", text: "…", page: 5 },
    { location: "Tema 2 > Recursividad", text: "…", page: 8 },
  ],
};

describe("the original of a document of the notes", () => {
  it("is read only when the server says how many pages it has and of which version", () => {
    expect(originalOf(NOTES)).toMatchObject({ pages: 9, version: "abc" });
    expect(originalOf({ ...NOTES, original: null })).toBeNull();
    expect(originalOf({ document: "a.pdf", sections: [] })).toBeNull();
    expect(originalOf({ ...NOTES, original: { pages: 0, version: "abc" } })).toBeNull();
  });

  it("gives every page a shape, the server's or an upright sheet's", () => {
    const sent = originalOf({ ...NOTES, original: { pages: 3, version: "abc", ratios: [0.5625, 0] } });
    expect(sent?.ratios).toEqual([0.5625, 297 / 210, 297 / 210]);
    expect(originalOf(NOTES)?.ratios).toHaveLength(9);
  });

  it("stands on the last page whose top has passed the reading line", () => {
    expect(pageAt([0, 500, 1000], 120)).toBe(1);
    expect(pageAt([-900, -400, 100], 120)).toBe(3);
    expect(pageAt([-400, 121, 700], 120)).toBe(1);
    expect(pageAt([300, 800], 120)).toBe(1);
  });

  it("opens a place on the page its section starts on, inside the document", () => {
    expect(pageOf(NOTES.sections, sectionOf(NOTES, "Tema 2 > Funciones"), 9)).toBe(5);
    expect(pageOf(NOTES.sections, sectionOf(NOTES, "Tema 2"), 9)).toBe(5);
    expect(pageOf(NOTES.sections, 3, 6)).toBe(6);
    expect(pageOf([{ location: "", text: "…" }], 0, 9)).toBe(1);
  });

  it("keeps the section held on its own page, else the first of the page, else the last before it", () => {
    expect(sectionAtPage(NOTES.sections, 2, 0)).toBe(0);
    expect(sectionAtPage(NOTES.sections, 2, 1)).toBe(1);
    expect(sectionAtPage(NOTES.sections, 2, 3)).toBe(0);
    expect(sectionAtPage(NOTES.sections, 4, 0)).toBe(1);
    expect(sectionAtPage(NOTES.sections, 5, 1)).toBe(2);
    expect(sectionAtPage(NOTES.sections, 9, 0)).toBe(3);
    expect(sectionAtPage(NOTES.sections, 1, 3)).toBe(0);
  });
});

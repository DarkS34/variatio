import { describe, expect, it } from "vitest";

import { isDrawableDiagram } from "@/lib/diagram";

import { conceptMapSource, isDrawable, narrowed, type ConceptMapData } from "./conceptMap";

const WORDS = { before: "Se da por sabido", after: "Viene después", more: (n: number) => `y ${n} más` };

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

describe("conceptMapSource", () => {
  it("draws the prerequisite relation in the order things are learnt", () => {
    const source = conceptMapSource(MAP, WORDS);
    expect(isDrawableDiagram(source)).toBe(true);
    expect(source).toContain('focus(["Recursividad"]):::focus');
    expect(source).toContain('subgraph before["Se da por sabido"]');
    expect(source).toContain('b0["Función"]:::known');
    expect(source).toContain("b0 --> focus");
    expect(source).toContain('a0["Subproblema"]:::later');
    expect(source).toContain("focus --> a0");
  });

  it("draws every other relation dotted, labelled and pointing the way the graph does", () => {
    const source = conceptMapSource(MAP, WORDS);
    expect(source).toContain('l0["Caso base"]:::tied -.->|"se engloba en"| focus');
    expect(source).toContain('focus -.->|"se engloba en"| l1["Subprograma"]:::tied');
    expect(source).toContain('focus -.-|"se relaciona con"| l2["Factorial"]:::tied');
  });

  it("counts what a cap left out instead of dropping it in silence", () => {
    const source = conceptMapSource(MAP, WORDS);
    expect(source).toContain('aMore["y 2 más"]:::more');
    expect(source).toContain('lMore["y 5 más"]:::more');
    expect(source).not.toContain("bMore");
  });

  it("gives the attention to the prerequisite to review, and to nothing else", () => {
    const source = conceptMapSource({ ...MAP, review: "Función" }, WORDS);
    expect(source).toContain('b0["Función"]:::review');
    expect(source).toContain('focus(["Recursividad"]):::anchor');
    expect(source).not.toContain(":::focus");
    const stray = conceptMapSource({ ...MAP, review: "No está" }, WORDS);
    expect(stray).toContain(":::focus");
  });

  it("keeps a concept's own punctuation out of Mermaid's syntax", () => {
    const source = conceptMapSource(
      { concept: 'Cadena "f"', before: ["range()", "`break`", "A#B\nC"] },
      WORDS,
      "TD",
    );
    expect(source).toContain("\nflowchart TD\n");
    expect(source).toContain('focus(["Cadena #quot;f#quot;"])');
    expect(source).toContain('b0["range()"]');
    expect(source).toContain('b1["#96;break#96;"]');
    expect(source).toContain('b2["A#35;B C"]');
  });

  it("stands each group in a column of its own when the map is drawn top-down", () => {
    const source = conceptMapSource(MAP, WORDS, "TD");
    expect(source).toContain("  b0 ~~~ b1");
    expect(source).toContain("  a0 ~~~ aMore");
    expect(source).toContain("  l1 ~~~ l2 ~~~ lMore");
    expect(conceptMapSource(MAP, WORDS, "LR")).not.toContain("~~~");
  });

  it("keeps the learning order alone on a narrow screen", () => {
    expect(narrowed(MAP).links).toEqual([]);
    expect(narrowed(MAP).before).toEqual(MAP.before);
    expect(conceptMapSource(narrowed(MAP), WORDS, "TD")).not.toContain("-.-");
  });

  it("has nothing to draw without a concept or without something before or after it", () => {
    expect(isDrawable(null)).toBe(false);
    expect(isDrawable({ concept: "Sola" })).toBe(false);
    expect(isDrawable({ concept: "", before: ["X"] })).toBe(false);
    expect(isDrawable({ concept: "Pila", links: MAP.links })).toBe(false);
    expect(isDrawable(MAP)).toBe(true);
  });
});

import { describe, expect, it } from "vitest";

import { domainColours } from "./domains";
import { domainColour } from "./format";
import type { KgConcept } from "./types";

const concept = (name: string, domain: string): KgConcept =>
  ({ name, domain, taggable: true, degree: 0, description: null, exemplars: 0,
     exemplars_by_type: {} }) as KgConcept;

// The server emits its concepts by walking `concepts_by_domains`, so the small domain
// that comes FIRST in the syllabus comes first here too. Ordering by size would put the
// big one first, and alphabetical order would put "Alfa" first.
const CONCEPTS = [
  concept("uno", "Zeta primero"),
  concept("dos", "Zeta primero"),
  concept("tres", "Alfa segundo"),
  concept("cuatro", "Media tercero"),
  concept("cinco", "Media tercero"),
  concept("seis", "Media tercero"),
];

describe("domainColours", () => {
  it("colours by first appearance, which is the order of the syllabus", () => {
    const colours = domainColours(CONCEPTS);
    expect(colours.get("Zeta primero")).toBe(domainColour(0, 3));
    expect(colours.get("Alfa segundo")).toBe(domainColour(1, 3));
    expect(colours.get("Media tercero")).toBe(domainColour(2, 3));
  });

  it("does not reorder by size", () => {
    const colours = domainColours(CONCEPTS);
    expect(colours.get("Media tercero")).not.toBe(domainColour(0, 3));
  });

  it("gives a colour to each distinct domain and no more", () => {
    expect(domainColours(CONCEPTS).size).toBe(3);
    expect(domainColours([]).size).toBe(0);
  });
});

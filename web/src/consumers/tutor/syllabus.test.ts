import { describe, expect, it } from "vitest";

import { searchSyllabus, unitOf, unitsOf } from "./syllabus";

const UNITS = [
  { name: "Modularidad", concepts: ["Función", "Procedimiento", "Llamada recursiva"] },
  { name: "Recursividad", concepts: ["Caso base", "Recursividad", "Árbol de llamadas"] },
];

describe("searchSyllabus", () => {
  it("finds a name whatever its accents and capitals, unit by unit in syllabus order", () => {
    expect(searchSyllabus(UNITS, "FUNCION")).toEqual([
      { number: 1, name: "Modularidad", concepts: ["Función"] },
    ]);
    expect(searchSyllabus(UNITS, "arbol")).toEqual([
      { number: 2, name: "Recursividad", concepts: ["Árbol de llamadas"] },
    ]);
  });

  it("asks for every word of the query, in any order", () => {
    expect(searchSyllabus(UNITS, "base caso")[0].concepts).toEqual(["Caso base"]);
    expect(searchSyllabus(UNITS, "caso bucle")).toEqual([]);
  });

  it("puts the names that start with the query before those that only hold it", () => {
    const [first, second] = searchSyllabus(UNITS, "rec");
    expect(first.concepts).toEqual(["Llamada recursiva"]);
    expect(second.concepts[0]).toBe("Recursividad");
  });

  it("brings a whole unit when the query names the unit", () => {
    expect(searchSyllabus(UNITS, "modular")[0].concepts).toEqual(UNITS[0].concepts);
  });

  it("finds nothing for an empty query", () => {
    expect(searchSyllabus(UNITS, "   ")).toEqual([]);
  });
});

describe("unitOf and unitsOf", () => {
  it("says which unit a concept belongs to", () => {
    expect(unitOf(UNITS, "Caso base")).toBe(1);
    expect(unitOf(UNITS, "No está")).toBe(-1);
    expect(unitOf(UNITS, null)).toBe(-1);
  });

  it("reads a payload defensively and drops what is not a unit with concepts", () => {
    expect(unitsOf(undefined)).toEqual([]);
    expect(unitsOf({ units: "no" })).toEqual([]);
    expect(
      unitsOf({ units: [{ name: "A", concepts: ["x", 3] }, { name: "B", concepts: [] }, null] }),
    ).toEqual([{ name: "A", concepts: ["x"] }]);
  });
});

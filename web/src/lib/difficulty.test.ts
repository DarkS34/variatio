import { describe, expect, it } from "vitest";

import { splitCriterion } from "./difficulty";

const ES = ["basico", "intermedio", "avanzado"];

// The real criterion of `cs0-ejercicios-clase`, shortened but with its punctuation intact.
const REAL =
  "Grado de exigencia del ejercicio. 'basico': una sola operación aritmética o fórmula " +
  "directa, sin bucles ni recursión (p. ej. calcular un discriminante). 'intermedio': " +
  "requiere bucles, condicionales o recursión simple. 'avanzado': requiere algoritmos no " +
  "triviales u optimización.";

describe("splitCriterion", () => {
  it("takes the axis apart from the rungs", () => {
    const { lead, rungs } = splitCriterion(REAL, ES);
    expect(lead).toBe("Grado de exigencia del ejercicio");
    expect(rungs.map((r) => r.level)).toEqual(ES);
    expect(rungs[0].text).toContain("una sola operación");
    expect(rungs[2].text).toBe("requiere algoritmos no triviales u optimización");
  });

  it("reads the shape the prompt legislates, « » and all", () => {
    const { lead, rungs } = splitCriterion(
      "Cuánto pide. «basico»: uno. «intermedio»: dos. «avanzado»: tres.",
      ES,
    );
    expect(lead).toBe("Cuánto pide");
    expect(rungs.map((r) => r.text)).toEqual(["uno", "dos", "tres"]);
  });

  it("folds accents and case, because a rung may be spelled either way", () => {
    const { rungs } = splitCriterion("Eje. Básico: uno. Intermedio: dos. Avanzado: tres.", ES);
    expect(rungs.map((r) => r.level)).toEqual(ES);
    expect(rungs[1].text).toBe("dos");
  });

  it("draws the rungs in the LADDER's order, not the text's", () => {
    const { rungs } = splitCriterion("«avanzado»: mucho. «basico»: poco.", ES);
    expect(rungs.map((r) => r.level)).toEqual(["basico", "avanzado"]);
  });

  // The old `cs0-examenes` shape: the rungs are named but never opened with a colon, so
  // there is nothing to split on and the paragraph is handed back whole.
  it("hands back a criterion it cannot split, rather than half of one", () => {
    const text = "Grado de complejidad: basico (secuencial), intermedio (bucles), avanzado (recursividad).";
    expect(splitCriterion(text, ES)).toEqual({ lead: text, rungs: [] });
  });

  it("needs two marks: one mention is not a criterion split three ways", () => {
    const text = "Grado de exigencia. basico: lo más sencillo que se pide.";
    expect(splitCriterion(text, ES)).toEqual({ lead: text, rungs: [] });
  });

  it("survives a criterion that opens straight on a rung", () => {
    const { lead, rungs } = splitCriterion("«basico»: uno. «intermedio»: dos.", ES);
    expect(lead).toBe("");
    expect(rungs).toHaveLength(2);
  });

  it("says nothing about nothing", () => {
    expect(splitCriterion(null, ES)).toEqual({ lead: "", rungs: [] });
    expect(splitCriterion("   ", ES)).toEqual({ lead: "", rungs: [] });
  });

  it("takes the ladder it is given, in any language", () => {
    const { rungs } = splitCriterion("Demand. «basic»: one. «advanced»: three.", [
      "basic",
      "intermediate",
      "advanced",
    ]);
    expect(rungs.map((r) => r.level)).toEqual(["basic", "advanced"]);
  });
});

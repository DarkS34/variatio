import { describe, expect, it } from "vitest";

import { progressByUnit } from "./courseProgress";

describe("progressByUnit", () => {
  it("counts each unit's covered concepts in the syllabus' order", () => {
    const units = [
      { name: "Fundamentos", concepts: ["Variable", "Función"] },
      { name: "Avanzado", concepts: ["Recursividad", "Memoización", "Notación"] },
      { name: "Vacía", concepts: [] },
    ];
    expect(progressByUnit(units, ["Función", "Variable", "Recursividad", "Otro"])).toEqual([
      { name: "Fundamentos", total: 2, covered: 2 },
      { name: "Avanzado", total: 3, covered: 1 },
      { name: "Vacía", total: 0, covered: 0 },
    ]);
  });
});

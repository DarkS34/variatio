import { describe, expect, it } from "vitest";

import type { ItemTypeSpec } from "@/lib/types";

import { difficultyFieldOf, difficultyLevelsOf, otherDecidedFields } from "./profile";

function modality(fields: Record<string, unknown>): ItemTypeSpec {
  return {
    label: "Modalidad",
    description: "",
    primary_field: "enunciado",
    fields: fields as ItemTypeSpec["fields"],
  } as ItemTypeSpec;
}

const STATEMENT = { schema: { type: "string" }, description: "El enunciado" };
const LADDER = { schema: { enum: ["basico", "intermedio", "avanzado"] }, description: "Eje" };

describe("the field every modality carries", () => {
  // THE REGRESSION THIS EXISTS FOR: `decided_by` is absent on every profile built before
  // the ladder became mandatory (4 of the 6 modalities of `cs0-examenes`), and the form
  // has to offer the rung on those too — reading it through `userDecidedFields` would
  // offer the choice on some instances and not on others.
  it("is offered whether or not the artifact says who decides it", () => {
    const old = modality({ enunciado: STATEMENT, nivel_dificultad: LADDER });
    expect(difficultyFieldOf(old)).toBe("nivel_dificultad");
    expect(difficultyLevelsOf(old)).toEqual(["basico", "intermedio", "avanzado"]);
  });

  it("is never asked twice: its own step, so out of the generic decisions", () => {
    const fresh = modality({
      enunciado: STATEMENT,
      formato: { schema: { enum: ["a", "b"] }, decided_by: "user" },
      nivel_dificultad: { ...LADDER, decided_by: "user" },
    });
    expect(otherDecidedFields(fresh)).toEqual(["formato"]);
  });

  it("knows the English name too, without being told the workspace's language", () => {
    const english = modality({ enunciado: STATEMENT, difficulty_level: LADDER });
    expect(difficultyFieldOf(english)).toBe("difficulty_level");
  });

  it("says nothing about a modality that declares none", () => {
    const bare = modality({ enunciado: STATEMENT });
    expect(difficultyFieldOf(bare)).toBeNull();
    expect(difficultyLevelsOf(bare)).toEqual([]);
    expect(otherDecidedFields(bare)).toEqual([]);
  });

  it("reads the rungs off the modality's own enum, never a table written here", () => {
    const renamed = modality({
      enunciado: STATEMENT,
      nivel_dificultad: { schema: { enum: ["suave", "medio", "duro"] } },
    });
    expect(difficultyLevelsOf(renamed)).toEqual(["suave", "medio", "duro"]);
  });
});

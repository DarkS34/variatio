import { describe, expect, it } from "vitest";

import { commissionLike, inputsOf, isRequired, orderedFields, valueOf } from "./exercise";

describe("what a teacher's exercise sends for each field", () => {
  it("asks for a field with no default that does not allow null", () => {
    expect(isRequired({ type: "string" })).toBe(true);
    expect(isRequired({ type: ["string", "null"] })).toBe(false);
    expect(isRequired({ type: "string", default: "" })).toBe(false);
    expect(isRequired({ enum: ["basico", "avanzado"] })).toBe(true);
  });

  it("writes a list one entry per line and an object as JSON", () => {
    expect(valueOf("uno\n\n dos ", { type: "array", items: { type: "string" } })).toEqual(["uno", "dos"]);
    expect(valueOf('{"a": 1}', { type: "object" })).toEqual({ a: 1 });
    expect(valueOf("no es json", { type: "object" })).toBeUndefined();
    expect(valueOf("3", { type: "integer" })).toBe(3);
    expect(valueOf("texto", { type: ["string", "null"] })).toBe("texto");
  });

  it("opens an exercise already written as the form edits it", () => {
    expect(inputsOf({ enunciado: "x", pasos: ["a", "b"], datos: { n: 2 } })).toEqual({
      enunciado: "x",
      pasos: "a\nb",
      datos: '{\n  "n": 2\n}',
    });
  });

  it("puts the statement first and keeps the profile's order", () => {
    const spec = {
      primary_field: "enunciado",
      fields: { solucion: { schema: {} }, enunciado: { schema: {} }, nivel: { schema: {} } },
    };
    expect(orderedFields(undefined, spec)).toEqual(["enunciado", "solucion", "nivel"]);
  });
});

describe("a commission like an exercise the class reads", () => {
  const type = {
    key: "ejercicio",
    label: "Ejercicio",
    description: "",
    primary_field: "enunciado",
    embed_fields: ["enunciado"],
    fields: ["enunciado", "solucion", "nivel_dificultad"],
    difficulty_field: "nivel_dificultad",
    difficulty_levels: ["basico", "avanzado"],
    count: 1,
  };
  const item = {
    id: "C001",
    item_type: "ejercicio",
    shown: ["enunciado"],
    enunciado: "Recorre la lista",
    nivel_dificultad: "avanzado",
    concepts: ["Bucles", "Listas"],
    primary_concept: "Listas",
  };

  it("takes its type, its level and its concepts, the one it is about first", () => {
    const form = commissionLike(item, type);
    expect(form.itemType).toBe("ejercicio");
    expect(form.concepts).toEqual(["Listas", "Bucles"]);
    expect(form.decisions).toEqual({ nivel_dificultad: "avanzado" });
    expect(form.instructions).toBe("");
  });

  it("asks no level of a type that declares none", () => {
    expect(commissionLike(item, { ...type, difficulty_field: null }).decisions).toEqual({});
    expect(commissionLike({ ...item, nivel_dificultad: undefined }, type).decisions).toEqual({});
  });
});

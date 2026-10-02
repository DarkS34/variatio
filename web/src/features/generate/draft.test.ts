import { describe, expect, it } from "vitest";

import type { GenerationRow } from "@/lib/types";

import { EMPTY_FORM } from "./commission";
import { fromGeneration } from "./draft";

/* «Generar más como este» reopens the commission as it was ASKED. A saved exercise keeps the
   level it was asked at since the exercises became files; a row from before kept only a
   bool, and that has to reopen at the default level rather than fail. */

function row(overrides: Partial<GenerationRow>): GenerationRow {
  return {
    id: "20261001T101530Z-abc123-1",
    created_at: 0,
    job_id: "abc123",
    item_type: "ejercicio",
    concepts: ["Función"],
    curriculum: [],
    fixed: {},
    instructions: "",
    think: true,
    model: null,
    author: { id: 1, name: "Ana", username: "ana" },
    promoted_item_id: null,
    item: {},
    ...overrides,
  };
}

describe("fromGeneration", () => {
  it("reopens the level a commission was asked at", () => {
    const form = fromGeneration(row({ think: "high" }));
    expect(form.think).toBe(true);
    expect(form.effort).toBe("high");
  });

  it("reopens an older row that kept only a bool at the default level", () => {
    const form = fromGeneration(row({ think: true }));
    expect(form.think).toBe(true);
    expect(form.effort).toBe(EMPTY_FORM.effort);
  });

  it("keeps reasoning off when it was asked off", () => {
    expect(fromGeneration(row({ think: false })).think).toBe(false);
  });

  it("reopens the concepts asked for, not the ones the bank chose", () => {
    const form = fromGeneration(row({ concepts: [], targets: ["Bucles"] }));
    expect(form.concepts).toEqual([]);
  });
});

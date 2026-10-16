import { describe, expect, it } from "vitest";

import { EMPTY_FORM, fromParams, toParams } from "./commission";

/* Which model writes it travels in the request. What is pinned is the ROUND TRIP plus the
   meaning of absence: null is "the default one" and must never become a name the browser
   guessed, because what a run RECORDS is what actually wrote it. */

describe("toParams", () => {
  it("carries the chosen model", () => {
    const params = toParams({ ...EMPTY_FORM, concepts: ["Función"], model: "qwen3.8:27b-q8_0" });
    expect(params.model).toBe("qwen3.8:27b-q8_0");
  });

  it("omits the key entirely when nobody chose, so the server resolves its own default", () => {
    const params = toParams({ ...EMPTY_FORM, concepts: ["Función"], model: null });
    expect("model" in params).toBe(false);
  });
});

describe("fromParams", () => {
  it("reads a recorded model back", () => {
    expect(fromParams({ model: "gemma-4-31b" }).model).toBe("gemma-4-31b");
  });

  it("reads a run that named none as the default, not as an empty name", () => {
    expect(fromParams({}).model).toBe(null);
    expect(fromParams({ model: "" }).model).toBe(null);
    expect(fromParams({ model: 7 }).model).toBe(null);
  });

  it("survives the round trip", () => {
    const state = { ...EMPTY_FORM, concepts: ["Función"], model: "gemma-4-31b" };
    expect(fromParams({ ...toParams(state) } as unknown as Record<string, unknown>).model).toBe(
      "gemma-4-31b",
    );
  });
});

/* The parts a commission leaves out travel as a list, and absence is "all of them": a run
   recorded before the question existed reads back as a commission that left nothing out. */
describe("the parts a commission leaves out", () => {
  it("travel only when there are any", () => {
    expect("omit" in toParams({ ...EMPTY_FORM, concepts: ["Función"] })).toBe(false);
    expect(toParams({ ...EMPTY_FORM, omit: ["solucion"] }).omit).toEqual(["solucion"]);
  });

  it("read back off a run, and as none off a run that named none", () => {
    expect(fromParams({ omit: ["solucion"] }).omit).toEqual(["solucion"]);
    expect(fromParams({}).omit).toEqual([]);
    expect(fromParams({ omit: "solucion" }).omit).toEqual([]);
  });
});

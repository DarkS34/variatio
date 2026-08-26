import { describe, expect, it } from "vitest";

import { EMPTY_FORM } from "@/features/run/commission";

import { toEvaluationParams, toStockParams } from "./commission";

/**
 * The two ways a comparison is commissioned, and the field that must never travel.
 *
 * `FormState.n` is «cuántos ítems produce este encargo», a question an evaluation never
 * asks: one item per arm is what makes the session the statistical unit, so the form hides
 * the counter in `variant="evaluation"` — and a hidden control keeps whatever it was left
 * at. The panel then read that hidden 2 as «cuántas comparaciones», so one commission
 * silently became two sessions and the same exercise appeared twice in the list.
 */
describe("what an evaluation commission carries", () => {
  it("never carries the form's item counter", () => {
    expect(toEvaluationParams({ ...EMPTY_FORM, n: 7 })).not.toHaveProperty("n");
  });

  it("never carries the reasoning switch, because the session draws it", () => {
    expect(toEvaluationParams({ ...EMPTY_FORM, think: false })).not.toHaveProperty("think");
  });

  it("still carries the commission itself", () => {
    const params = toEvaluationParams({ ...EMPTY_FORM, concepts: ["Recursividad"] });
    expect(params.concepts).toEqual(["Recursividad"]);
  });
});

describe("how many comparisons a stocked batch prepares", () => {
  it("is the number asked for and never the form's item counter", () => {
    expect(toStockParams({ ...EMPTY_FORM, n: 7 }, "default", 1).n).toBe(1);
  });

  it("is not the form's default either, which is what shipped broken", () => {
    expect(EMPTY_FORM.n).not.toBe(1);
    expect(toStockParams(EMPTY_FORM, "default", 1).n).toBe(1);
  });

  it("takes the workspace it was told to stock", () => {
    expect(toStockParams(EMPTY_FORM, "examenes-cs1", 3).workspace).toBe("examenes-cs1");
  });

  it("drops the reasoning switch like the evaluator's own commission does", () => {
    expect(toStockParams({ ...EMPTY_FORM, think: false }, "default", 1)).not.toHaveProperty(
      "think",
    );
  });
});

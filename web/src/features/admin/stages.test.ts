import { describe, expect, it } from "vitest";

import { USES } from "@/lib/steps";

import { CONFIG_STAGES, stageOfFeature } from "./stages";

describe("the configuration's stages and the functions' tabs", () => {
  it("draws each function's own stage in that function's tab", () => {
    // Swapped door keys pass every other gate: each tab would draw the other's settings.
    expect(stageOfFeature("evaluation").key).toBe("evaluation");
    expect(stageOfFeature("tutor").key).toBe("tutoring");
  });

  it("names each function's stage as the bar names its door", () => {
    for (const feature of ["evaluation", "tutor"] as const) {
      const door = USES.find((use) => use.feature === feature)!;
      expect(stageOfFeature(feature).labelKey).toBe(door.labelKey);
    }
  });

  it("leaves «Configuración» the product's own stages, in the path's order", () => {
    const product = CONFIG_STAGES.filter((stage) => stage.feature === null);
    // The types of exercise have no screen of their own: they are the bank's step's first part.
    expect(product.map((stage) => stage.key)).toEqual([
      "transcription",
      "graph",
      "bank",
      "generation",
    ]);
    expect(product.map((stage) => stage.number)).toEqual(["1", "2", "3", null]);
  });
});

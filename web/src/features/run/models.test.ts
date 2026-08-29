import { describe, expect, it } from "vitest";

import { clampEffort, EFFORT_ORDER, effortWarning, type EffortLevel } from "./effort";
import { familyOf, MODEL_FAMILIES, modelLabel } from "./models";

/* What the screen knows about a model it may offer. The claim worth pinning is the
   matching rule: a family is served under several names — `qwen3.8:27b-q8_0` here and
   `qwen3.8:27b-q4_K_M` on another installation are the same choice with the same
   trade-off — so the table is keyed by the START of the name, and a model it does not
   recognise is still offered, with its bare name and no note. */

describe("familyOf", () => {
  it("matches a family by the start of the name, whatever the tag", () => {
    expect(familyOf("qwen3.8:27b-q8_0").label).toBe("Qwen3.8");
    expect(familyOf("qwen3.8:27b-q4_K_M").label).toBe("Qwen3.8");
    expect(familyOf("gemma-4-31b").label).toBe("Gemma 4");
  });

  it("keeps an unrecognised model offerable, with its own name and nothing else", () => {
    const family = familyOf("un-modelo-de-otra-instalacion:9b");
    expect(family.label).toBe("un-modelo-de-otra-instalacion:9b");
    expect(family.url).toBeNull();
    expect(family.blurbKey).toBeNull();
    expect(family.speed).toBeNull();
    // It still gets the full effort scale: nothing is known about it, so nothing is denied.
    expect(family.levels).toEqual(EFFORT_ORDER);
  });

  it("answers for no model at all, which is the screen before health lands", () => {
    expect(modelLabel(undefined)).toBe("");
    expect(familyOf(undefined).levels.length).toBeGreaterThan(0);
  });
});

describe("the declared families", () => {
  it("only ever name levels the scale has, in its order", () => {
    for (const family of MODEL_FAMILIES) {
      expect(family.levels.length).toBeGreaterThan(0);
      expect(family.levels).toEqual(EFFORT_ORDER.filter((l) => family.levels.includes(l)));
    }
  });

  it("link to something a person can read about the model", () => {
    for (const family of MODEL_FAMILIES) {
      expect(family.url).toMatch(/^https:\/\//);
    }
  });
});

// Choosing the model BEFORE the effort is what makes this the normal path rather than an
// edge case: a level the newly chosen model does not accept has to come down to one it does.
describe("an effort a model does not accept", () => {
  it("comes down to the highest that model has", () => {
    const gemma = familyOf("gemma-4-31b");
    expect(gemma.levels).not.toContain("max" as EffortLevel);
    expect(clampEffort("max", gemma)).toBe("high");
    expect(clampEffort("low", gemma)).toBe("low");
  });

  it("is left alone when the model does accept it", () => {
    expect(clampEffort("max", familyOf("qwen3.8:27b-q8_0"))).toBe("max");
  });
});

describe("the warning above a model's comfortable level", () => {
  it("fires only above what that family declares", () => {
    const qwen = familyOf("qwen3.8:27b-q8_0");
    expect(effortWarning("medium", qwen)).toBeNull();
    expect(effortWarning("high", qwen)).toBe("effort.warn.qwen38");
  });

  it("never fires for a family that declares none", () => {
    for (const level of EFFORT_ORDER) {
      expect(effortWarning(level, familyOf("gemma-4-31b"))).toBeNull();
    }
  });
});

import { describe, expect, it } from "vitest";

import {
  clampEffort,
  EFFORT_ORDER,
  effortAdjustable,
  effortWarning,
  fixedEffort,
  type EffortLevel,
} from "./effort";
import { familyOf, MODEL_FAMILIES, modelLabel } from "./models";

/* What the screen knows about a model it may offer. The claim worth pinning is the
   matching rule: a family is served under several names — `qwen3.8:27b-q8_0` here and
   `qwen3.8:27b-q5_K_M` on another installation are the same choice with the same
   trade-off — so the table is keyed by the START of the name, and a model it does not
   recognise is still offered, with its bare name. */

describe("familyOf", () => {
  it("matches a family by the start of the name, whatever the tag", () => {
    expect(familyOf("qwen3.8:27b-q8_0").label).toBe("Qwen3.8 (local)");
    expect(familyOf("qwen3.8:27b-q5_K_M").label).toBe("Qwen3.8 (local)");
    expect(familyOf("gemma-4-31b").label).toBe("Gemma 4 (Cerebras)");
  });

  /* Each family is served on both engines under a different name, and the two prefixes
     have to stay apart under a rule that only looks at the start of the string: they
     differ by one hyphen, in opposite places. */
  it("tells a family's two halves apart by the engine that serves it", () => {
    expect(familyOf("qwen-3.8-27b").label).toBe("Qwen3.8 (Cerebras)");
    expect(familyOf("gemma4:31b-it-q4_K_M").label).toBe("Gemma 4 (local)");
  });

  /* The local half's warning quotes a measurement taken on Ollama, so it may not travel
     to the half Cerebras serves. */
  it("does not lend the local half's warning to the remote one", () => {
    expect(familyOf("qwen3.8:27b-q8_0").warningKey).toBe("effort.warn.qwen38");
    expect(familyOf("qwen-3.8-27b").warningKey).toBeUndefined();
  });

  it("keeps an unrecognised model offerable, with its own name and nothing else", () => {
    const family = familyOf("un-modelo-de-otra-instalacion:9b");
    expect(family.label).toBe("un-modelo-de-otra-instalacion:9b");
    expect(family.url).toBeNull();
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
    for (const model of ["gemma-4-31b", "qwen3.8:27b-q8_0"]) {
      const family = familyOf(model);
      expect(family.levels).not.toContain("max" as EffortLevel);
      expect(clampEffort("max", family)).toBe("high");
      expect(clampEffort("low", family)).toBe("low");
    }
  });

  it("is left alone by a model nothing is known about", () => {
    expect(clampEffort("max", familyOf("un-modelo-desconocido"))).toBe("max");
  });
});

// Neither declared family reaches `max`, and for two different measured reasons: Cerebras
// has no such level and lowers it to `high`, and on `qwen3.8` Ollama's renderer answers
// `max` with byte-identical output to `high`. The scale keeps the fourth step for a model
// that might implement it; a family may not offer a stop that changes nothing.
describe("the top of the scale", () => {
  it("is offered by no declared family", () => {
    for (const family of MODEL_FAMILIES) {
      expect(family.levels).not.toContain("max" as EffortLevel);
    }
  });

  it("still exists for a model nothing is known about", () => {
    expect(EFFORT_ORDER).toContain("max" as EffortLevel);
    expect(familyOf("un-modelo-desconocido").levels).toContain("max" as EffortLevel);
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

/* Whether the slider is drawn is the INSTALLATION's and not this table's. The rule is
   whole-name and not prefix, unlike `familyOf`: both lists hold engine names, so a prefix
   would lock a quantisation nobody measured. */
describe("effortAdjustable", () => {
  it("is true for a model nobody locked", () => {
    expect(effortAdjustable("qwen3.8:27b-q8_0", ["gemma-4-31b"])).toBe(true);
  });

  it("is false for a model the installation locked", () => {
    expect(effortAdjustable("gemma-4-31b", ["gemma-4-31b"])).toBe(false);
  });

  it("compares whole names, so another quantisation of a locked family stays adjustable", () => {
    expect(effortAdjustable("gemma-4-31b-q8_0", ["gemma-4-31b"])).toBe(true);
  });

  it("degrades to adjustable with no list at all", () => {
    expect(effortAdjustable("gemma-4-31b", [])).toBe(true);
    expect(effortAdjustable(undefined, ["gemma-4-31b"])).toBe(true);
  });
});

/* With WHICH LEVEL a locked model is called is the other half of it, and the
   installation's too (`generation.fixed_effort_levels`). Absent means the engine resolves
   it. */
describe("fixedEffort", () => {
  const gemma = familyOf("gemma-4-31b");

  it("returns the level the installation declared for that model", () => {
    expect(fixedEffort("gemma-4-31b", { "gemma-4-31b": "high" }, gemma)).toBe("high");
  });

  it("is null when nothing is declared for it", () => {
    expect(fixedEffort("gemma-4-31b", { otro: "high" }, gemma)).toBeNull();
    expect(fixedEffort("gemma-4-31b", {}, gemma)).toBeNull();
    expect(fixedEffort("gemma-4-31b", undefined, gemma)).toBeNull();
    expect(fixedEffort(undefined, { "gemma-4-31b": "high" }, gemma)).toBeNull();
  });

  it("clamps to a level the family actually implements", () => {
    // Cerebras has no `max` at all, so gemma's declared scale stops at `high`.
    expect(fixedEffort("gemma-4-31b", { "gemma-4-31b": "max" }, gemma)).toBe("high");
  });

  it("ignores a level outside the scale rather than passing it on", () => {
    expect(fixedEffort("gemma-4-31b", { "gemma-4-31b": "altísimo" }, gemma)).toBeNull();
  });
});

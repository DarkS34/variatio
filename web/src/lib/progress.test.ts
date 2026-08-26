import { describe, expect, it } from "vitest";

import { isRebuild, stepPercent } from "./progress";

describe("isRebuild", () => {
  it("is true only for the three jobs that write an artifact whole", () => {
    expect(["build_profile", "build_kg", "build_bank"].map(isRebuild)).toEqual([
      true,
      true,
      true,
    ]);
  });

  it("is false for the jobs that patch what is already there", () => {
    expect(["tag", "review_taggability", "describe_concepts", "index"].map(isRebuild)).toEqual([
      false,
      false,
      false,
      false,
    ]);
  });

  it("is false when no job is running", () => {
    expect(isRebuild(undefined)).toBe(false);
    expect(isRebuild(null)).toBe(false);
  });
});

describe("stepPercent", () => {
  it("measures the step it is given", () => {
    expect(stepPercent({ current: 0, total: 152 })).toBe(0);
    expect(stepPercent({ current: 38, total: 152 })).toBe(25);
    expect(stepPercent({ current: 152, total: 152 })).toBe(100);
  });

  it("is null while there is nothing to measure, which is not a zero", () => {
    expect(stepPercent(undefined)).toBeNull();
    expect(stepPercent(null)).toBeNull();
    expect(stepPercent({ current: 3 })).toBeNull();
    expect(stepPercent({ current: 3, total: null })).toBeNull();
    expect(stepPercent({ current: 3, total: 0 })).toBeNull();
  });

  it("never reports past the end", () => {
    expect(stepPercent({ current: 9, total: 8 })).toBe(100);
  });
});

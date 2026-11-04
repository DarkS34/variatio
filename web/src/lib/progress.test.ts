import { describe, expect, it } from "vitest";

import { roughDuration } from "./format";
import { barFill, isRebuild, stepPercent, timeLeft } from "./progress";

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

describe("barFill", () => {
  it("measures a meter whose total is known", () => {
    expect(barFill(0, 152)).toBe(0);
    expect(barFill(38, 152)).toBe(25);
    expect(barFill(152, 152)).toBe(100);
  });

  // The bug this exists for: deleting the last item of the exemplars bank leaves
  // `0/0`, which the meter drew as the indeterminate sweep — so the bank screen
  // animated for ever over a workspace where nothing was running at all.
  it("reads a KNOWN total of zero as an empty bar, never as the sweep", () => {
    expect(barFill(0, 0)).toBe(0);
    expect(barFill(3, 0)).toBe(0);
    expect(barFill(0, -1)).toBe(0);
  });

  it("is null only when the total is genuinely unknown", () => {
    expect(barFill(0, null)).toBeNull();
    expect(barFill(0, undefined)).toBeNull();
    expect(barFill(0, Number.NaN)).toBeNull();
  });

  it("never reports past either end", () => {
    expect(barFill(9, 8)).toBe(100);
    expect(barFill(-4, 8)).toBe(0);
  });
});

const running = (id: string, current: number, total: number | null) => ({
  id,
  status: "running",
  current,
  total,
});

describe("timeLeft", () => {
  const rates = { transcribe_pages: { seconds: 19 }, kg_extract: { seconds: 60 } };

  it("multiplies the units still to do by the step's measured seconds", () => {
    expect(timeLeft([running("kg_extract", 10, 30)], rates)).toBe(20 * 60);
  });

  it("takes the outermost running step: the slot's pages, not the document's", () => {
    const steps = [running("transcribe_pages", 100, 500), running("transcribe", 3, 40)];
    expect(timeLeft(steps, { ...rates, transcribe: { seconds: 999 } })).toBe(400 * 19);
  });

  it("shows nothing for a step this engine and these models were never timed on", () => {
    expect(timeLeft([running("kg_link", 1, 12)], rates)).toBeNull();
    expect(timeLeft([running("kg_extract", 1, 12)], undefined)).toBeNull();
    expect(timeLeft([running("kg_extract", 1, 12)], {})).toBeNull();
  });

  it("shows nothing while the total is unknown, and nothing for a finished step", () => {
    expect(timeLeft([running("kg_extract", 0, null)], rates)).toBeNull();
    expect(timeLeft([{ ...running("kg_extract", 30, 30), status: "ok" }], rates)).toBeNull();
  });
});

describe("roughDuration", () => {
  it("rounds up to whole minutes, never down to zero", () => {
    expect(roughDuration(5)).toBe("1 min");
    expect(roughDuration(61)).toBe("2 min");
  });

  it("counts hours past sixty minutes", () => {
    expect(roughDuration(3600)).toBe("1 h");
    expect(roughDuration(3600 + 7 * 60)).toBe("1 h 07 min");
  });
});

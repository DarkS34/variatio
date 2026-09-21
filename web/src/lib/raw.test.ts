import { describe, expect, it } from "vitest";

import { rawDriftLines, rawDriftOf } from "./raw";

const plural = (key: string, n: number, params?: Record<string, string | number>) =>
  `${key}:${n}:${params?.names ?? ""}`;

describe("rawDriftOf", () => {
  it("reads a cause about the documents and defaults its lists", () => {
    expect(rawDriftOf({ slot: "exemplars", label: "x", reason: "r", added: ["a.pdf"] })).toEqual({
      slot: "exemplars",
      added: ["a.pdf"],
      removed: [],
      changed: [],
    });
  });

  it("is nothing for a cause about an artifact above", () => {
    expect(rawDriftOf({ artifact: "exemplars_profile", label: "x", reason: "r" })).toBeNull();
  });
});

describe("rawDriftLines", () => {
  it("draws one line per non-empty list, added first", () => {
    const lines = rawDriftLines(
      { slot: "corpus", added: ["t2.pdf", "t3.pdf"], removed: [], changed: ["t1.pdf"] },
      plural,
    );
    expect(lines).toEqual(["stage.staleRaw.added:2:t2.pdf, t3.pdf", "stage.staleRaw.changed:1:t1.pdf"]);
  });

  it("draws nothing for a drift with nothing in it", () => {
    expect(rawDriftLines({ slot: "corpus", added: [], removed: [], changed: [] }, plural)).toEqual([]);
  });
});

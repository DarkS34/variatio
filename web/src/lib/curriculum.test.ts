import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { assumedKnown, notYetTaught } from "./curriculum";

interface Case {
  name: string;
  closure: string[];
  curriculum: string[] | null;
  assumed_known: string[];
  forbidden: string[];
}

const FIXTURE = fileURLToPath(
  new URL("../../../tests/fixtures/curriculum_sets.json", import.meta.url),
);
const CASES: Case[] = JSON.parse(readFileSync(FIXTURE, "utf-8"));

describe("curriculum set operations follow the shared table", () => {
  it("has cases", () => {
    expect(CASES.length).toBeGreaterThan(0);
  });

  for (const c of CASES) {
    it(`assumedKnown — ${c.name}`, () => {
      expect(assumedKnown(c.closure, c.curriculum)).toEqual(c.assumed_known);
    });

    it(`notYetTaught — ${c.name}`, () => {
      expect(notYetTaught(c.closure, c.curriculum)).toEqual(c.forbidden);
    });
  }
});

import { describe, expect, it } from "vitest";

import type { GraphView } from "@/lib/types";

import { adjacency, covered, frontier, priors } from "./prerequisites";

// Variable ← Función ← Recursividad ← Memoización: the chain from `tests/conftest.py`,
// the only shape where one hop and the closure differ. `[source, target]` reads "source
// has target as prerequisite".
const GRAPH = {
  nodes: [["Variable"], ["Función"], ["Recursividad"], ["Memoización"], ["Suelto"]],
  links: [
    [1, 0, "pre"],
    [2, 1, "pre"],
    [3, 2, "pre"],
  ],
  meta: { prerequisite: "pre" },
} as unknown as GraphView;

describe("covered — a coverage closed downwards", () => {
  it("adds everything the picks rest on, transitively, sorted", () => {
    expect(covered(adjacency(GRAPH), ["Recursividad"])).toEqual([
      "Función",
      "Recursividad",
      "Variable",
    ]);
  });

  it("is idempotent, so a stored row restores as it ran", () => {
    const once = covered(adjacency(GRAPH), ["Memoización", "Suelto"]);
    expect(covered(adjacency(GRAPH), once)).toEqual(once);
    expect(priors(adjacency(GRAPH)!, once)).toEqual([]);
  });

  it("hands the picks back untouched with no graph or no picks", () => {
    expect(covered(null, ["Recursividad"])).toEqual(["Recursividad"]);
    expect(covered(adjacency(GRAPH), [])).toEqual([]);
  });
});

describe("frontier — the picks a stored coverage comes from", () => {
  it("keeps what nothing else in the coverage rests on, and closing it gives the coverage back", () => {
    const stored = covered(adjacency(GRAPH), ["Recursividad", "Suelto"]);
    const picks = frontier(adjacency(GRAPH), stored);
    expect(picks).toEqual(["Recursividad", "Suelto"]);
    expect(covered(adjacency(GRAPH), picks)).toEqual(stored);
  });

  it("hands the coverage back untouched with no graph", () => {
    expect(frontier(null, ["Función", "Variable"])).toEqual(["Función", "Variable"]);
  });
});

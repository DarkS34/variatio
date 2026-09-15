import { describe, expect, it } from "vitest";

import type { GraphView } from "@/lib/types";

import { computeMapLayout, layoutKey, seedsFrom } from "./mapLayout";
import { planRegions } from "./regions";

/** A subject in `units` units of `size` concepts, each concept tied to a few of its own unit. */
function subject(units: number[], across = 0.1, loose = 0): GraphView {
  const groups = units.map((count, index) => ({ name: `Unidad ${index + 1}`, count }));
  const nodes: GraphView["nodes"] = [];
  const firsts: number[] = [];
  units.forEach((count, group) => {
    firsts.push(nodes.length);
    for (let index = 0; index < count; index += 1) nodes.push([`c${group}-${index}`, group, 0]);
  });
  const links: GraphView["links"] = [];
  let state = 7;
  const random = () => ((state = (state * 48271) % 2147483647) / 2147483647);
  units.forEach((count, group) => {
    for (let index = loose; index < count; index += 1) {
      const node = firsts[group] + index;
      let partner = firsts[group] + loose + Math.floor(random() * Math.max(1, count - loose));
      if (partner === node) partner = firsts[group] + loose + ((index - loose + 1) % (count - loose));
      links.push([node, partner, 1]);
      if (random() < across && units.length > 1) {
        const other = (group + 1) % units.length;
        links.push([node, firsts[other] + loose + Math.floor(random() * (units[other] - loose)), 2]);
      }
    }
  });
  return {
    meta: { title: "t", kind: "curated", generated: "", isolated: 0, prerequisite: null },
    relations: [],
    groups,
    nodes,
    links,
  };
}

describe("planRegions", () => {
  const counts = [146, 303, 24, 556, 253, 178, 360, 177, 354, 145];
  const plan = planRegions(counts);

  it("gives every unit that has concepts one region, in the syllabus's order", () => {
    expect(plan.regions.map((region) => region.group)).toEqual(counts.map((_, index) => index));
  });

  it("keeps every region inside the map and apart from every other", () => {
    for (const region of plan.regions) {
      expect(region.x).toBeGreaterThanOrEqual(-plan.width / 2);
      expect(region.y).toBeGreaterThanOrEqual(-plan.height / 2);
      expect(region.x + region.width).toBeLessThanOrEqual(plan.width / 2 + 1e-6);
      expect(region.y + region.height).toBeLessThanOrEqual(plan.height / 2 + 1e-6);
    }
    for (const a of plan.regions) {
      for (const b of plan.regions) {
        if (a === b) continue;
        const apart =
          a.x + a.width + plan.gutter / 2 <= b.x + 1e-6 ||
          b.x + b.width + plan.gutter / 2 <= a.x + 1e-6 ||
          a.y + a.height + plan.gutter / 2 <= b.y + 1e-6 ||
          b.y + b.height + plan.gutter / 2 <= a.y + 1e-6;
        expect(apart).toBe(true);
      }
    }
  });

  it("sizes a region by the concepts it holds", () => {
    const biggest = plan.regions.find((region) => region.count === 556)!;
    const middle = plan.regions.find((region) => region.count === 253)!;
    const area = (region: typeof biggest) =>
      (region.width + plan.gutter) * (region.height + plan.gutter);
    expect(area(biggest) / area(middle)).toBeCloseTo(556 / 253, 0);
  });

  it("never draws a unit as a sliver, however small it is beside the rest", () => {
    for (const region of plan.regions) {
      const skew = Math.max(region.width / region.height, region.height / region.width);
      expect(skew).toBeLessThan(3.5);
    }
  });

  it("skips an empty unit and answers an empty graph with nothing", () => {
    expect(planRegions([4, 0, 9]).regions.map((region) => region.group)).toEqual([0, 2]);
    expect(planRegions([]).regions).toEqual([]);
  });
});

describe("layoutKey", () => {
  const graph = subject([30, 40]);

  it("does not change with what moves no concept: names and taggability", () => {
    const renamed: GraphView = {
      ...graph,
      nodes: graph.nodes.map(([name, group], index) => [`${name}!`, group, index % 2]),
    };
    expect(layoutKey(renamed)).toBe(layoutKey(graph));
  });

  it("changes with a relation and with a concept moving unit", () => {
    expect(layoutKey({ ...graph, links: graph.links.slice(1) })).not.toBe(layoutKey(graph));
    const moved: GraphView = {
      ...graph,
      nodes: graph.nodes.map((node, index) => (index === 0 ? [node[0], 1, node[2]] : node)),
    };
    expect(layoutKey(moved)).not.toBe(layoutKey(graph));
  });
});

describe("computeMapLayout", () => {
  const graph = subject([60, 150, 20], 0.1, 3);
  const layout = computeMapLayout(graph);

  it("places every concept inside its own unit's region", () => {
    graph.nodes.forEach(([, group], index) => {
      const region = layout.regions.find((entry) => entry.group === group)!;
      const x = layout.positions[index * 2];
      const y = layout.positions[index * 2 + 1];
      expect(Number.isFinite(x) && Number.isFinite(y)).toBe(true);
      expect(x).toBeGreaterThanOrEqual(region.x);
      expect(x).toBeLessThanOrEqual(region.x + region.width);
      expect(y).toBeGreaterThanOrEqual(region.y);
      expect(y).toBeLessThanOrEqual(region.y + region.height);
    });
  });

  it("draws the same map for the same structure, on every device", () => {
    expect(Array.from(computeMapLayout(graph).positions)).toEqual(Array.from(layout.positions));
  });

  it("parks the concepts no relation mentions in a lane at the foot of their region", () => {
    expect(layout.lanes.map((lane) => [lane.group, lane.count])).toEqual([
      [0, 3],
      [1, 3],
      [2, 3],
    ]);
    const lane = layout.lanes[0];
    for (let index = 0; index < 3; index += 1) {
      expect(layout.positions[index * 2 + 1]).toBeGreaterThan(lane.top);
    }
  });

  // A relation inside the third unit, so the edit touches that unit and no other.
  let inner = graph.links.length - 1;
  while (graph.nodes[graph.links[inner][0]][1] !== 2 || graph.nodes[graph.links[inner][1]][1] !== 2) {
    inner -= 1;
  }
  const edited: GraphView = { ...graph, links: graph.links.filter((_, index) => index !== inner) };

  it("leaves every concept of a unit the edit did not touch exactly where it was", () => {
    const seeds = seedsFrom(edited, { graph, layout });
    expect(Array.from(seeds.keep)).toEqual([1, 1, 0]);
    const next = computeMapLayout(edited, seeds);
    graph.nodes.forEach(([, group], index) => {
      if (group === 2) return;
      expect(next.positions[index * 2]).toBeCloseTo(layout.positions[index * 2], 2);
      expect(next.positions[index * 2 + 1]).toBeCloseTo(layout.positions[index * 2 + 1], 2);
    });
  });

  it("moves the concepts of the unit it touched only a little", () => {
    const next = computeMapLayout(edited, seedsFrom(edited, { graph, layout }));
    let moved = 0;
    let counted = 0;
    graph.nodes.forEach(([, group], index) => {
      if (group !== 2) return;
      moved += Math.hypot(
        next.positions[index * 2] - layout.positions[index * 2],
        next.positions[index * 2 + 1] - layout.positions[index * 2 + 1],
      );
      counted += 1;
    });
    // Forty world units is one concept's cell: on average nothing moved as much.
    expect(moved / counted).toBeLessThan(40);
  });

  it("draws a different map of the same structure when asked to recolocar", () => {
    const again = computeMapLayout(graph, null, "otra");
    expect(Array.from(again.positions)).not.toEqual(Array.from(layout.positions));
  });
});

import type { GraphView } from "@/lib/types";

import { planRegions, type Region } from "./regions";
import { relax } from "./relax";

/**
 * THE WHOLE MAP: EVERY UNIT A REGION, EVERY CONCEPT RELAXED INSIDE ITS OWN.
 *
 * Pure and deterministic — the same graph gives the same map on every device, because the
 * spiral that seeds it and the jitter that breaks ties both come from a generator seeded by the
 * graph's own fingerprint — which is what lets `layoutClient.ts` compute it once, off the main
 * thread, and keep it.
 *
 * What the layout depends on is the STRUCTURE and nothing else: which unit each concept is in
 * and which relations join them. A concept's name, whether it serves as a label, its
 * description — none of it moves a dot, so none of it is in the fingerprint, and flipping a
 * taggability switch reuses the map instead of computing a new one.
 */

export interface Lane {
  group: number;
  /** World y of the rule above the parked concepts. */
  top: number;
  count: number;
}

export interface MapLayout {
  key: string;
  /** World position of every concept, `[x0, y0, x1, y1, …]` in node order. */
  positions: Float32Array;
  regions: Region[];
  width: number;
  height: number;
  /** Where each unit parks the concepts no relation mentions. */
  lanes: Lane[];
}

/** Where a new layout starts from, taken from the map the reader was looking at. */
export interface Seeds {
  /** Per concept, `u`, `v` in 0–1 inside its unit's field in the previous map, or `NaN`. */
  positions: Float32Array;
  /** Per unit of the new graph, 1 when nothing about it changed: its concepts stay put. */
  keep: Uint8Array;
}

/** Bumped whenever the algorithm changes what it draws, so no stored map outlives it. */
export const LAYOUT_VERSION = 1;

// A parked concept's cell, and the room above the first row for the rule and its caption.
const LANE_GAP = 28;
const LANE_HEAD = 26;
const LANE_MARGIN = 18;
// The lane never takes more than this share of its region, or a unit made mostly of loose
// concepts would leave its connected ones no room to be laid out in.
const LANE_SHARE = 0.45;

/** The structure's fingerprint: FNV-1a over the units, the concepts' units and the relations. */
export function layoutKey(graph: GraphView): string {
  let hash = 0x811c9dc5;
  const mix = (value: number) => {
    hash ^= value & 0xffff;
    hash = Math.imul(hash, 0x01000193);
    hash ^= (value >>> 16) & 0xffff;
    hash = Math.imul(hash, 0x01000193);
  };
  mix(LAYOUT_VERSION);
  mix(graph.groups.length);
  mix(graph.nodes.length);
  for (const node of graph.nodes) mix(node[1]);
  mix(graph.links.length);
  for (const [source, target, relation] of graph.links) {
    mix(source);
    mix(target);
    mix(relation);
  }
  return `${LAYOUT_VERSION}-${graph.nodes.length}-${(hash >>> 0).toString(36)}`;
}

/** The regions alone, which is all the map needs to draw before its concepts are placed. */
export function regionsOf(graph: GraphView) {
  const counts = new Array<number>(graph.groups.length).fill(0);
  for (const node of graph.nodes) counts[node[1]] = (counts[node[1]] ?? 0) + 1;
  return planRegions(counts);
}

/**
 * Lay the map out.
 *
 * With `seeds`, every concept starts where it sat in the map the reader was looking at, and a
 * unit whose concepts and relations did not change is not relaxed again at all: an edit moves
 * what it touched and leaves the rest of the picture where the reader left it. `salt` is the
 * "recolocar" button, the one thing that asks for a DIFFERENT map of the same structure.
 */
export function computeMapLayout(
  graph: GraphView,
  seeds?: Seeds | null,
  salt = "",
): MapLayout {
  const key = layoutKey(graph);
  const random = generator(key + salt);
  const plan = regionsOf(graph);
  const count = graph.nodes.length;
  const positions = new Float32Array(count * 2);

  const degree = new Uint32Array(count);
  for (const [source, target] of graph.links) {
    degree[source] += 1;
    degree[target] += 1;
  }

  const regionOf = new Map<number, Region>();
  for (const region of plan.regions) regionOf.set(region.group, region);

  const members = new Map<number, number[]>();
  for (let index = 0; index < count; index += 1) {
    const group = graph.nodes[index][1];
    const list = members.get(group);
    if (list) list.push(index);
    else members.set(group, [index]);
  }

  const lanes: Lane[] = [];
  const localIndex = new Int32Array(count).fill(-1);
  // The rectangle each region's connected concepts are relaxed in, once its lane is taken off.
  const field = new Map<number, { cx: number; cy: number; width: number; height: number }>();

  for (const region of plan.regions) {
    const nodes = members.get(region.group) ?? [];
    const loose = nodes.filter((index) => degree[index] === 0);
    const tied = nodes.filter((index) => degree[index] > 0);
    let band = 0;
    if (loose.length > 0) {
      const usable = Math.max(1, region.width - LANE_MARGIN * 2);
      const all = tied.length === 0;
      const room = all ? region.height : region.height * LANE_SHARE;
      // The head never takes more than two fifths of the band, or a short region would put
      // its parked concepts below its own bottom edge.
      const head = Math.min(LANE_HEAD, room * 0.4);
      let columns = Math.max(1, Math.floor(usable / LANE_GAP));
      let rows = Math.ceil(loose.length / columns);
      let step = LANE_GAP;
      if (rows * step + head > room) {
        // More than the band holds at the usual spacing: as many columns as keep the cells
        // square in the room there is, and the rows closed up to fit it exactly.
        const height = Math.max(1, room - head);
        columns = Math.max(1, Math.ceil(Math.sqrt((loose.length * usable) / height)));
        rows = Math.ceil(loose.length / columns);
        step = height / rows;
      }
      band = all ? region.height : Math.min(room, rows * step + head);
      const top = region.y + region.height - band;
      lanes.push({ group: region.group, top, count: loose.length });
      loose.forEach((index, rank) => {
        const column = rank % columns;
        const row = Math.floor(rank / columns);
        positions[index * 2] = region.x + LANE_MARGIN + (column + 0.5) * (usable / columns);
        positions[index * 2 + 1] = top + head + (row + 0.5) * step;
      });
    }
    tied.forEach((index, local) => (localIndex[index] = local));
    field.set(region.group, {
      cx: region.x + region.width / 2,
      cy: region.y + (region.height - band) / 2,
      width: region.width,
      height: region.height - band,
    });
  }

  // Relations inside a unit tie two of its concepts; a relation across units pulls each end
  // toward the edge of its own region that faces the other one.
  const inside = new Map<number, number[]>();
  const across = new Map<number, number[]>();
  const facing = (from: number, to: number) => {
    const a = field.get(from)!;
    const b = regionOf.get(to)!;
    const dx = b.x + b.width / 2 - a.cx;
    const dy = b.y + b.height / 2 - a.cy;
    const reach = Math.min(
      Math.abs(dx) > 1e-6 ? a.width / 2 / Math.abs(dx) : Infinity,
      Math.abs(dy) > 1e-6 ? a.height / 2 / Math.abs(dy) : Infinity,
    );
    return Number.isFinite(reach) ? [dx * reach * 0.85, dy * reach * 0.85] : [0, 0];
  };
  for (const [source, target] of graph.links) {
    const gs = graph.nodes[source][1];
    const gt = graph.nodes[target][1];
    if (gs === gt) {
      const list = inside.get(gs) ?? [];
      list.push(localIndex[source], localIndex[target]);
      inside.set(gs, list);
      continue;
    }
    for (const [node, from, to] of [
      [source, gs, gt],
      [target, gt, gs],
    ]) {
      const [x, y] = facing(from, to);
      const list = across.get(from) ?? [];
      list.push(localIndex[node], x, y);
      across.set(from, list);
    }
  }

  for (const region of plan.regions) {
    const tied = (members.get(region.group) ?? []).filter((index) => degree[index] > 0);
    if (tied.length === 0) continue;
    const box = field.get(region.group)!;

    let seed: Float64Array | null = null;
    let complete = false;
    if (seeds) {
      seed = new Float64Array(tied.length * 2).fill(Number.NaN);
      let found = 0;
      tied.forEach((index, local) => {
        const u = seeds.positions[index * 2];
        const v = seeds.positions[index * 2 + 1];
        if (Number.isFinite(u) && Number.isFinite(v)) {
          seed![local * 2] = (u - 0.5) * box.width;
          seed![local * 2 + 1] = (v - 0.5) * box.height;
          found += 1;
        }
      });
      complete = found === tied.length;
    }

    let local: Float64Array;
    if (seed && complete && seeds!.keep[region.group]) {
      local = seed;
    } else {
      const order = Uint32Array.from(
        tied.map((_, i) => i).sort((a, b) => degree[tied[b]] - degree[tied[a]] || a - b),
      );
      local = relax(
        {
          width: box.width,
          height: box.height,
          count: tied.length,
          edges: Uint32Array.from(inside.get(region.group) ?? []),
          anchors: Float64Array.from(across.get(region.group) ?? []),
          seed,
          order,
        },
        random,
      );
    }
    tied.forEach((index, i) => {
      positions[index * 2] = box.cx + local[i * 2];
      positions[index * 2 + 1] = box.cy + local[i * 2 + 1];
    });
  }

  return { key, positions, regions: plan.regions, width: plan.width, height: plan.height, lanes };
}

/**
 * Where each concept of `graph` sat in a previous map, and which units did not change at all.
 *
 * Matched by NAME and by unit: a concept that moved to another unit has no place to start from
 * in its new one, and a rename is a new concept as far as the picture is concerned. A position
 * is a fraction of the unit's field — its region minus its lane — so a unit that grew or shrank
 * because another one changed keeps its shape, only scaled.
 */
export function seedsFrom(
  graph: GraphView,
  previous: { graph: GraphView; layout: MapLayout },
): Seeds {
  const positions = new Float32Array(graph.nodes.length * 2).fill(Number.NaN);
  const fields = new Map<string, { x: number; y: number; width: number; height: number }>();
  for (const region of previous.layout.regions) {
    const name = previous.graph.groups[region.group]?.name;
    if (name === undefined) continue;
    const lane = previous.layout.lanes.find((entry) => entry.group === region.group);
    fields.set(name, {
      x: region.x,
      y: region.y,
      width: region.width,
      height: lane ? Math.max(1, lane.top - region.y) : region.height,
    });
  }
  const before = new Map<string, number>();
  previous.graph.nodes.forEach(([name], index) => before.set(name, index));
  graph.nodes.forEach(([name, group], index) => {
    const old = before.get(name);
    if (old === undefined) return;
    const unit = graph.groups[group]?.name;
    if (unit === undefined || previous.graph.groups[previous.graph.nodes[old][1]]?.name !== unit)
      return;
    const box = fields.get(unit);
    if (!box) return;
    positions[index * 2] = (previous.layout.positions[old * 2] - box.x) / box.width;
    positions[index * 2 + 1] = (previous.layout.positions[old * 2 + 1] - box.y) / box.height;
  });

  const now = signatures(graph);
  const then = signatures(previous.graph);
  const keep = new Uint8Array(graph.groups.length);
  graph.groups.forEach((group, index) => {
    const signature = now.get(group.name);
    keep[index] = signature !== undefined && signature === then.get(group.name) ? 1 : 0;
  });
  return { positions, keep };
}

/**
 * One order-free fingerprint per unit, by NAME: its concepts, the relations inside it and the
 * relations leaving it with the unit they reach. Two graphs agreeing on a unit's signature laid
 * that unit out from the same forces.
 */
function signatures(graph: GraphView): Map<string, string> {
  const sums = new Map<string, [number, number]>();
  const add = (unit: string, text: string) => {
    let hash = 0x811c9dc5;
    for (let index = 0; index < text.length; index += 1) {
      hash = Math.imul(hash ^ text.charCodeAt(index), 0x01000193);
    }
    const entry = sums.get(unit) ?? [0, 0];
    entry[0] = (entry[0] + (hash >>> 0)) % 4294967296;
    entry[1] = (entry[1] ^ Math.imul(hash, 2654435761)) >>> 0;
    sums.set(unit, entry);
  };
  const units = graph.groups.map((group) => group.name);
  graph.nodes.forEach(([name, group]) => add(units[group], `n${name}`));
  for (const [source, target, relation] of graph.links) {
    const [sourceName, sourceGroup] = graph.nodes[source];
    const [targetName, targetGroup] = graph.nodes[target];
    const kind = graph.relations[relation]?.key ?? String(relation);
    if (sourceGroup === targetGroup) {
      add(units[sourceGroup], `e${sourceName}${targetName}${kind}`);
    } else {
      add(units[sourceGroup], `o${sourceName}${units[targetGroup]}${kind}`);
      add(units[targetGroup], `o${targetName}${units[sourceGroup]}${kind}`);
    }
  }
  return new Map([...sums].map(([unit, [sum, xor]]) => [unit, `${sum}:${xor}`]));
}

/** mulberry32, seeded by the fingerprint: the same map on every device. */
function generator(key: string): () => number {
  let state = 0;
  for (let index = 0; index < key.length; index += 1) {
    state = Math.imul(state ^ key.charCodeAt(index), 2654435761);
  }
  return () => {
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

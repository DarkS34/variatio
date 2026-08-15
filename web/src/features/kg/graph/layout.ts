import type { GraphView } from "@/lib/types";
import type { GraphModel } from "./model";

export type LayoutMode = "force" | "curriculum";

export interface Body {
  x: number;
  y: number;
  dx: number;
  dy: number;
  /** Where the body is heading when a layout change is being animated into place. */
  tx: number;
  ty: number;
  pinned: boolean;
  /** Isolated concepts are placed, not simulated: they hold their lane position. */
  parked: boolean;
}

export interface Frame {
  width: number;
  height: number;
}

export const PADDING = 52;

// Fruchterman-Reingold constants, measured against this graph (118 concepts, 182
// edges) rather than guessed. Unbounded, the relaxation spread to ~5000 units and the
// camera had to zoom out to 0.2 to show it. Bounding it to the canvas and tuning these
// two makes the layout fill the frame with a single node touching the border:
// REPULSION sets the edge length (~78 px), GRAVITY keeps the periphery off the boundary.
const REPULSION = 0.45;
const GRAVITY = 0.5;

// Each node is also pulled toward the centre of its own domain. Without it, a graph this
// sparse (353 concepts, 485 edges, 2.7 per node) relaxes into one undifferentiated cloud:
// the domains are in the colours and nowhere in the picture, so the legend, the domain
// filter and the blobs behind them have nothing to point at.
//
// Measured on that graph, as the ratio between how far apart the domain centres end up
// and how wide a domain is — above 1 the domains read as separate regions — against the
// number of node pairs closer than 14px, which is what tightening costs in readability:
//
//   0     ratio 2.02   26 overlapping pairs      (the old behaviour)
//   0.09  ratio 2.32   20
//   0.3   ratio 2.95   26                        ← here
//   0.55  ratio 3.26   30
//
// Separation buys almost nothing in overlap up to ~0.5, so the ceiling is not crowding
// but meaning: past this the domains are drawn apart harder than their own edges pull
// them together, and the picture starts asserting a separation the graph does not have.
const CLUSTER = 0.3;

const LEVEL_GAP = 96;
const ROW_GAP = 46;
const COLUMN_GAP = 78;
const BARYCENTRE_SWEEPS = 6;

const PARK_GAP = 22;
const PARK_MARGIN = 58;

/** Width taken out of the canvas by the isolated lane, so the cloud is laid out in what
 *  is left instead of being drawn over it. Zero when nothing is isolated. */
export function parkReserve(model: GraphModel, frame: Frame): number {
  if (model.isolated.length === 0) return 0;
  return PARK_MARGIN + parkColumns(model, frame) * PARK_GAP;
}

function parkRows(frame: Frame): number {
  return Math.max(4, Math.floor((frame.height - PADDING * 2) / PARK_GAP));
}

function parkColumns(model: GraphModel, frame: Frame): number {
  return Math.max(1, Math.ceil(model.isolated.length / parkRows(frame)));
}

export function half(frame: Frame, reserve = 0) {
  return {
    width: Math.max(200, (frame.width - reserve) / 2 - PADDING),
    height: Math.max(150, frame.height / 2 - PADDING),
  };
}

/**
 * Where the isolated concepts go: a tidy grid down the right margin.
 *
 * They are a real finding about the graph — 28 concepts nothing links to — but left in
 * the simulation they are also the worst thing in the picture: with no edges to hold
 * them, repulsion alone pushes them out into a halo that surrounds the structure and
 * takes up most of the canvas, so the graph is drawn small in the middle of its own
 * outliers. Parked, they stay countable and legible and the cloud gets the frame.
 */
export function parkPositions(model: GraphModel, frame: Frame): Map<number, { x: number; y: number }> {
  const positions = new Map<number, { x: number; y: number }>();
  if (model.isolated.length === 0) return positions;

  const reserve = parkReserve(model, frame);
  const rows = parkRows(frame);
  const left = half(frame, reserve).width + PARK_MARGIN;

  model.isolated.forEach((node, index) => {
    const column = Math.floor(index / rows);
    const row = index % rows;
    const inColumn = Math.min(rows, model.isolated.length - column * rows);
    positions.set(node, {
      x: left + column * PARK_GAP,
      y: row * PARK_GAP - ((inColumn - 1) * PARK_GAP) / 2,
    });
  });
  return positions;
}

/** Seed by domain, so the relaxation starts from something already grouped and settles
 *  into readable clusters instead of a ring that untangles itself on camera. */
export function seedBodies(graph: GraphView, model: GraphModel, frame: Frame): Body[] {
  const groupCount = Math.max(1, graph.groups.length);
  const { width, height } = half(frame, parkReserve(model, frame));
  const parked = parkPositions(model, frame);
  const seen = new Map<number, number>();

  return graph.nodes.map(([, group], index) => {
    const lane = parked.get(index);
    if (lane) {
      return { x: lane.x, y: lane.y, dx: 0, dy: 0, tx: lane.x, ty: lane.y, pinned: false, parked: true };
    }
    const rank = seen.get(group) ?? 0;
    seen.set(group, rank + 1);
    const angle = (group / groupCount) * Math.PI * 2;
    const spread = 30 + Math.sqrt(rank + 1) * 18;
    const x = Math.cos(angle) * width * 0.55 + Math.cos(rank * 2.4) * spread;
    const y = Math.sin(angle) * height * 0.55 + Math.sin(rank * 2.4) * spread;
    return { x, y, dx: 0, dy: 0, tx: x, ty: y, pinned: false, parked: false };
  });
}

/** One Fruchterman-Reingold iteration, plus a pull toward each node's own domain. The
 *  frame minus the isolated lane is the world: bodies are clamped to it, which is what
 *  keeps the graph on screen instead of drifting off it. */
export function forceStep(
  bodies: Body[],
  links: [number, number, number][],
  model: GraphModel,
  frame: Frame,
  temperature: number,
  hidden?: Set<number>,
): number {
  const n = bodies.length;
  if (n === 0) return temperature;

  const { width, height } = half(frame, parkReserve(model, frame));
  const k = REPULSION * Math.sqrt((width * 2 * height * 2) / n);

  for (const body of bodies) {
    body.dx = 0;
    body.dy = 0;
  }

  for (let i = 0; i < n; i += 1) {
    const a = bodies[i];
    if (a.parked) continue;
    for (let j = i + 1; j < n; j += 1) {
      const b = bodies[j];
      if (b.parked) continue;
      let deltaX = a.x - b.x;
      let deltaY = a.y - b.y;
      let distance = Math.hypot(deltaX, deltaY);
      if (distance < 0.01) {
        deltaX = Math.random() - 0.5;
        deltaY = Math.random() - 0.5;
        distance = 0.01;
      }
      const force = (k * k) / distance;
      const ux = (deltaX / distance) * force;
      const uy = (deltaY / distance) * force;
      a.dx += ux;
      a.dy += uy;
      b.dx -= ux;
      b.dy -= uy;
    }
  }

  for (const [source, target, relation] of links) {
    if (hidden?.has(relation)) continue;
    const a = bodies[source];
    const b = bodies[target];
    if (!a || !b || a.parked || b.parked) continue;
    const deltaX = a.x - b.x;
    const deltaY = a.y - b.y;
    const distance = Math.max(0.01, Math.hypot(deltaX, deltaY));
    const force = (distance * distance) / k;
    const ux = (deltaX / distance) * force;
    const uy = (deltaY / distance) * force;
    a.dx -= ux;
    a.dy -= uy;
    b.dx += ux;
    b.dy += uy;
  }

  // Domain cohesion, recomputed each iteration rather than pinned to a fixed anchor: the
  // regions have to be free to move out of each other's way, and only their members
  // decide where each one is.
  const centres = domainCentres(bodies, model);
  for (let index = 0; index < n; index += 1) {
    const body = bodies[index];
    if (body.parked || body.pinned) continue;
    const centre = centres[model.groupOf[index]];
    if (!centre) continue;
    body.dx -= (body.x - centre.x) * CLUSTER * k * 0.08;
    body.dy -= (body.y - centre.y) * CLUSTER * k * 0.08;
  }

  // Gravity is elliptical, not round: pulling harder vertically than horizontally makes
  // the cloud take the shape of the canvas instead of a circle with two empty margins.
  const gravityY = GRAVITY * (width / height);
  for (const body of bodies) {
    if (body.pinned) continue;
    if (body.parked) {
      // Parked bodies are eased to their lane rather than snapped, so a relayout or a
      // resize slides them across instead of teleporting.
      body.x += (body.tx - body.x) * 0.2;
      body.y += (body.ty - body.y) * 0.2;
      continue;
    }
    body.dx -= body.x * GRAVITY;
    body.dy -= body.y * gravityY;
    const magnitude = Math.max(0.01, Math.hypot(body.dx, body.dy));
    const move = Math.min(magnitude, temperature);
    body.x = Math.max(-width, Math.min(width, body.x + (body.dx / magnitude) * move));
    body.y = Math.max(-height, Math.min(height, body.y + (body.dy / magnitude) * move));
  }
  return temperature;
}

/** Mean position of each domain's connected members. Allocates one small array per
 *  iteration, not per node, which is the budget this loop has. */
export function domainCentres(
  bodies: Body[],
  model: GraphModel,
): ({ x: number; y: number } | null)[] {
  const centres: ({ x: number; y: number } | null)[] = new Array(model.groupCount).fill(null);
  for (let group = 0; group < model.groupCount; group += 1) {
    let sumX = 0;
    let sumY = 0;
    let seen = 0;
    for (const node of model.domainMembers[group] ?? []) {
      const body = bodies[node];
      if (!body || body.parked) continue;
      sumX += body.x;
      sumY += body.y;
      seen += 1;
    }
    if (seen > 0) centres[group] = { x: sumX / seen, y: sumY / seen };
  }
  return centres;
}

/**
 * Layered layout over the prerequisite relation: one row per depth, top row first.
 *
 * This is the view the graph is actually *for* — a curriculum is an order, and reading
 * that order off a force cloud is guesswork. Rows come from the DAG; the order inside a
 * row is a barycentre sweep, the standard Sugiyama heuristic: put each node near the
 * average position of what it connects to, alternate the direction you sweep in, and
 * the long edges stop crossing each other. Ties break by domain, so a row still reads
 * as grouped when nothing else decides.
 *
 * A level is a BAND, not a line. Real KGs are lopsided — the graph this was built
 * against declares 8 prerequisites over 118 concepts, so level 0 holds almost
 * everything — and one row per level would draw that as a 9000px line nobody can read.
 * A wide level wraps into a grid instead: the reading "everything in this band comes
 * before everything in the next" survives, and the sparse case degrades into a
 * domain-sorted block rather than into a mess.
 */
export function curriculumPositions(
  graph: GraphView,
  model: GraphModel,
): { x: number; y: number }[] {
  const count = graph.nodes.length;
  const rows: number[][] = Array.from({ length: model.levelCount }, () => []);
  for (let index = 0; index < count; index += 1) rows[model.levels[index]].push(index);

  for (const row of rows) {
    row.sort((a, b) => {
      const [nameA, groupA] = graph.nodes[a];
      const [nameB, groupB] = graph.nodes[b];
      return groupA - groupB || nameA.localeCompare(nameB, "es");
    });
  }

  const up = new Map<number, number[]>();
  const down = new Map<number, number[]>();
  for (const [source, target, relation] of graph.links) {
    if (model.prerequisite !== null && relation !== model.prerequisite) continue;
    if (model.levels[source] === model.levels[target]) continue;
    if (!down.has(source)) down.set(source, []);
    if (!up.has(target)) up.set(target, []);
    down.get(source)!.push(target);
    up.get(target)!.push(source);
  }

  const order = new Array<number>(count).fill(0);
  const reindex = () => rows.forEach((row) => row.forEach((node, i) => (order[node] = i)));
  reindex();

  for (let sweep = 0; sweep < BARYCENTRE_SWEEPS; sweep += 1) {
    const downwards = sweep % 2 === 0;
    const sequence = downwards ? rows : [...rows].reverse();
    for (const row of sequence) {
      const neighbours = downwards ? down : up;
      const centre = new Map<number, number>();
      for (const node of row) {
        const linked = neighbours.get(node) ?? [];
        centre.set(
          node,
          linked.length === 0
            ? order[node]
            : linked.reduce((sum, other) => sum + order[other], 0) / linked.length,
        );
      }
      row.sort((a, b) => centre.get(a)! - centre.get(b)! || order[a] - order[b]);
    }
    reindex();
  }

  const widest = Math.max(1, ...rows.map((row) => row.length));
  const columns = Math.max(6, Math.min(22, Math.ceil(Math.sqrt(widest * 2.6))));

  const positions = new Array<{ x: number; y: number }>(count);
  let cursor = 0;
  for (const row of rows) {
    const lines = Math.max(1, Math.ceil(row.length / columns));
    row.forEach((node, index) => {
      const line = Math.floor(index / columns);
      const column = index % columns;
      // Every line is centred on the others rather than left-aligned, so a short line
      // sits under the middle of the one above instead of drifting to one side.
      const inLine = Math.min(columns, row.length - line * columns);
      positions[node] = {
        x: column * COLUMN_GAP - ((inLine - 1) * COLUMN_GAP) / 2,
        y: cursor + line * ROW_GAP,
      };
    });
    cursor += (lines - 1) * ROW_GAP + LEVEL_GAP;
  }

  const spanY = cursor - LEVEL_GAP;
  for (const position of positions) position.y -= spanY / 2;
  return positions;
}

/** Re-park the isolated bodies: called when the graph is seeded, when the canvas is
 *  resized, and when the force view is entered from the layered one, which left every
 *  body — parked ones included — on a curriculum target. */
export function applyParking(bodies: Body[], model: GraphModel, frame: Frame): void {
  const parked = parkPositions(model, frame);
  bodies.forEach((body, index) => {
    const lane = parked.get(index);
    body.parked = Boolean(lane);
    if (lane) {
      body.tx = lane.x;
      body.ty = lane.y;
    }
  });
}

/** Ease every body toward its target; returns true while anything is still moving. */
export function settleTowardTargets(bodies: Body[], rate = 0.18): boolean {
  let moving = false;
  for (const body of bodies) {
    const deltaX = body.tx - body.x;
    const deltaY = body.ty - body.y;
    if (Math.abs(deltaX) < 0.4 && Math.abs(deltaY) < 0.4) {
      body.x = body.tx;
      body.y = body.ty;
      continue;
    }
    body.x += deltaX * rate;
    body.y += deltaY * rate;
    moving = true;
  }
  return moving;
}

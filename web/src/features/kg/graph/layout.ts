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

const LEVEL_GAP = 96;
const ROW_GAP = 46;
const COLUMN_GAP = 78;
const BARYCENTRE_SWEEPS = 6;

export function half(frame: Frame) {
  return {
    width: Math.max(200, frame.width / 2 - PADDING),
    height: Math.max(150, frame.height / 2 - PADDING),
  };
}

/** Seed by domain, so the relaxation starts from something already grouped and settles
 *  into readable clusters instead of a ring that untangles itself on camera. */
export function seedBodies(graph: GraphView, frame: Frame): Body[] {
  const groupCount = Math.max(1, graph.groups.length);
  const { width, height } = half(frame);
  const seen = new Map<number, number>();

  return graph.nodes.map(([, group]) => {
    const rank = seen.get(group) ?? 0;
    seen.set(group, rank + 1);
    const angle = (group / groupCount) * Math.PI * 2;
    const spread = 30 + Math.sqrt(rank + 1) * 18;
    const x = Math.cos(angle) * width * 0.55 + Math.cos(rank * 2.4) * spread;
    const y = Math.sin(angle) * height * 0.55 + Math.sin(rank * 2.4) * spread;
    return { x, y, dx: 0, dy: 0, tx: x, ty: y, pinned: false };
  });
}

/** One Fruchterman-Reingold iteration. The frame is the world: bodies are clamped to
 *  it, which is what keeps the graph on screen instead of drifting off it. */
export function forceStep(
  bodies: Body[],
  links: [number, number, number][],
  frame: Frame,
  temperature: number,
  hidden?: Set<number>,
): number {
  const n = bodies.length;
  if (n === 0) return temperature;

  const { width, height } = half(frame);
  const k = REPULSION * Math.sqrt((width * 2 * height * 2) / n);

  for (const body of bodies) {
    body.dx = 0;
    body.dy = 0;
  }

  for (let i = 0; i < n; i += 1) {
    const a = bodies[i];
    for (let j = i + 1; j < n; j += 1) {
      const b = bodies[j];
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
    if (!a || !b) continue;
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

  // Gravity is elliptical, not round: pulling harder vertically than horizontally makes
  // the cloud take the shape of the canvas instead of a circle with two empty margins.
  const gravityY = GRAVITY * (width / height);
  for (const body of bodies) {
    if (body.pinned) continue;
    body.dx -= body.x * GRAVITY;
    body.dy -= body.y * gravityY;
    const magnitude = Math.max(0.01, Math.hypot(body.dx, body.dy));
    const move = Math.min(magnitude, temperature);
    body.x = Math.max(-width, Math.min(width, body.x + (body.dx / magnitude) * move));
    body.y = Math.max(-height, Math.min(height, body.y + (body.dy / magnitude) * move));
  }
  return temperature;
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

import type { GraphView } from "@/lib/types";
import type { GraphModel } from "./model";

export type LayoutMode = "force" | "curriculum";

/**
 * One concept on the canvas: where it is drawn, and where it is heading while a change of
 * layout — or a new map landing — is animated into place.
 *
 * The map's own positions are computed once per structure, off the main thread, by
 * `mapLayout.ts`; nothing here simulates anything. What is left is the ORDER view, which is
 * cheap enough to derive where it is drawn, and the easing between the two.
 */
export interface Body {
  x: number;
  y: number;
  tx: number;
  ty: number;
  pinned: boolean;
}

export interface Frame {
  width: number;
  height: number;
}

export const PADDING = 52;

const LEVEL_GAP = 96;
const ROW_GAP = 46;
const COLUMN_GAP = 78;
const BARYCENTRE_SWEEPS = 6;

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

  let widest = 1;
  for (const row of rows) widest = Math.max(widest, row.length);
  // The ceiling was 22, which a subject of thousands turns into a band a hundred rows deep and
  // twenty wide: measured on a 10 000-concept graph, a column eleven times taller than wide
  // that the frame could only fit as a sliver. Up to 120 the widest band keeps a shape.
  const columns = Math.max(6, Math.min(120, Math.ceil(Math.sqrt(widest * 2.6))));

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

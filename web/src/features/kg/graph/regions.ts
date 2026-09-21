/**
 * THE MAP'S UNITS, AS RECTANGLES IN THE ORDER THE SYLLABUS TEACHES THEM.
 *
 * A force layout of a whole subject is a hairball past a few hundred concepts: measured on the
 * nursing subject (2 496 concepts, 5 262 relations) the free layout was one grey mass whose
 * units could not be told apart, and its O(n²) relaxation kept the page frozen 47 s. What
 * separates a big syllabus into something a person can read is the syllabus itself: 85 % of
 * that subject's relations stay inside a unit. So every unit gets a region of its own, and the
 * concepts are laid out INSIDE it.
 *
 * Rectangles and not circles, because the material is the grid — `--radius: 0` — and because a
 * rectangle packs the rectangular canvas with no holes. In the syllabus's own order, row after
 * row, so the map reads in the order the outline beside it lists the units. Area follows the
 * concepts a unit holds, so the density is about the same everywhere and one zoom level means
 * the same thing in every unit.
 *
 * What keeps a unit from becoming a sliver — which an ordered strip layout produces as soon as a
 * small unit sits between two big ones: measured, the plain strip gave the nursing subject's
 * 24-concept unit a column two concepts wide and its last unit a band 27 times wider than
 * tall. The rows are cut by dynamic programming over what each row costs; inside a row no
 * rectangle is let past `MAX_SKEW`, the width it gives up going to its neighbours; a row that
 * cannot keep that promise — one small unit alone across the whole map — costs so much the
 * cut avoids it; and a unit is sized as if it held at least a sixtieth of the subject. What
 * that costs is density, and only in the units that needed the room.
 */

export interface Region {
  /** Index into `graph.groups`. */
  group: number;
  /** Top-left corner and size, in world units, gutters already taken out. */
  x: number;
  y: number;
  width: number;
  height: number;
  count: number;
}

export interface RegionPlan {
  regions: Region[];
  /** The whole map, centred on the origin. */
  width: number;
  height: number;
  /** The empty band between two regions, in world units. */
  gutter: number;
}

/** World side each concept is given: the typical distance between two concepts. */
export const CONCEPT_SIDE = 40;

const MAX_SKEW = 2.5;
const FLOOR_SHARE = 1 / 60;
// The map's width over its height is chosen among these, nearest 1.6 when the costs tie: wide
// enough for the expanded view, not so wide the card beside the outline letterboxes it.
const ASPECTS = [1.3, 1.45, 1.6, 1.8, 2];
const PREFERRED_ASPECT = 1.6;

interface Row {
  from: number;
  height: number;
  widths: number[];
}

export function planRegions(counts: number[]): RegionPlan {
  const items = counts
    .map((count, group) => ({ group, count }))
    .filter((item) => item.count > 0);
  if (items.length === 0) return { regions: [], width: 0, height: 0, gutter: 0 };

  const concepts = items.reduce((sum, item) => sum + item.count, 0);
  const cell = CONCEPT_SIDE * CONCEPT_SIDE;
  const areas = items.map((item) => Math.max(item.count, concepts * FLOOR_SHARE, 1) * cell);
  const total = areas.reduce((sum, area) => sum + area, 0);
  // The gutter follows the size of the map — a fiftieth of its side, between 16 and 48 — so a
  // subject of a hundred concepts is not mostly gutter and one of ten thousand is not all seams.
  const gutter = Math.min(48, Math.max(16, Math.sqrt(total) / 50));

  let best: { score: number; rows: Row[]; width: number } | null = null;
  for (const aspect of ASPECTS) {
    const width = Math.sqrt(total * aspect);
    const rows = cutRows(areas, width, total);
    const score =
      rows.cost + total * 0.3 * Math.abs(Math.log(aspect / PREFERRED_ASPECT));
    if (!best || score < best.score) best = { score, rows: rows.rows, width };
  }

  const { rows, width } = best!;
  const height = rows.reduce((sum, row) => sum + row.height, 0);
  const regions: Region[] = [];
  let top = -height / 2;
  for (const row of rows) {
    let left = -width / 2;
    row.widths.forEach((rowWidth, offset) => {
      const item = items[row.from + offset];
      regions.push({
        group: item.group,
        count: item.count,
        x: left + gutter / 2,
        y: top + gutter / 2,
        width: Math.max(CONCEPT_SIDE, rowWidth - gutter),
        height: Math.max(CONCEPT_SIDE, row.height - gutter),
      });
      left += rowWidth;
    });
    top += row.height;
  }
  return { regions, width, height, gutter };
}

/**
 * The cheapest way to cut the ordered areas into full-width rows.
 *
 * A row costs, per rectangle, how far it is from a square plus how far its area is from the one
 * it was due — both on a log scale, weighted by the area, with a floor so a small unit's shape
 * still counts for something — and steeply more for every step past `MAX_SKEW`.
 */
function cutRows(areas: number[], width: number, total: number) {
  const count = areas.length;
  const cost = new Array<number>(count + 1).fill(Infinity);
  const last = new Array<Row | null>(count + 1).fill(null);
  cost[0] = 0;
  const floor = total / 30;
  const limit = Math.log(MAX_SKEW);
  for (let to = 1; to <= count; to += 1) {
    for (let from = 0; from < to; from += 1) {
      const slice = areas.slice(from, to);
      const { height, widths } = fitRow(slice, width);
      let value = cost[from];
      widths.forEach((rowWidth, index) => {
        const skew = Math.abs(Math.log(rowWidth / height));
        const beyond = Math.max(0, skew - limit * 1.05);
        const distortion = Math.abs(Math.log((rowWidth * height) / slice[index]));
        value += Math.max(slice[index], floor) * (skew + distortion + 20 * beyond);
      });
      if (value < cost[to]) {
        cost[to] = value;
        last[to] = { from, height, widths };
      }
    }
  }
  const rows: Row[] = [];
  for (let to = count; to > 0; to = last[to]!.from) rows.unshift(last[to]!);
  return { cost: cost[count], rows };
}

/**
 * One row: full width, one height, no rectangle past `MAX_SKEW` of it when the row can help it.
 *
 * What a clamped rectangle gives up or takes is shared out among the unclamped ones in
 * proportion, a few passes, and the row is scaled to the width at the end. The height stays
 * the one that gives the row exactly its area, so rows always add up to the map; a row whose
 * rectangles cannot all be kept in shape — every one clamped — comes out skewed, and its cost
 * says so.
 */
function fitRow(areas: number[], width: number): { height: number; widths: number[] } {
  const height = areas.reduce((sum, area) => sum + area, 0) / width;
  const low = height / MAX_SKEW;
  const high = height * MAX_SKEW;
  let widths = areas.map((area) => area / height);
  for (let pass = 0; pass < 8; pass += 1) {
    const clamped = widths.map((value) => Math.min(Math.max(value, low), high));
    const pinned = clamped.map((value) => value <= low || value >= high);
    const used = clamped.reduce((sum, value) => sum + value, 0);
    const free = clamped.reduce((sum, value, index) => sum + (pinned[index] ? 0 : value), 0);
    const extra = width - used;
    widths = clamped;
    if (Math.abs(extra) < 1e-6 || free <= 0) break;
    widths = clamped.map((value, index) => (pinned[index] ? value : value * (1 + extra / free)));
  }
  const sum = widths.reduce((total, value) => total + value, 0);
  return { height, widths: widths.map((value) => (value * width) / sum) };
}

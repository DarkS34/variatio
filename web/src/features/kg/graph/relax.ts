/**
 * THE CONCEPTS OF ONE REGION, RELAXED BY FORCE — IN O(n log n).
 *
 * Fruchterman–Reingold, as the map has always used, bounded to the region instead of to the
 * canvas: repulsion k²/d between every pair, attraction d²/k along every relation, a gravity
 * that is elliptical so the cloud takes the region's shape, and a temperature that caps each
 * step and cools. What changed is the repulsion. Summed over every pair it cost 136 ms a step
 * on the nursing subject — 2 496 concepts, 200 steps, 27 s in Node and 47 s in the browser,
 * on the main thread, on every visit — so it is a Barnes–Hut quadtree now: a far cell pushes
 * as one body at its centre of mass.
 *
 * A relation that leaves the region still pulls, toward the point of the region's edge that
 * faces the other unit, so the concepts a unit shares with another sit on the side where the
 * line to it will be drawn.
 */

export interface RegionProblem {
  /** The rectangle the concepts must stay in, centred on the origin. */
  width: number;
  height: number;
  count: number;
  /** Relations inside the region, as pairs of local indices. */
  edges: Uint32Array;
  /** Relations leaving it: `[localIndex, x, y]` triples, the point on the edge to pull toward. */
  anchors: Float64Array;
  /** A previous position per concept, `NaN` where there is none. */
  seed: Float64Array | null;
  /** The local indices in the order the spiral seeds them — the most connected first. */
  order: Uint32Array;
}

// The constants below were chosen by drawing the nursing subject and a synthetic 10 000-concept
// one under five variants and looking. The canvas's own FR constants (gravity 0.5, attraction
// uncapped, clamped to the frame) packed each unit into a dense blob in the middle of its region
// and lined the concepts pulled toward other units up along its edges, a column of dots per
// border; stronger repulsion only made the columns longer.
const REPULSION = 0.6;
// Weak: what keeps the cloud off the edges is the walls, and this only centres it.
const GRAVITY = 0.15;
// Attraction is FR's d²/k up to three edge lengths and linear beyond: one relation to the far
// side of a unit must not drag a concept across it, which is what collapsed every unit whose
// relations are spread over its whole list into one knot.
const ATTRACTION_CAP = 3;
const ANCHOR_PULL = 0.1;
// Each edge of the region pushes a concept back with k²/(distance + k/4): soft enough to leave
// the band next to it usable, strong enough that nothing piles on the border.
const WALL = 1.5;
// The last move spreads each axis toward even ranks, half-way: density is what decides how many
// names fit when the map is read up close, and a force layout leaves its centre several times
// denser than its rim. Half-way keeps who is beside whom — ranks preserve order.
const RANK_BLEND = 0.5;
// Barnes–Hut's opening angle, squared: a cell pushes as one body once it is farther than
// its own side.
const THETA2 = 1;
// Below this many concepts the exact sum is cheaper than building a tree.
const EXACT_BELOW = 90;
const COOLING = 0.95;
const SETTLED = 0.4;
const MAX_STEPS = 180;
// A warm start — most of the concepts already placed by the previous layout — only has to
// make room for what changed, so it starts cool and stops early.
const WARM_SHARE = 0.6;
const WARM_HEAT = 0.1;
const WARM_STEPS = 60;
const MARGIN = 18;
const GOLDEN = Math.PI * (3 - Math.sqrt(5));

export function relax(problem: RegionProblem, random: () => number): Float64Array {
  const n = problem.count;
  const pos = new Float64Array(n * 2);
  if (n === 0) return pos;

  const hw = Math.max(2, problem.width / 2 - MARGIN);
  const hh = Math.max(2, problem.height / 2 - MARGIN);

  let seeded = 0;
  if (problem.seed) {
    for (let i = 0; i < n; i += 1) {
      const x = problem.seed[i * 2];
      const y = problem.seed[i * 2 + 1];
      if (Number.isFinite(x) && Number.isFinite(y)) {
        pos[i * 2] = clamp(x, hw);
        pos[i * 2 + 1] = clamp(y, hh);
        seeded += 1;
      } else {
        pos[i * 2] = Number.NaN;
      }
    }
  }
  // A sunflower spiral, the most connected concepts at the centre: nothing coincides, and the
  // hubs start where the relaxation would take them anyway.
  for (let rank = 0; rank < n; rank += 1) {
    const i = problem.order[rank];
    if (problem.seed && !Number.isNaN(pos[i * 2])) continue;
    const radius = Math.sqrt((rank + 0.5) / n) * 0.92;
    pos[i * 2] = Math.cos(rank * GOLDEN) * radius * hw + (random() - 0.5) * 0.01;
    pos[i * 2 + 1] = Math.sin(rank * GOLDEN) * radius * hh + (random() - 0.5) * 0.01;
  }
  if (n === 1) return pos;

  const warm = problem.seed !== null && seeded >= n * WARM_SHARE;
  const k = REPULSION * Math.sqrt((4 * hw * hh) / n);
  const k2 = k * k;
  const gravityY = GRAVITY * (hw / hh);
  let temperature = ((Math.max(hw, hh) * 2) / 10) * (warm ? WARM_HEAT : 1);
  const steps = warm ? WARM_STEPS : MAX_STEPS;

  const disp = new Float64Array(n * 2);
  const tree = n >= EXACT_BELOW ? new Tree(n) : null;
  const { edges, anchors } = problem;

  for (let step = 0; step < steps && temperature > SETTLED; step += 1) {
    disp.fill(0);

    if (tree) {
      tree.build(pos, n);
      for (let i = 0; i < n; i += 1) tree.repel(i, pos, k2, disp, random);
    } else {
      for (let i = 0; i < n; i += 1) {
        for (let j = i + 1; j < n; j += 1) {
          let dx = pos[i * 2] - pos[j * 2];
          let dy = pos[i * 2 + 1] - pos[j * 2 + 1];
          let d2 = dx * dx + dy * dy;
          if (d2 < 1e-4) {
            dx = (random() - 0.5) * 0.1;
            dy = (random() - 0.5) * 0.1;
            d2 = dx * dx + dy * dy;
          }
          const f = k2 / d2;
          disp[i * 2] += dx * f;
          disp[i * 2 + 1] += dy * f;
          disp[j * 2] -= dx * f;
          disp[j * 2 + 1] -= dy * f;
        }
      }
    }

    // `Math.sqrt` and never `Math.hypot`, which V8 runs several times slower, in the loops a
    // 10 000-concept map repeats hundreds of thousands of times.
    for (let e = 0; e < edges.length; e += 2) {
      const a = edges[e];
      const b = edges[e + 1];
      const dx = pos[a * 2] - pos[b * 2];
      const dy = pos[a * 2 + 1] - pos[b * 2 + 1];
      const f = Math.min(Math.max(0.01, Math.sqrt(dx * dx + dy * dy)) / k, ATTRACTION_CAP);
      disp[a * 2] -= dx * f;
      disp[a * 2 + 1] -= dy * f;
      disp[b * 2] += dx * f;
      disp[b * 2 + 1] += dy * f;
    }

    for (let t = 0; t < anchors.length; t += 3) {
      const i = anchors[t];
      const dx = pos[i * 2] - anchors[t + 1];
      const dy = pos[i * 2 + 1] - anchors[t + 2];
      const f =
        Math.min(Math.max(0.01, Math.sqrt(dx * dx + dy * dy)) / k, ATTRACTION_CAP) * ANCHOR_PULL;
      disp[i * 2] -= dx * f;
      disp[i * 2 + 1] -= dy * f;
    }

    const soft = k / 4;
    const wall = WALL * k2;
    for (let i = 0; i < n; i += 1) {
      const x = pos[i * 2];
      const y = pos[i * 2 + 1];
      const dx = disp[i * 2] - x * GRAVITY + wall * (1 / (x + hw + soft) - 1 / (hw - x + soft));
      const dy =
        disp[i * 2 + 1] - y * gravityY + wall * (1 / (y + hh + soft) - 1 / (hh - y + soft));
      const magnitude = Math.max(0.01, Math.sqrt(dx * dx + dy * dy));
      const move = Math.min(magnitude, temperature);
      pos[i * 2] = clamp(x + (dx / magnitude) * move, hw);
      pos[i * 2 + 1] = clamp(y + (dy / magnitude) * move, hh);
    }
    temperature *= COOLING;
  }
  // A warm start too: its seeds were spread, and relaxing them without spreading again would
  // gather the unit back toward its centre every time an edit touched it.
  spreadByRank(pos, n, hw, hh);
  return pos;
}

/** Move each axis half-way toward evenly spaced ranks, which evens out the density. */
function spreadByRank(pos: Float64Array, n: number, hw: number, hh: number) {
  const order = new Uint32Array(n);
  for (const [axis, half] of [
    [0, hw],
    [1, hh],
  ] as const) {
    for (let i = 0; i < n; i += 1) order[i] = i;
    order.sort((a, b) => pos[a * 2 + axis] - pos[b * 2 + axis] || a - b);
    for (let rank = 0; rank < n; rank += 1) {
      const node = order[rank];
      const even = -half + ((rank + 0.5) / n) * 2 * half;
      pos[node * 2 + axis] += (even - pos[node * 2 + axis]) * RANK_BLEND;
    }
  }
}

function clamp(value: number, limit: number) {
  return value < -limit ? -limit : value > limit ? limit : value;
}

/**
 * A quadtree in flat typed arrays, rebuilt every step without allocating: a cell is an index,
 * its four children sit at `child[4 * cell + q]`, and a leaf holds one body — or, past the
 * depth where two bodies can only be coincident, the mass of all of them.
 */
class Tree {
  private capacity = 0;
  private used = 0;
  private x0 = new Float64Array(0);
  private y0 = new Float64Array(0);
  private size = new Float64Array(0);
  private mass = new Float64Array(0);
  private mx = new Float64Array(0);
  private my = new Float64Array(0);
  private child = new Int32Array(0);
  private body = new Int32Array(0);
  private stack = new Int32Array(256);

  constructor(n: number) {
    this.grow(Math.max(64, n * 4));
  }

  private grow(capacity: number) {
    const floats = (from: Float64Array) => {
      const to = new Float64Array(capacity);
      to.set(from.subarray(0, Math.min(from.length, capacity)));
      return to;
    };
    const ints = (from: Int32Array, size: number) => {
      const to = new Int32Array(size);
      to.set(from.subarray(0, Math.min(from.length, size)));
      return to;
    };
    this.x0 = floats(this.x0);
    this.y0 = floats(this.y0);
    this.size = floats(this.size);
    this.mass = floats(this.mass);
    this.mx = floats(this.mx);
    this.my = floats(this.my);
    this.child = ints(this.child, capacity * 4);
    this.body = ints(this.body, capacity);
    this.capacity = capacity;
  }

  private cell(x0: number, y0: number, size: number) {
    if (this.used === this.capacity) this.grow(this.capacity * 2);
    const index = this.used;
    this.used += 1;
    this.x0[index] = x0;
    this.y0[index] = y0;
    this.size[index] = size;
    this.mass[index] = 0;
    this.mx[index] = 0;
    this.my[index] = 0;
    this.body[index] = -1;
    this.child.fill(-1, index * 4, index * 4 + 4);
    return index;
  }

  build(pos: Float64Array, n: number) {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (let i = 0; i < n; i += 1) {
      const x = pos[i * 2];
      const y = pos[i * 2 + 1];
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
    const size = Math.max(maxX - minX, maxY - minY) * 1.0001 + 1e-3;
    this.used = 0;
    this.cell(minX, minY, size);
    for (let i = 0; i < n; i += 1) this.insert(i, pos[i * 2], pos[i * 2 + 1]);
  }

  private insert(i: number, x: number, y: number) {
    let node = 0;
    for (let depth = 0; ; depth += 1) {
      if (this.child[node * 4] === -1) {
        if (this.mass[node] === 0) {
          this.body[node] = i;
          this.mass[node] = 1;
          this.mx[node] = x;
          this.my[node] = y;
          return;
        }
        if (depth > 40) {
          this.mass[node] += 1;
          this.mx[node] += x;
          this.my[node] += y;
          return;
        }
        const half = this.size[node] / 2;
        const x0 = this.x0[node];
        const y0 = this.y0[node];
        for (let q = 0; q < 4; q += 1) {
          // Into a local FIRST: `cell` may grow — replace — the arrays, and an assignment
          // evaluates its left side before the call, so the index would land in the old one.
          const created = this.cell(x0 + (q & 1) * half, y0 + ((q >> 1) & 1) * half, half);
          this.child[node * 4 + q] = created;
        }
        const held = this.body[node];
        const hx = this.mx[node];
        const hy = this.my[node];
        const moved = this.child[node * 4 + this.quadrant(node, hx, hy)];
        this.body[moved] = held;
        this.mass[moved] = 1;
        this.mx[moved] = hx;
        this.my[moved] = hy;
        this.body[node] = -1;
      }
      this.mass[node] += 1;
      this.mx[node] += x;
      this.my[node] += y;
      node = this.child[node * 4 + this.quadrant(node, x, y)];
    }
  }

  private quadrant(node: number, x: number, y: number) {
    const half = this.size[node] / 2;
    return (x >= this.x0[node] + half ? 1 : 0) | (y >= this.y0[node] + half ? 2 : 0);
  }

  repel(i: number, pos: Float64Array, k2: number, disp: Float64Array, random: () => number) {
    const x = pos[i * 2];
    const y = pos[i * 2 + 1];
    let fx = 0;
    let fy = 0;
    let top = 0;
    this.stack[top++] = 0;
    while (top > 0) {
      const node = this.stack[--top];
      let m = this.mass[node];
      if (m === 0) continue;
      let dx = x - this.mx[node] / m;
      let dy = y - this.my[node] / m;
      let d2 = dx * dx + dy * dy;
      if (this.child[node * 4] === -1) {
        if (this.body[node] === i) m -= 1;
        if (m <= 0) continue;
        if (d2 < 1e-4) {
          dx = (random() - 0.5) * 0.1;
          dy = (random() - 0.5) * 0.1;
          d2 = dx * dx + dy * dy;
        }
      } else {
        const size = this.size[node];
        if (size * size >= THETA2 * d2 || d2 < 1e-4) {
          if (top + 4 > this.stack.length) {
            const bigger = new Int32Array(this.stack.length * 2);
            bigger.set(this.stack);
            this.stack = bigger;
          }
          for (let q = 0; q < 4; q += 1) this.stack[top++] = this.child[node * 4 + q];
          continue;
        }
      }
      const f = (k2 * m) / d2;
      fx += dx * f;
      fy += dy * f;
    }
    disp[i * 2] += fx;
    disp[i * 2 + 1] += fy;
  }
}

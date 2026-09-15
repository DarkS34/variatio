/**
 * WHERE A NAME MAY GO: an occupancy grid over the canvas, in screen pixels.
 *
 * Names are drawn at a fixed pixel size whatever the zoom, so what decides whether one is
 * readable is whether it collides with another ON SCREEN. The previous check compared every
 * candidate against every name already placed — quadratic in the names, and with every label
 * of a 10 000-concept map as a candidate once zoomed in, a frame of seconds. A grid of small
 * cells answers the same question in the cells a box covers, whatever has been placed before.
 *
 * Conservative on purpose: a box claims every cell it touches, so two names can be refused for
 * overlapping by less than a cell, and never drawn one over the other.
 */
export class LabelGrid {
  private readonly cell: number;
  private columns = 0;
  private rows = 0;
  private taken = new Uint8Array(0);

  constructor(cell = 8) {
    this.cell = cell;
  }

  /** Start a frame over a canvas of this size, reusing the buffer when it still fits. */
  reset(width: number, height: number) {
    this.columns = Math.max(1, Math.ceil(width / this.cell));
    this.rows = Math.max(1, Math.ceil(height / this.cell));
    const size = this.columns * this.rows;
    if (this.taken.length < size) this.taken = new Uint8Array(size);
    else this.taken.fill(0, 0, size);
  }

  /**
   * Claim the box `[x0, y0]–[x1, y1]` if none of its cells is taken, and say whether it was.
   * `force` claims it anyway — the name a person asked for is drawn over whatever is there.
   * A box wholly off the canvas is refused: nothing of it would be seen.
   */
  place(x0: number, y0: number, x1: number, y1: number, force = false): boolean {
    const c0 = Math.max(0, Math.floor(x0 / this.cell));
    const r0 = Math.max(0, Math.floor(y0 / this.cell));
    const c1 = Math.min(this.columns - 1, Math.floor(x1 / this.cell));
    const r1 = Math.min(this.rows - 1, Math.floor(y1 / this.cell));
    if (c0 > c1 || r0 > r1) return false;
    if (!force) {
      for (let row = r0; row <= r1; row += 1) {
        const base = row * this.columns;
        for (let column = c0; column <= c1; column += 1) {
          if (this.taken[base + column]) return false;
        }
      }
    }
    for (let row = r0; row <= r1; row += 1) {
      this.taken.fill(1, row * this.columns + c0, row * this.columns + c1 + 1);
    }
    return true;
  }
}

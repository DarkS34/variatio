import qrcode from "qrcode-generator";

/**
 * A QR code as one SVG path, drawn by the browser: no image travels and the CSP stays as it
 * is. Medium error correction (`M`), which survives a projector's blur, and the quiet zone of
 * four modules a scanner needs around the code, counted in `size`.
 */
export interface QrDrawing {
  /** The side of the square, in modules, quiet zone included. */
  size: number;
  /** Every dark module, as squares of one module in one path. */
  path: string;
}

const QUIET = 4;

export function qrDrawing(text: string): QrDrawing {
  const code = qrcode(0, "M");
  code.addData(text);
  code.make();
  const count = code.getModuleCount();
  const squares: string[] = [];
  for (let row = 0; row < count; row += 1) {
    for (let col = 0; col < count; col += 1) {
      if (code.isDark(row, col)) squares.push(`M${col + QUIET} ${row + QUIET}h1v1h-1z`);
    }
  }
  return { size: count + QUIET * 2, path: squares.join("") };
}

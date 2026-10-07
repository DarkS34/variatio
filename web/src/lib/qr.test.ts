import { describe, expect, it } from "vitest";

import { qrDrawing } from "./qr";

describe("qrDrawing", () => {
  it("draws a square with its quiet zone and the three finder patterns' corners dark", () => {
    const { size, path } = qrDrawing("https://variatio.app/invite?token=" + "a".repeat(43));
    expect(size).toBeGreaterThanOrEqual(21 + 8);
    // The top-left module of the top-left finder pattern sits just inside the quiet zone.
    expect(path).toContain("M4 4h1v1h-1z");
    expect(path).toContain(`M${size - 5} 4h1v1h-1z`);
    expect(path).toContain(`M4 ${size - 5}h1v1h-1z`);
  });
});

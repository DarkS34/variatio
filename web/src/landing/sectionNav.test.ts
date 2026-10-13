import { describe, expect, it } from "vitest";

import { sectionAt } from "./sectionNav";

const IDS = ["how", "demo"];
const LINE = 300;

describe("which section the header marks", () => {
  it("is none above the first linked section: the hero is no link's", () => {
    expect(sectionAt([900, 1600], IDS, LINE, false)).toBeNull();
  });

  it("is the last whose top has passed the reading line", () => {
    expect(sectionAt([-500, 200], IDS, LINE, false)).toBe("demo");
    expect(sectionAt([-500, 301], IDS, LINE, false)).toBe("how");
  });

  it("is the last of all at the foot of the page, though its top never reached the line", () => {
    expect(sectionAt([-1200, 420], IDS, LINE, true)).toBe("demo");
  });

  it("skips a section that is not on the page", () => {
    expect(sectionAt([null, 100], IDS, LINE, false)).toBe("demo");
  });
});

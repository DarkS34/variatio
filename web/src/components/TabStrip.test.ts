import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { TabStrip, tabIds } from "./TabStrip";

/** The strip as the server would draw it, with the second tab chosen. */
function markup(counts: [number | undefined, number | undefined], id?: string) {
  return renderToStaticMarkup(
    createElement(TabStrip<"generate" | "mine">, {
      label: "Generate exercises",
      id,
      items: [
        { value: "generate", label: "Generate", count: counts[0] },
        { value: "mine", label: "My exercises", count: counts[1] },
      ],
      value: "mine",
      onChange: () => undefined,
    }),
  );
}

describe("TabStrip", () => {
  it("is a labelled tablist whose chosen tab alone is selected and in the tab order", () => {
    const html = markup([undefined, 3]);
    expect(html).toContain('role="tablist" aria-label="Generate exercises"');
    expect(html).toMatch(/role="tab" aria-selected="false" tabindex="-1"[^>]*>Generate</);
    expect(html).toMatch(/role="tab" aria-selected="true" tabindex="0"[^>]*>My exercises/);
  });

  it("names each tab and the panel it controls only when given an id", () => {
    const { tab, panel } = tabIds("gen", "mine");
    expect(markup([undefined, 3], "gen")).toContain(`id="${tab}" aria-controls="${panel}"`);
    expect(markup([undefined, 3])).not.toContain("aria-controls");
  });

  it("draws a count above zero and nothing for zero or unknown", () => {
    expect(markup([undefined, 3])).toMatch(/My exercises<span[^>]*>3<\/span>/);
    expect(markup([0, 0])).not.toContain("<span");
  });
});

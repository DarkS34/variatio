import { describe, expect, it } from "vitest";

import { safeHref } from "./Markdown";

// The markdown this renderer is handed is a generated item field or a bank statement, so a
// link's scheme is attacker input by way of a poisoned raw corpus. Until the allowlist, the
// only thing between `[pulsa](javascript:…)` and a live anchor in an authenticated page was
// the CSP.
describe("safeHref", () => {
  it("keeps the three schemes a teaching corpus has a reason to carry", () => {
    expect(safeHref("https://docs.python.org/3/")).toBe("https://docs.python.org/3/");
    expect(safeHref("http://ejemplo.test/a?b=1#c")).toBe("http://ejemplo.test/a?b=1#c");
    expect(safeHref("mailto:profe@ejemplo.test")).toBe("mailto:profe@ejemplo.test");
    expect(safeHref("MAILTO:profe@ejemplo.test")).toBe("MAILTO:profe@ejemplo.test");
  });

  it("refuses a scheme that executes", () => {
    for (const href of [
      "javascript:alert(1)",
      "JaVaScRiPt:alert(1)",
      "  javascript:alert(1)",
      "vbscript:msgbox",
      "data:text/html;base64,PHNjcmlwdD4=",
      "file:///etc/passwd",
    ]) {
      expect(safeHref(href)).toBeNull();
    }
  });

  // A browser strips C0 controls before it parses the scheme, so the escaped forms below are
  // working URLs that a naive `startsWith("javascript:")` never sees.
  it("refuses a scheme hidden behind control characters", () => {
    expect(safeHref("java\u0001script:alert(1)")).toBeNull();
    expect(safeHref("\u0000javascript:alert(1)")).toBeNull();
    expect(safeHref("java\tscript:alert(1)")).toBeNull();
    expect(safeHref("java\nscript:alert(1)")).toBeNull();
  });

  // No scheme means no script: a relative reference cannot express `javascript:`, and
  // refusing it would cost a corpus its own anchors for nothing.
  it("lets a relative reference through", () => {
    expect(safeHref("#solucion")).toBe("#solucion");
    expect(safeHref("./figura.png")).toBe("./figura.png");
    expect(safeHref("apartado/2")).toBe("apartado/2");
  });
});

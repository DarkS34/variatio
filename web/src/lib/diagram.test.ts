import { describe, expect, it } from "vitest";

import { diagramSource, DRAWN_DIAGRAMS, isDiagramTag, isDrawableDiagram } from "./diagram";

const CLASS = "classDiagram\n    class Proyecto {\n        +codigo\n    }\n\n    class Socio\n    Proyecto --> Socio";

describe("diagramSource", () => {
  it("recognises a bare diagram by its header line", () => {
    expect(diagramSource(CLASS)).toBe(CLASS);
    expect(diagramSource("graph TD\n  A --> B")).toBe("graph TD\n  A --> B");
    expect(diagramSource("flowchart LR\n  A --- B")).not.toBeNull();
    expect(diagramSource("sequenceDiagram\n  A->>B: hola")).not.toBeNull();
    expect(diagramSource("stateDiagram-v2\n  [*] --> S")).not.toBeNull();
    expect(diagramSource("mindmap\n  root((a))")).not.toBeNull();
    expect(diagramSource("gantt\n  title x")).not.toBeNull();
  });

  it("skips what Mermaid allows before the header", () => {
    expect(diagramSource("\n\n  classDiagram\n  class A")).not.toBeNull();
    expect(diagramSource("%%{init: {'theme':'base'}}%%\nflowchart TD\n  A")).not.toBeNull();
    expect(diagramSource("---\ntitle: x\n---\nflowchart TD\n  A")).not.toBeNull();
  });

  it("keeps blank lines inside the diagram", () => {
    // The reference bank's class diagrams separate their classes with blank lines.
    expect(diagramSource(CLASS)).toContain("\n\n");
  });

  it("refuses prose that merely opens with a diagram word", () => {
    expect(diagramSource("graph theory says that every tree has n-1 edges")).toBeNull();
    expect(diagramSource("Pie charts are misleading")).toBeNull();
    expect(diagramSource("pie de página: ninguno")).toBeNull();
    expect(diagramSource("Realiza un diagrama de clases del sistema")).toBeNull();
    expect(diagramSource("")).toBeNull();
  });

  it("leaves a fenced text to the markdown layer", () => {
    expect(diagramSource("```mermaid\ngraph TD\n  A --> B\n```")).toBeNull();
    expect(diagramSource("Solución:\n\n```mermaid\nclassDiagram\n```")).toBeNull();
  });
});

describe("isDiagramTag", () => {
  it("names only the mermaid fence", () => {
    expect(isDiagramTag("mermaid")).toBe(true);
    expect(isDiagramTag(" Mermaid ")).toBe(true);
    expect(isDiagramTag("python")).toBe(false);
    expect(isDiagramTag("")).toBe(false);
  });
});

describe("isDrawableDiagram", () => {
  it("gates a fence's BODY the way a bare block is gated", () => {
    expect(isDrawableDiagram("classDiagram\n  class A")).toBe(true);
    expect(isDrawableDiagram("sequenceDiagram\n  A->>B: hola")).toBe(true);
  });

  // The kinds `vite/mermaid-subset.ts` leaves out of the bundle. A fence holding one of them
  // is shown as its own source, which is the whole reason the build may leave it out.
  it("refuses the kinds this app does not bundle", () => {
    // Everything the transcription prompt does not ask for, `usecase-beta` included: the
    // prompt writes a use-case diagram as a `flowchart LR`, which is why that one is drawn.
    for (const header of ["usecase-beta", "pie", "gitGraph", "C4Context", "journey", "cynefin-beta", "wardley-beta"]) {
      expect(isDrawableDiagram(`${header}\n  whatever`)).toBe(false);
    }
  });

  it("names every kind once, with mermaid's own id", () => {
    expect(new Set(DRAWN_DIAGRAMS).size).toBe(DRAWN_DIAGRAMS.length);
    expect(DRAWN_DIAGRAMS).toHaveLength(8);
    expect(DRAWN_DIAGRAMS).toContain("flowchart-v2");
    expect(DRAWN_DIAGRAMS).not.toContain("flowchart-elk");
  });
});

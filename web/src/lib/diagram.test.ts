import { describe, expect, it } from "vitest";

import { diagramSource, isDiagramTag } from "./diagram";

const CLASS = "classDiagram\n    class Proyecto {\n        +codigo\n    }\n\n    class Socio\n    Proyecto --> Socio";

describe("diagramSource", () => {
  it("recognises a bare diagram by its header line", () => {
    expect(diagramSource(CLASS)).toBe(CLASS);
    expect(diagramSource("graph TD\n  A --> B")).toBe("graph TD\n  A --> B");
    expect(diagramSource("flowchart LR\n  A --- B")).not.toBeNull();
    expect(diagramSource("sequenceDiagram\n  A->>B: hola")).not.toBeNull();
    expect(diagramSource("stateDiagram-v2\n  [*] --> S")).not.toBeNull();
    expect(diagramSource("mindmap\n  root((a))")).not.toBeNull();
    expect(diagramSource("usecase-beta\n  actor A")).not.toBeNull();
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

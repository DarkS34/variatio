import { describe, expect, it } from "vitest";

import { DISPLAY_OPEN, splitInlineMath, takeDisplayMath } from "./math";

const tex = (text: string) =>
  splitInlineMath(text)
    .filter((t) => t.kind === "math")
    .map((t) => (t as { tex: string }).tex);

describe("splitInlineMath", () => {
  // Straight out of `generations`: this is what the model writes for an automata item.
  it("finds the formulas a generated item actually carries", () => {
    expect(tex("Considere $\\Sigma = \\{0, 1\\}$ y el estado $q_0$.")).toEqual([
      "\\Sigma = \\{0, 1\\}",
      "q_0",
    ]);
    expect(tex("  $\\delta(q_0, 1) = q_1$")).toEqual(["\\delta(q_0, 1) = q_1"]);
    expect(tex("a) $1(0|1)^*0$")).toEqual(["1(0|1)^*0"]);
  });

  it("keeps the text around them, in order", () => {
    expect(splitInlineMath("antes $x$ después")).toEqual([
      { kind: "text", value: "antes " },
      { kind: "math", tex: "x" },
      { kind: "text", value: " después" },
    ]);
  });

  // The reference bank's LR tables: `$` is the end-of-input marker, alone in a cell and
  // several times per item. Pairing two of them swallows the row in between.
  it("does not pair the end-of-input markers of a parsing table", () => {
    expect(tex("|   | a  | b  | e  | x  | y  | $  | S  | A  | B  |")).toEqual([]);
    expect(tex("Arcs: 8 --> $ --> Accept\nArcs: 11 --> $ --> Accept")).toEqual([]);
    expect(tex("(c) State0 - Clousure(A->+B+, $):")).toEqual([]);
  });

  it("does not pair them in an UNPADDED table row either", () => {
    expect(tex("|a|$|S|$|b|")).toEqual([]);
    expect(tex("cell |$| and |$| here")).toEqual([]);
  });

  it("still typesets a formula in a padded cell, which is what the pages write", () => {
    expect(tex("| $A' \\rightarrow \\cdot A$ | $B \\to c$ |")).toEqual([
      "A' \\rightarrow \\cdot A",
      "B \\to c",
    ]);
  });

  it("does not read a price or an escaped dollar as a delimiter", () => {
    expect(tex("cuesta US$5 y el otro $6")).toEqual([]);
    expect(tex("un literal \\$x\\$ en el texto")).toEqual([]);
  });

  it("never crosses a line, so a stray dollar cannot eat a paragraph", () => {
    expect(tex("primero $a\nsegundo b$ tercero")).toEqual([]);
  });

  it("leaves a code span alone", () => {
    expect(tex("Siguiente (A): $+x y el código `printf(\"$d\")` aparte")).toEqual([]);
  });

  it("lets a formula contain an escaped dollar", () => {
    expect(tex("el coste $a \\$ b$ final")).toEqual(["a \\$ b"]);
  });

  it("ignores `$$`, which is a block and not a span", () => {
    expect(tex("$$x + y$$")).toEqual([]);
  });
});

describe("takeDisplayMath", () => {
  const block = (text: string) => takeDisplayMath(text.split("\n"), 0);

  it("takes a formula written on one line", () => {
    expect(block("$$E \\to E + T$$")).toEqual({ tex: "E \\to E + T", next: 1 });
  });

  // The lines of a grammar start with `-`, with `\\` and with `|`, every one of which the
  // paragraph rules would have claimed. This is why it is a block and not a span.
  it("takes one written over several, and says where it ended", () => {
    const source = "$$\n\\begin{array}{l}\nA \\to aB \\\\\nB \\to b\n\\end{array}\n$$\nsigue la prosa";

    expect(block(source)).toEqual({
      tex: "\\begin{array}{l}\nA \\to aB \\\\\nB \\to b\n\\end{array}",
      next: 6,
    });
  });

  it("runs to the end when the closing delimiter never arrives", () => {
    expect(block("$$\nA \\to aB")).toEqual({ tex: "A \\to aB", next: 2 });
  });

  it("gives back nothing for an empty pair, which is not a formula", () => {
    expect(block("$$$$").tex).toBe("");
  });
});

describe("DISPLAY_OPEN", () => {
  it("opens on a line that starts with the delimiter, indented or not", () => {
    expect(DISPLAY_OPEN.test("$$x$$")).toBe(true);
    expect(DISPLAY_OPEN.test("   $$")).toBe(true);
  });

  it("does not open mid-sentence, where the paragraph owns the line", () => {
    expect(DISPLAY_OPEN.test("el coste $$x$$ del paso")).toBe(false);
    expect(DISPLAY_OPEN.test("| a | b | $ | S |")).toBe(false);
  });
});

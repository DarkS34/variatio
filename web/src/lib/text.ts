/**
 * Comparing what somebody typed against what is on screen.
 *
 * Every search box in the app has the same problem: the reader types «grafico» and the
 * row says «Gráfico», or types in capitals what is written in lower case. Folding both
 * sides through NFD, dropping the combining marks and lowering is what makes the two
 * meet, and it has to be ONE function — a second copy of an accent-folding rule is a
 * second place for two search boxes to disagree about what «matches» means.
 */
export const fold = (text: string) =>
  Array.from(text.normalize("NFD"))
    .filter((glyph) => glyph.charCodeAt(0) < 0x300 || glyph.charCodeAt(0) > 0x36f)
    .join("")
    .toLowerCase();

/**
 * Comparing what somebody typed against what is on screen.
 *
 * Every search box in the app has the same problem: the reader types "grafico" and the
 * row says "Gráfico", or types in capitals what is written in lower case. Folding both
 * sides through NFD, dropping the combining marks and lowering is what makes the two
 * meet, and it has to be ONE function — a second copy of an accent-folding rule is a
 * second place for two search boxes to disagree about what "matches" means.
 */
export const fold = (text: string) =>
  Array.from(text.normalize("NFD"))
    .filter((glyph) => glyph.charCodeAt(0) < 0x300 || glyph.charCodeAt(0) > 0x36f)
    .join("")
    .toLowerCase();

/**
 * An enum value from the profile, as a person should read it.
 *
 * The values come from the item type's JSON schema and are identifiers: the reference
 * profile declares `basico`, `intermedio`, `avanzado`, and the generate form painted them
 * exactly like that — lower-case and unaccented — next to a "Cualquiera" that had been
 * written by hand. They are the profile's wire values and must not be translated, so this
 * only does what is safe on any of them: underscores become spaces and the first letter
 * is capitalised.
 *
 * It deliberately does NOT restore accents. Guessing that `basico` is "básico" works for
 * Spanish and fails for every identifier that is not a word; a profile that wants proper
 * labels should declare them, and that is a change to the artifact rather than to this.
 */
export function readableValue(value: string): string {
  const spaced = value.replace(/[_-]+/g, " ").trim();
  if (!spaced) return value;
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

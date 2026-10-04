import { describe, expect, it } from "vitest";

/** One entry as a test reads it: a sentence, or the two forms of a counted one. */
type Entry = string | { readonly one: string; readonly other: string };

/**
 * Describe what a Spanish catalogue and its English translation must agree on.
 *
 * Shared by the core's test and each optional function's, because the rules are the same
 * wherever a catalogue lives and a fourth copy of them would drift from the first three.
 */
export function describeCatalogue(
  name: string,
  es: Readonly<Record<string, Entry>>,
  en: Readonly<Record<string, Entry>>,
) {
  describe(name, () => {
    it("declare exactly the same keys", () => {
      // TypeScript already refuses a missing one; this is what catches a key that exists in
      // `en` and not in `es`, which the type cannot see because `es` is the source.
      expect(Object.keys(en).sort()).toEqual(Object.keys(es).sort());
    });

    it("agree on which entries are plural", () => {
      for (const key of Object.keys(es)) {
        expect(typeof en[key], key).toBe(typeof es[key]);
      }
    });

    it("leave no value empty", () => {
      for (const [key, value] of [...Object.entries(es), ...Object.entries(en)]) {
        const text = typeof value === "string" ? value : `${value.one}${value.other}`;
        expect(text.trim(), key).not.toBe("");
      }
    });

    it("keep every interpolation the other one has", () => {
      // A `{name}` dropped in translation renders a sentence with a hole in it, and nothing
      // else would notice: the type is `string` either way.
      const slots = (value: unknown): string[] => {
        const text = typeof value === "string" ? value : Object.values(value as object).join(" ");
        return [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
      };
      for (const key of Object.keys(es)) {
        expect(slots(en[key]), key).toEqual(slots(es[key]));
      }
    });
  });
}

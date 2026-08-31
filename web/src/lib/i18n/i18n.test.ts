import { beforeAll, beforeEach, describe, expect, it } from "vitest";

import { en } from "./en";
import { es } from "./es";
import { ensureCatalogue, LANGUAGES, localeStore, normalise, pluralise, translate } from "./index";

// `en` is fetched on demand now, so asking for an English string before it lands answers
// in Spanish — the deliberate fallback. Without this the suite would go on passing while
// testing the wrong catalogue, which is exactly what it did when the split was written:
// `pluralise("en", "count.items", 1)` came back «1 ítem».
beforeAll(() => ensureCatalogue("en"));

describe("normalise", () => {
  it("folds the regional tag a browser actually sends", () => {
    // `navigator.language` is never a bare code, so a form seeding itself from it would
    // otherwise miss every time.
    expect(normalise("es-ES")).toBe("es");
    expect(normalise("en_US")).toBe("en");
    expect(normalise("  EN  ")).toBe("en");
  });

  it("does not turn what the installation cannot read into something it can", () => {
    for (const value of ["fr", "de-DE", "", "   ", null, undefined]) {
      expect(normalise(value)).toBeNull();
    }
  });
});

describe("the catalogues", () => {
  it("declare exactly the same keys", () => {
    // TypeScript already refuses a missing one; this is what catches a key that exists in
    // `en` and not in `es`, which the type cannot see because `es` is the source.
    expect(Object.keys(en).sort()).toEqual(Object.keys(es).sort());
  });

  it("agree on which entries are plural", () => {
    for (const key of Object.keys(es) as (keyof typeof es)[]) {
      expect(typeof en[key]).toBe(typeof es[key]);
    }
  });

  it("leave no value empty", () => {
    for (const [key, value] of Object.entries({ ...es, ...en })) {
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
    for (const key of Object.keys(es) as (keyof typeof es)[]) {
      expect(slots(en[key]), key).toEqual(slots(es[key]));
    }
  });
});

describe("translate", () => {
  it("fills the named slots", () => {
    expect(translate("es", "language.changed", { name: "English" })).toContain("English");
    expect(translate("en", "language.changed", { name: "Español" })).toContain("Español");
  });

  it("leaves a slot alone when nothing was passed for it", () => {
    // Better a visible `{name}` than an empty gap that reads as finished copy.
    expect(translate("es", "language.changed")).toContain("{name}");
  });
});

describe("pluralise", () => {
  it("picks the singular only at one", () => {
    expect(pluralise("en", "count.items", 1)).toBe("1 exercise");
    expect(pluralise("en", "count.items", 2)).toBe("2 exercises");
    expect(pluralise("en", "count.items", 0)).toBe("0 exercises");
  });

  it("does the same in Spanish, where the app used to write «N ítem(s)»", () => {
    expect(pluralise("es", "count.items", 1)).toBe("1 ejercicio");
    expect(pluralise("es", "count.items", 3)).toBe("3 ejercicios");
  });
});

describe("the store", () => {
  beforeEach(() => {
    localeStore.set("es");
  });

  it("adopts what the account says", () => {
    localeStore.adopt("en-GB");
    expect(localeStore.getSnapshot()).toBe("en");
  });

  it("ignores a language the installation does not speak", () => {
    localeStore.adopt("fr");
    expect(localeStore.getSnapshot()).toBe("es");
  });

  it("notifies its subscribers so a screen redraws", () => {
    let calls = 0;
    const stop = localeStore.subscribe(() => (calls += 1));
    localeStore.set("en");
    localeStore.set("en");
    stop();
    expect(calls).toBe(1);
  });

  it("knows exactly two languages", () => {
    expect(LANGUAGES).toEqual(["es", "en"]);
  });
});

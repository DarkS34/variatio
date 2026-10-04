import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { en } from "./en";
import { es } from "./es";
import {
  ensureCatalogue,
  LANGUAGES,
  localeStore,
  normalise,
  pluralise,
  registerCatalogue,
  translate,
  withCatalogues,
  type Key,
} from "./index";
import { describeCatalogue } from "./testing";

// `en` is fetched on demand now, so asking for an English string before it lands answers
// in Spanish — the deliberate fallback. Without this the suite would go on passing while
// testing the wrong catalogue, which is exactly what it did when the split was written:
// the English count of exercises came back "1 ítem".
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

describeCatalogue("the catalogues", es, en);

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
    expect(pluralise("en", "form.items", 1)).toBe("1 exercise");
    expect(pluralise("en", "form.items", 2)).toBe("2 exercises");
    expect(pluralise("en", "form.items", 0)).toBe("0 exercises");
  });

  it("does the same in Spanish, where the app used to write «N ítem(s)»", () => {
    expect(pluralise("es", "form.items", 1)).toBe("1 ejercicio");
    expect(pluralise("es", "form.items", 3)).toBe("3 ejercicios");
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

describe("a function's catalogue", () => {
  beforeEach(() => {
    localeStore.set("es");
  });

  // Keys no catalogue of the app declares, so the cast: what is under test is the
  // registration, not the app's own strings.
  const key = (name: string) => name as Key;

  it("answers in Spanish the moment it is registered", () => {
    registerCatalogue("test-spanish", { "test.spanish.greeting": "Hola, {name}" }, {});
    expect(translate("es", key("test.spanish.greeting"), { name: "Ana" })).toBe("Hola, Ana");
  });

  it("falls back to Spanish until its English arrives through the loader", async () => {
    type Counted = { "test.english.count": { one: string; other: string } };
    localeStore.set("en");
    let deliver: (entries: Counted) => void = () => {};
    const english = vi.fn(() => new Promise<Counted>((resolve) => (deliver = resolve)));
    registerCatalogue(
      "test-english",
      { "test.english.count": { one: "1 vuelta", other: "{n} vueltas" } },
      { en: english },
    );

    // Registered while the reader reads English: the entries are already on their way.
    expect(english).toHaveBeenCalledTimes(1);
    expect(pluralise("en", key("test.english.count"), 2)).toBe("2 vueltas");

    deliver({ "test.english.count": { one: "1 lap", other: "{n} laps" } });
    await ensureCatalogue("en");
    expect(pluralise("en", key("test.english.count"), 1)).toBe("1 lap");
    expect(pluralise("en", key("test.english.count"), 2)).toBe("2 laps");
    expect(pluralise("es", key("test.english.count"), 2)).toBe("2 vueltas");
    expect(english).toHaveBeenCalledTimes(1);
  });

  it("is fetched for a language chosen after it was registered", async () => {
    const english = vi.fn(async () => ({ "test.later.title": "Later" }));
    registerCatalogue("test-later", { "test.later.title": "Después" }, { en: english });
    expect(english).not.toHaveBeenCalled();

    await ensureCatalogue("en");
    expect(english).toHaveBeenCalledTimes(1);
    expect(translate("en", key("test.later.title"))).toBe("Later");
  });

  it("holds back the lazy module that registered it until its English is here", async () => {
    localeStore.set("en");
    let deliver: () => void = () => {};
    // What `import()` of a function's screen does: evaluating the module registers.
    const screen = Promise.resolve().then(() => {
      registerCatalogue("test-lazy", { "test.lazy.title": "Pantalla" }, {
        en: () =>
          new Promise((resolve) => {
            deliver = () => resolve({ "test.lazy.title": "Screen" });
          }),
      });
      return { Screen: "screen" };
    });

    let handed = false;
    const ready = withCatalogues(screen).then((module) => {
      handed = true;
      return module;
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(handed).toBe(false);

    deliver();
    expect(await ready).toEqual({ Screen: "screen" });
    expect(translate("en", key("test.lazy.title"))).toBe("Screen");
  });

  it("stays on Spanish when its English cannot be fetched", async () => {
    const failing = vi.fn(() => Promise.reject(new Error("offline")));
    registerCatalogue("test-failing", { "test.failing.title": "Sin red" }, { en: failing });

    await expect(ensureCatalogue("en")).resolves.toBeUndefined();
    expect(translate("en", key("test.failing.title"))).toBe("Sin red");
  });
});

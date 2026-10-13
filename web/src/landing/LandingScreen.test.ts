import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it, vi } from "vitest";

// The client's stores read the tab's storage when they load; node has none.
vi.hoisted(() => {
  const memory = (): Storage => {
    const held = new Map<string, string>();
    return {
      get length() {
        return held.size;
      },
      clear: () => held.clear(),
      getItem: (key) => held.get(key) ?? null,
      key: (index) => [...held.keys()][index] ?? null,
      removeItem: (key) => void held.delete(key),
      setItem: (key, value) => void held.set(key, String(value)),
    };
  };
  globalThis.sessionStorage ??= memory();
  globalThis.localStorage ??= memory();
  // The theme's store asks the window for its colour scheme when it loads; the landing
  // draws the application, whose shell reads that store.
  const stub = { matches: false, addEventListener: () => {}, removeEventListener: () => {} };
  (globalThis as { window?: unknown }).window ??= globalThis;
  (globalThis as { location?: unknown }).location ??= { search: "", pathname: "/" };
  (globalThis as { matchMedia?: unknown }).matchMedia ??= () => stub;
  (globalThis as { document?: unknown }).document ??= {
    documentElement: { dataset: {}, lang: "" },
    addEventListener: () => {},
    removeEventListener: () => {},
  };
});

import { ToastProvider } from "@/components/ui/toast";
import { ensureCatalogue, localeStore } from "@/lib/i18n";

import { en } from "./i18n/en";
import { es } from "./i18n/es";
import { DemoPage } from "./DemoPage";
import { LandingScreen } from "./LandingScreen";

/** The page as it first draws: its own copy and an empty frame where the demo mounts. */
function markup() {
  const client = new QueryClient();
  return renderToStaticMarkup(
    createElement(QueryClientProvider, { client }, createElement(ToastProvider, null, createElement(LandingScreen))),
  );
}

beforeAll(() => localeStore.adopt("es"));

describe("the landing", () => {
  it("says entry is by invitation and offers the login form", () => {
    const html = markup();
    expect(html).toContain(es["landing.join.title"]);
    expect(html).toContain(es["landing.join.body"]);
    // `/` is the landing itself for a visitor: the form is one route over.
    expect(html).toMatch(/<a href="\/login"[^>]*>(?:<svg[^>]*>.*?<\/svg>)?Entrar/);
  });

  it("keeps the language apart from entering: a quiet switch, not a button like it", () => {
    const html = markup();
    const switcher = /<div role="group" aria-label="Idioma"[^>]*>(.*?)<\/div>/.exec(html)?.[1] ?? "";
    expect(switcher).toContain('aria-label="Español"');
    expect(switcher).toContain('aria-label="English"');
    expect(switcher).not.toContain("Entrar");
  });

  it("shows the example of the first subject, and lets the visitor turn to the others", () => {
    const html = markup();
    expect(html).toContain('role="tablist" aria-label="Asignatura del ejemplo"');
    for (const subject of ["Programación", "Enfermería", "Lengua"]) {
      expect(html).toMatch(new RegExp(`role="tab"[^>]*>${subject}<`));
    }
    const shown = /<div role="tabpanel"[^>]*>(.*)$/.exec(html)?.[1] ?? "";
    expect(shown).toContain(es["landing.example.programming.statement"]);
    expect(html).toContain('id="landing-example-panel-programming" aria-labelledby="landing-example-tab-programming"');
  });

  it("keeps every example mounted, the others hidden, so a tab fades instead of redrawing", () => {
    const html = markup();
    const panels = [...html.matchAll(/<div role="tabpanel" id="landing-example-panel-(\w+)"[^>]*class="([^"]*)"/g)];
    expect(panels.map((match) => match[1])).toEqual(["programming", "pharmacology", "language"]);
    expect(panels.map((match) => match[2].includes(" visible "))).toEqual([true, false, false]);
    expect(panels.slice(1).every((match) => match[2].includes("invisible"))).toBe(true);
  });

  it("tells a teacher's three moves in plain verbs, not the application's names for its steps", () => {
    const html = markup();
    for (const key of ["landing.how.step1Title", "landing.how.step2Title", "landing.how.step3Title"] as const) {
      expect(html).toContain(es[key]);
    }
    const how = /<section id="how"(.*?)<\/section>/.exec(html)?.[1] ?? "";
    expect(how).not.toContain("Banco de ejercicios");
  });

  it("opens each linked section with its own heading", () => {
    const html = markup();
    for (const id of ["how", "demo"]) {
      expect(html).toContain(`<section id="${id}" aria-labelledby="${id}-title"`);
      expect(html).toContain(`id="${id}-head"`);
    }
  });

  it("spends the coral on one thing alone: trying the demo", () => {
    const html = markup();
    expect(html.match(/bg-attention-fill/g)).toHaveLength(1);
    expect(html).toMatch(/<a href="\/demo"[^>]*bg-attention-fill[^>]*>Probar la demo/);
  });

  it("reads in English once switched", async () => {
    await ensureCatalogue("en");
    localeStore.set("en");
    try {
      const html = markup();
      expect(html).toContain(en["landing.join.title"]);
      expect(html).toContain(en["landing.hero.title"]);
      expect(html).toContain(en["landing.example.programming.statement"]);
    } finally {
      localeStore.set("es");
    }
  });

  it("opens the demo on a page of its own, from the start or at the door", () => {
    const html = markup();
    expect(html).toContain('href="/demo"');
    expect(html).toContain('href="/demo?start=generate"');
    // Nothing of the demo is mounted on the landing itself.
    expect(html).not.toContain(`aria-label="${es["landing.demo.frame"]}"`);
  });
});

describe("the demo's page", () => {
  it("draws its own bar — the way back, the samples, its moves, the language — over the frame", () => {
    const client = new QueryClient();
    const html = renderToStaticMarkup(
      createElement(QueryClientProvider, { client }, createElement(ToastProvider, null, createElement(DemoPage))),
    );
    expect(html).toMatch(/<a href="\/"[^>]*>(?:<svg[^>]*>.*?<\/svg>)?Portada/);
    expect(html).toContain(`aria-label="${es["landing.demoPage.samples"]}"`);
    expect(html).toContain(`aria-label="${es["landing.demo.reset"]}"`);
    expect(html).toContain(`aria-label="${es["landing.demo.skip"]}"`);
    expect(html).toContain('aria-label="Idioma"');
    expect(html).toContain(`aria-label="${es["landing.demo.frame"]}"`);
  });
});

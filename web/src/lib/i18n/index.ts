import { useSyncExternalStore } from "react";

import { es, type Catalogue, type Key } from "./es";
import { DEFAULT, type Language, localeStore } from "./locale";

export {
  DEFAULT,
  LANGUAGES,
  LANGUAGE_KEY,
  LANGUAGE_NAMES,
  localeStore,
  normalise,
} from "./locale";
export type { Language } from "./locale";
export type { Key } from "./es";

/**
 * ONE CATALOGUE SHIPS, THE OTHER IS FETCHED, AND THE FALLBACK WAS ALREADY WRITTEN.
 *
 * The two catalogues measured 225,599 bytes of the 653 kB entry chunk — 34.6 % of it —
 * and no reader needs both. `es` stays static because it is three things at once: the
 * DEFAULT, the typed source `en` is checked against, and the fallback `entry()` below has
 * always fallen back to. `en` becomes a chunk of its own, fetched by the readers who read
 * in English.
 *
 * What did NOT change is the contract: `translate` and `pluralise` are still synchronous,
 * still take a language, and still answer on the first call. The window in which `en` has
 * not landed yet renders Spanish prose rather than a raw key — the behaviour the comment
 * on `entry()` already described for a half-applied hot reload. `main.tsx` closes even
 * that window on the normal path by awaiting the catalogue before the first paint; what
 * is left is the account adopting a language `localStorage` did not know, which can
 * happen at most once per browser.
 *
 * The `Catalogue` type relationship is untouched, so a missing translation is still a
 * `tsc` error rather than a runtime fallback nobody notices.
 */
const CATALOGUES: Partial<Record<Language, Catalogue>> = { es };

const LOADERS: Partial<Record<Language, () => Promise<Catalogue>>> = {
  en: () => import("./en").then((module) => module.en),
};

const inFlight = new Map<Language, Promise<void>>();

// A counter and not the catalogue itself: `useSyncExternalStore` compares snapshots by
// identity, and the language does not change when its catalogue arrives — so without a
// second signal the screens that are already mounted would keep the fallback until
// something else re-rendered them.
let revision = 0;
const arrivals = new Set<() => void>();

function subscribeCatalogue(listener: () => void) {
  arrivals.add(listener);
  return () => {
    arrivals.delete(listener);
  };
}

function catalogueRevision() {
  return revision;
}

/**
 * Load a language's catalogue if it is not here yet. Idempotent, deduped, and it never
 * rejects: a fetch that fails leaves the app on the fallback, which is a screen in the
 * wrong language and not a screen that is gone.
 */
export function ensureCatalogue(language: Language): Promise<void> {
  if (CATALOGUES[language]) return Promise.resolve();
  const load = LOADERS[language];
  if (!load) return Promise.resolve();

  let pending = inFlight.get(language);
  if (!pending) {
    pending = load()
      .then((catalogue) => {
        CATALOGUES[language] = catalogue;
        revision += 1;
        for (const listener of arrivals) listener();
      })
      .catch(() => {})
      .finally(() => {
        inFlight.delete(language);
      });
    inFlight.set(language, pending);
  }
  return pending;
}

// Changing the language is the other way a catalogue is asked for, and it happens in three
// places that do not know about each other — the account menu, `adopt` on the session
// query, and the pre-session picker on the invitation screen. One subscription covers all
// three rather than each remembering.
localeStore.subscribe(() => {
  void ensureCatalogue(localeStore.getSnapshot());
});

type Params = Record<string, string | number>;

function fill(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  );
}

function entry(language: Language, key: Key): Catalogue[Key] | undefined {
  // `es` is the source of truth for what a key is, so a language whose catalogue somehow
  // lacks one falls back to it rather than rendering the key. TypeScript already makes a
  // MISSING key unreachable; what this now also covers is the catalogue that has not
  // arrived yet, which is the same fallback for the same reason.
  return CATALOGUES[language]?.[key] ?? CATALOGUES[DEFAULT]?.[key];
}

// Missing from BOTH catalogues is the case the types rule out and a half-applied hot
// reload produces anyway. The key on screen is ugly; reading `.other` off `undefined`
// throws in the middle of a render and takes the whole tree with it.
export function translate(language: Language, key: Key, params?: Params): string {
  const value = entry(language, key);
  if (value === undefined) return key;
  if (typeof value === "string") return fill(value, params);
  // A plural entry read through `t` still renders: `other` is the form that reads sanely
  // with no number, which is better than showing the key.
  return fill(value.other ?? key, params);
}

export function pluralise(language: Language, key: Key, n: number, params?: Params): string {
  const value = entry(language, key);
  if (value === undefined) return key;
  const template = typeof value === "string" ? value : n === 1 ? value.one : value.other;
  return fill(template ?? key, { n, ...params });
}

/**
 * What a PURE function takes instead of a hook.
 *
 * `lib/queue.ts` decides "is it waiting, and behind what", is covered by 30 vitest cases
 * and must not import React. Handing it a translator keeps its criterion testable — the
 * tests pass the Spanish one and their assertions go on meaning what they meant — and
 * keeps the sentences out of it.
 */
export interface Translate {
  t: (key: Key, params?: Params) => string;
  plural: (key: Key, n: number, params?: Params) => string;
}

export function translator(language: Language): Translate {
  return {
    t: (key, params) => translate(language, key, params),
    plural: (key, n, params) => pluralise(language, key, n, params),
  };
}

export function useLanguage(): Language {
  return useSyncExternalStore(localeStore.subscribe, localeStore.getSnapshot);
}

/**
 * The hook every screen uses. `t` for a string, `plural` for anything counted — the two
 * are separate because "1 ítem" and "2 ítems" are one decision in Spanish and a different
 * one in English, and a single function would have to guess which it was being asked.
 */
export function useT(): Translate & { language: Language } {
  const language = useLanguage();
  // Two subscriptions, because two different things move: the language, and whether its
  // catalogue has landed. Neither implies the other.
  useSyncExternalStore(subscribeCatalogue, catalogueRevision, catalogueRevision);
  return { language, ...translator(language) };
}

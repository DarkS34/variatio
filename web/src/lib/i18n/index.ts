import { useSyncExternalStore } from "react";

import type { es as evaluation } from "@/evaluation/i18n/es";
import type { es as tutor } from "@/tutor/i18n/es";

import { es, type CatalogueOf } from "./es";
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
export type { CatalogueOf } from "./es";

/**
 * Every key the interface may ask for: the core's and each optional function's.
 *
 * The functions' keys reach this module as TYPES only. A value import would put their
 * strings back in the entry chunk, which is what moving them out was for, and
 * `pnpm check:lazy` refuses it. What the type cannot say is WHO may read a key: `tsc`
 * accepts a tutor key read from core, where it renders as its own name until the tutor has
 * been loaded. `pnpm check:i18n` refuses that one.
 */
export type Key = keyof typeof es | keyof typeof evaluation | keyof typeof tutor;

/** One entry of a catalogue: a sentence, or the two forms of a counted one. */
type Entry = string | { readonly one: string; readonly other: string };

/** How a catalogue fetches the languages it does not ship, typed against its Spanish `T`. */
export type CatalogueLoaders<T> = Partial<Record<Language, () => Promise<CatalogueOf<T>>>>;

/** A registered catalogue: the core's, or an optional function's. */
interface Part {
  loaders: Partial<Record<Language, () => Promise<Readonly<Record<string, Entry>>>>>;
  loaded: Set<Language>;
  inFlight: Map<Language, Promise<void>>;
}

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
 *
 * THE OPTIONAL FUNCTIONS' STRINGS ARRIVE WITH THEIR CODE. What only the evaluation or only
 * the tutor reads is a catalogue of its own, in its folder, registered here when its code
 * loads (`registerCatalogue`); so `CATALOGUES` holds, per language, the entries of every
 * catalogue registered and arrived so far, merged. An account a function is closed to
 * downloads none of its strings, in either language. Measured on 2026-10-04: 438 keys
 * moved (318 the evaluation's, 120 the tutor's), and the entry chunk went from 278,882 to
 * 250,455 bytes (−10.2 %), the core's `en` from 144,223 to 116,156.
 */
const CATALOGUES: Partial<Record<Language, Record<string, Entry>>> = {};

const PARTS = new Map<string, Part>();

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
 * Add a catalogue: its Spanish entries at once, its other languages when they are read.
 *
 * The core registers here, below. An optional function registers from its own `i18n`
 * module, which every module of the function that core loads lazily imports first, so its
 * Spanish entries are here before any of its screens renders. When the reader's language is
 * another, it is fetched now and the mounted screens redraw when it arrives; a language
 * chosen later is fetched by `ensureCatalogue`, for every catalogue registered by then.
 *
 * A name registered again replaces the earlier one: that is a hot reload re-evaluating the
 * module that registers it.
 */
export function registerCatalogue<T extends Readonly<Record<string, Entry>>>(
  name: string,
  spanish: T,
  loaders: CatalogueLoaders<T>,
): void {
  const part: Part = {
    loaders: loaders as Part["loaders"],
    loaded: new Set([DEFAULT]),
    inFlight: new Map(),
  };
  PARTS.set(name, part);
  Object.assign((CATALOGUES[DEFAULT] ??= {}), spanish);
  void load(name, part, localeStore.getSnapshot());
}

/** Fetch one catalogue's entries in one language, once, merging them when they arrive. */
function load(name: string, part: Part, language: Language): Promise<void> {
  if (part.loaded.has(language)) return Promise.resolve();
  const read = part.loaders[language];
  if (!read) return Promise.resolve();

  let pending = part.inFlight.get(language);
  if (!pending) {
    pending = read()
      .then((entries) => {
        // Registered again while this was on its way: the newer registration fills it.
        if (PARTS.get(name) !== part) return;
        Object.assign((CATALOGUES[language] ??= {}), entries);
        part.loaded.add(language);
        revision += 1;
        for (const listener of arrivals) listener();
      })
      .catch(() => {})
      .finally(() => {
        part.inFlight.delete(language);
      });
    part.inFlight.set(language, pending);
  }
  return pending;
}

/**
 * Load a language's entries for every catalogue registered so far, where they are not here
 * yet. Idempotent, deduped, and it never rejects: a fetch that fails leaves the app on the
 * fallback, which is a screen in the wrong language and not a screen that is gone.
 */
export function ensureCatalogue(language: Language): Promise<void> {
  return Promise.all([...PARTS].map(([name, part]) => load(name, part, language))).then(
    () => undefined,
  );
}

/**
 * Hand over a lazily imported module once the catalogues it registered are here in the
 * reader's language.
 *
 * Importing a function's module registers its catalogue, and the English entries only start
 * on their way then. `React.lazy` keeps its fallback until this resolves, so a function's
 * screen does not draw its first frame in Spanish for somebody who reads English.
 */
export function withCatalogues<T>(module: Promise<T>): Promise<T> {
  return module.then((loaded) => ensureCatalogue(localeStore.getSnapshot()).then(() => loaded));
}

registerCatalogue("core", es, {
  en: () => import("./en").then((module) => module.en),
});

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

function entry(language: Language, key: Key): Entry | undefined {
  // `es` is the source of truth for what a key is, so a language whose catalogue somehow
  // lacks one falls back to it rather than rendering the key. TypeScript already makes a
  // MISSING key unreachable; what this now also covers is the catalogue that has not
  // arrived yet, which is the same fallback for the same reason.
  return CATALOGUES[language]?.[key] ?? CATALOGUES[DEFAULT]?.[key];
}

// Missing from BOTH languages is the case the types rule out and a half-applied hot
// reload produces anyway, and so does a function's key read before its catalogue is
// registered. The key on screen is ugly; reading `.other` off `undefined` throws in the
// middle of a render and takes the whole tree with it.
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
  // The same snapshot server-side, so a screen also draws as markup (its tests do).
  return useSyncExternalStore(localeStore.subscribe, localeStore.getSnapshot, localeStore.getSnapshot);
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

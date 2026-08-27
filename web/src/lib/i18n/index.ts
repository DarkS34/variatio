import { useSyncExternalStore } from "react";

import { en } from "./en";
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

const CATALOGUES: Record<Language, Catalogue> = { es, en };

type Params = Record<string, string | number>;

function fill(template: string, params?: Params): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in params ? String(params[name]) : whole,
  );
}

function entry(language: Language, key: Key): Catalogue[Key] | undefined {
  // `es` is the source of truth for what a key is, so a language whose catalogue somehow
  // lacks one falls back to it rather than rendering the key. TypeScript already makes
  // that unreachable; this is what keeps a hot-reloaded half-edit from blanking a screen.
  return CATALOGUES[language]?.[key] ?? CATALOGUES[DEFAULT][key];
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
 * `lib/queue.ts` decides «is it waiting, and behind what», is covered by 30 vitest cases
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
 * are separate because «1 ítem» and «2 ítems» are one decision in Spanish and a different
 * one in English, and a single function would have to guess which it was being asked.
 */
export function useT(): Translate & { language: Language } {
  const language = useLanguage();
  return { language, ...translator(language) };
}

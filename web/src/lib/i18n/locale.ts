/**
 * Which language the INTERFACE is drawn in.
 *
 * Not the same question as a workspace's `prompt_language`, and deliberately not stored
 * in the same place: this one belongs to the person, so it lives on the account and
 * travels on the session query. Somebody working in Spanish may perfectly well prepare an
 * instance whose prompts are English, and the app has to be able to say so.
 *
 * `localStorage` is the fallback and not the truth. It exists for the three routes that
 * render before there is a session — login, `/invite`, `/reset` — where there
 * is no account to ask, and it is seeded from `navigator.language` so a browser set to
 * English does not greet somebody in Spanish. The moment the session arrives, `adopt`
 * replaces it with what the account says.
 */

export const LANGUAGES = ["es", "en"] as const;

export type Language = (typeof LANGUAGES)[number];

export const DEFAULT: Language = "es";

/** Each one written in itself: a picker in a language you do not read is not a picker. */
export const LANGUAGE_NAMES: Record<Language, string> = {
  es: "Español",
  en: "English",
};

export const LANGUAGE_KEY = "vg.lang";

const listeners = new Set<() => void>();

/** Folds `es-ES` and `en_US`, which is the shape `navigator.language` actually has. */
export function normalise(value: string | null | undefined): Language | null {
  if (!value) return null;
  const base = String(value).trim().toLowerCase().replace(/_/g, "-").split("-")[0];
  return (LANGUAGES as readonly string[]).includes(base) ? (base as Language) : null;
}

function stored(): Language | null {
  try {
    return normalise(localStorage.getItem(LANGUAGE_KEY));
  } catch {
    return null;
  }
}

function preferred(): Language | null {
  try {
    return normalise(navigator.language);
  } catch {
    return null;
  }
}

let language: Language = stored() ?? preferred() ?? DEFAULT;

// Stamping `<html lang>` is what a screen reader and the browser's own hyphenation read,
// and it is the one thing here that touches the DOM. Guarded because this module is pure
// enough to be tested without one, and a store that cannot be exercised outside a browser
// is a store whose rules are never checked.
function announce() {
  if (typeof document !== "undefined") document.documentElement.lang = language;
  for (const listener of listeners) listener();
}

export const localeStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },

  getSnapshot(): Language {
    return language;
  },

  /**
   * What the account says, written through so the next pre-session render already has it.
   * Called from the session query for the same reason `workspaceStore.adopt` is: it has to
   * land BEFORE the first child renders, and an effect would run child-first and too late.
   */
  adopt(next: string | null | undefined) {
    const resolved = normalise(next);
    if (!resolved || resolved === language) return;
    language = resolved;
    try {
      localStorage.setItem(LANGUAGE_KEY, resolved);
    } catch {
      // A browser with site data blocked still gets the language, just not the memory.
    }
    announce();
  },

  set(next: Language) {
    if (next === language) return;
    language = next;
    try {
      localStorage.setItem(LANGUAGE_KEY, next);
    } catch {
      // As above.
    }
    announce();
  },
};

announce();

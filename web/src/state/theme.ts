/**
 * Light, dark, or whatever the OS says.
 *
 * The stylesheet keys every dark token on `data-theme="dark"` and on nothing else, so
 * this store is the only place that decides what the page looks like: it resolves the
 * preference against `prefers-color-scheme` and stamps the RESULT on <html>. A bootstrap
 * line in `index.html` does the same before React loads, from the same key, so the first
 * paint already has the right ground.
 *
 * `localStorage`, not the account: the theme is a property of the screen someone is
 * sitting at, and the same person reads the app on a bright laptop and a dark desk.
 */

export type ThemePreference = "system" | "light" | "dark";
export type Theme = "light" | "dark";

export const THEME_KEY = "vg.theme";

const media = window.matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function read(): ThemePreference {
  const stored = localStorage.getItem(THEME_KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

let preference: ThemePreference = read();

export function resolve(pref: ThemePreference): Theme {
  return pref === "system" ? (media.matches ? "dark" : "light") : pref;
}

function stamp() {
  document.documentElement.dataset.theme = resolve(preference);
  for (const listener of listeners) listener();
}

media.addEventListener("change", () => {
  if (preference === "system") stamp();
});

export const themeStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },

  getSnapshot(): ThemePreference {
    return preference;
  },

  set(next: ThemePreference) {
    preference = next;
    if (next === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, next);
    stamp();
  },
};

stamp();

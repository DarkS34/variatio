/**
 * Which instance this tab is looking at.
 *
 * The server decides who may enter a workspace; this only decides which one is *asked
 * for*, and it is asked for on every request through the `X-Workspace` header. Keeping it
 * in the tab rather than only on the account is what lets one browser hold two subjects
 * open side by side — the header is per request, so the two tabs never fight over a
 * shared server-side pointer.
 *
 * `sessionStorage`, not `localStorage`: per tab is the whole point, and a new tab should
 * start where the account left off (what `/api/auth/me` reports) rather than where some
 * other tab happens to be.
 */

const KEY = "vg.workspace";

let active: string | null = sessionStorage.getItem(KEY);
const listeners = new Set<() => void>();

export const workspaceStore = {
  subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  },

  getSnapshot() {
    return active;
  },

  /** What the account says its workspace is, used only when this tab has no opinion. */
  adopt(slug: string | null) {
    if (active !== null || !slug) return;
    active = slug;
    sessionStorage.setItem(KEY, slug);
    for (const listener of listeners) listener();
  },

  set(slug: string | null) {
    if (active === slug) return;
    active = slug;
    if (slug) sessionStorage.setItem(KEY, slug);
    else sessionStorage.removeItem(KEY);
    for (const listener of listeners) listener();
  },
};

/** The header every request carries. Absent until the tab knows, which the server reads
 *  as "use the account's own workspace" — the right answer for the very first request. */
export function workspaceHeader(): Record<string, string> {
  return active ? { "X-Workspace": active } : {};
}

export function activeWorkspace(): string | null {
  return active;
}

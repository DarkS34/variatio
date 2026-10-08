/**
 * Whether the guide and the tutorial are reachable at all.
 *
 * Hidden at the user's decision (2026-10-07): no entry in the account menu, no «Leer en la
 * guía» under a title, and `/guide`, `/guide/*`, `/tutorial` and `/tutorial/*` draw «not
 * found» before anything else, so their chunks are never fetched. Both are screens of the
 * client — the server has no route of either — so this one flag closes them. Their code and
 * copy stay: they speak of four steps and are not updated while hidden.
 */
export const HELP_HIDDEN = true;

/** Whether a path is one of the guide's or the tutorial's. */
export function isHelpPath(path: string): boolean {
  return (
    path === "/guide" ||
    path.startsWith("/guide/") ||
    path === "/tutorial" ||
    path.startsWith("/tutorial/")
  );
}

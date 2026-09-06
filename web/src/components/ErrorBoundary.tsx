import { Component, type ReactNode } from "react";

/**
 * The floor under every render error.
 *
 * Without it an uncaught exception unmounts the whole tree and the person sees a white
 * page with nothing to act on — which is exactly how the concurrent-user bug presented.
 * This does not fix any crash; it turns the next one into a sentence and a button, and
 * prints the message so a report can say more than "se quedó en blanco".
 *
 * A class because React only hands errors to class boundaries; the copy is hardcoded
 * Spanish on purpose — if the crash came from the i18n layer itself, a translated
 * boundary would crash with it.
 */
interface State {
  error: Error | null;
}

/**
 * A DEPLOY IS NOT A CRASH, and this is the one error that must not be reported as one.
 *
 * Every screen but the panel is a dynamic import, and Vite names each chunk by the hash of
 * its contents — so a build replaces the whole set and deletes the previous one. A tab left
 * open across that deploy is still running the old document, which names chunks the server
 * no longer has: the moment somebody navigates to a lazy route, the import rejects with
 * "Failed to fetch dynamically imported module" and the boundary catches it. Nothing is
 * broken; the page is simply out of date, and the fix is the reload the person was about to
 * be asked to perform.
 *
 * So it reloads itself, ONCE. The guard is `sessionStorage` and it is not optional: if the
 * chunk is missing for any other reason — a bad deploy, a proxy serving a truncated file —
 * an unguarded reload is an infinite loop that never shows the message explaining why. The
 * flag is cleared on the next successful render, so a second genuine deploy is handled the
 * same way an hour later.
 */
const RELOADED = "vg.chunk-reloaded";

function isStaleChunk(error: Error): boolean {
  const text = `${error.name} ${error.message}`;
  return (
    /dynamically imported module/i.test(text) ||
    /Importing a module script failed/i.test(text) ||
    /ChunkLoadError/i.test(text)
  );
}

function reloadOnce(): boolean {
  try {
    if (sessionStorage.getItem(RELOADED)) return false;
    sessionStorage.setItem(RELOADED, "1");
  } catch {
    // A browser with site data blocked cannot hold the guard, so it does not get the
    // automatic reload either: an unguarded one would loop.
    return false;
  }
  window.location.reload();
  return true;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidMount() {
    try {
      sessionStorage.removeItem(RELOADED);
    } catch {
      // Nothing to clear, and nothing that depends on it.
    }
  }

  componentDidCatch(error: Error) {
    if (isStaleChunk(error)) reloadOnce();
  }

  render() {
    if (this.state.error === null) return this.props.children;
    return (
      <div className="flex min-h-full items-center justify-center p-6">
        <div className="w-full max-w-md space-y-4 border border-border bg-card p-6">
          <h1 className="font-display font-expanded text-title">Algo ha fallado</h1>
          <p className="text-body text-muted-foreground">
            {isStaleChunk(this.state.error)
              ? "Esta pestaña llevaba abierta desde antes de la última actualización y ya no encuentra parte de la aplicación. Recarga para traer la versión nueva."
              : "La pantalla no se pudo dibujar. Recargar suele bastar; si vuelve a pasar, copia el detalle de abajo al informarlo."}
          </p>
          <p className="break-all font-mono text-small text-destructive">
            {this.state.error.message || String(this.state.error)}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="w-full bg-primary px-4 py-2 text-body font-medium text-primary-foreground transition-colors hover:opacity-90"
          >
            Recargar la página
          </button>
        </div>
      </div>
    );
  }
}

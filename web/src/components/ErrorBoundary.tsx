import { Component, type ReactNode } from "react";

/**
 * The floor under every render error.
 *
 * Without it an uncaught exception unmounts the whole tree and the person sees a white
 * page with nothing to act on — which is exactly how the concurrent-user bug presented.
 * This does not fix any crash; it turns the next one into a sentence and a button, and
 * prints the message so a report can say more than «se quedó en blanco».
 *
 * A class because React only hands errors to class boundaries; the copy is hardcoded
 * Spanish on purpose — if the crash came from the i18n layer itself, a translated
 * boundary would crash with it.
 */
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error === null) return this.props.children;
    return (
      <div className="flex min-h-full items-center justify-center p-6">
        <div className="w-full max-w-md space-y-4 border border-border bg-card p-6">
          <h1 className="font-display font-expanded text-title">Algo ha fallado</h1>
          <p className="text-body text-muted-foreground">
            La pantalla no se pudo dibujar. Recargar suele bastar; si vuelve a pasar,
            copia el detalle de abajo al informarlo.
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

import { RefreshCw, Wrench } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Logo } from "@/components/ui/logo";
import type { MaintenanceState } from "@/lib/types";
import { LoginScreen } from "@/features/auth/LoginScreen";

/**
 * What the installation looks like from outside while somebody is working on it.
 *
 * It replaces the whole application rather than sitting on top of it, and it is the one
 * screen in the app that renders with no session, no workspace and no socket. Two things
 * it deliberately does:
 *
 * It says WHEN it closed, not when it will open. This project refuses time estimates for
 * a build for a measured reason, and the same argument applies here with less evidence
 * still: whoever threw the switch does not know either.
 *
 * It keeps a way in for whoever administers the installation. The gate lets an
 * administrator through, so the notice offers them the login form instead of leaving the
 * only door behind a URL they have to remember.
 */
export function MaintenanceScreen({
  state,
  onRetry,
  canLogIn,
}: {
  state: MaintenanceState;
  onRetry: () => void;
  /** Only when there is no session at all: with one, the way in is not a login form. */
  canLogIn: boolean;
}) {
  const [login, setLogin] = useState(false);
  const elapsed = useElapsed(state.since);

  if (login) return <LoginScreen />;

  return (
    <div className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        <div className="mb-6 flex items-center gap-2 font-semibold">
          <Logo className="size-5 text-primary" />
          Variatio
        </div>

        <Card className="p-6 sm:p-8">
          <div className="flex items-center gap-3">
            {/* The pulse is the one motion `prefers-reduced-motion` keeps, and for the
                same reason it keeps it on a build: it is what says this is a state
                somebody is holding, not a page that failed to load. */}
            <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-[color-mix(in_oklch,var(--attention)_14%,transparent)] text-attention">
              <Wrench className="size-4 animate-pulse-soft" />
            </span>
            <h1 className="font-display font-expanded text-title sm:text-display">
              En mantenimiento
            </h1>
          </div>

          <p className="mt-5 text-body text-foreground">{state.message}</p>

          <p className="mt-2 text-small text-muted-foreground">
            {elapsed
              ? `Cerrada desde hace ${elapsed}. No hay una hora prevista de vuelta: nada se ha perdido, lo construido sigue donde estaba.`
              : "Nada se ha perdido: lo construido sigue donde estaba y volverá tal cual."}
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={onRetry}>
              <RefreshCw />
              Comprobar de nuevo
            </Button>
            {canLogIn ? (
              <Button variant="ghost" onClick={() => setLogin(true)}>
                Entrar como administración
              </Button>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  );
}

/** How long it has been closed, recomputed every half minute so a screen left open does
 *  not keep reporting the number it had when it loaded. */
function useElapsed(since: string | null): string | null {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);

  if (!since) return null;
  const started = new Date(since).getTime();
  if (Number.isNaN(started)) return null;

  const minutes = Math.max(0, Math.round((now - started) / 60_000));
  if (minutes < 1) return "menos de un minuto";
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ${(minutes % 60).toString().padStart(2, "0")} min`;
  const days = Math.floor(hours / 24);
  return `${days} día${days === 1 ? "" : "s"}`;
}

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { useRouter } from "@/lib/router";
import { authKeys, useIsUnauthenticated, useLogout, useSession } from "@/state/auth";
import { useStream } from "@/state/queries";

import { AcceptInvite } from "./AcceptInvite";
import { AuthLayout } from "./AuthLayout";
import { LoginScreen } from "./LoginScreen";
import { ResetPassword } from "./ResetPassword";

/**
 * Nothing else in the app renders until this has an answer.
 *
 * Keeping the gate outside `App` rather than inside each screen is what makes "logged
 * out" a single state instead of one 401 per panel: no query fires, the WebSocket is
 * never opened, and the screens keep assuming there is a session, which is true whenever
 * they exist.
 *
 * Two routes are public because they are the ones you reach *without* an account: the
 * invitation link and the password-reset link.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const { path } = useRouter();
  const token = new URLSearchParams(window.location.search).get("token") ?? "";

  if (path === "/invitacion") {
    return token ? <AcceptInvite token={token} /> : <MissingToken kind="invitación" />;
  }
  if (path === "/restablecer") {
    return token ? <ResetPassword token={token} /> : <MissingToken kind="enlace" />;
  }

  return <Guarded>{children}</Guarded>;
}

function Guarded({ children }: { children: ReactNode }) {
  const session = useSession();
  const unauthenticated = useIsUnauthenticated(session);
  const client = useQueryClient();
  const stream = useStream();

  // The socket is the other half of the session: when the server closes it with 4401 the
  // cookie is gone or revoked, and the cached `me` is a lie until it is re-asked.
  useEffect(() => {
    if (stream.unauthorised) client.invalidateQueries({ queryKey: authKeys.me });
  }, [stream.unauthorised, client]);

  if (session.isLoading) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <Spinner className="size-6 text-muted-foreground" />
      </div>
    );
  }

  if (unauthenticated) return <LoginScreen />;

  if (session.isError) {
    return (
      <AuthLayout title="El servidor no responde">
        <p className="text-sm text-muted-foreground">
          {session.error instanceof Error ? session.error.message : "Error desconocido"}
        </p>
        <Button className="mt-4 w-full" onClick={() => session.refetch()}>
          Reintentar
        </Button>
      </AuthLayout>
    );
  }

  // Authenticated, but with no membership on the workspace this server is serving. It is
  // a real state — an account can exist before anyone grants it access — and it is not
  // the same as being logged out, so it does not send them back to the login form.
  if (session.data && session.data.role === null) return <NoAccess />;

  return <>{children}</>;
}

function NoAccess() {
  const session = useSession();
  const logout = useLogout();
  return (
    <AuthLayout
      title="Todavía no tienes acceso"
      description="Tu cuenta existe, pero nadie te ha dado permiso sobre esta instancia."
    >
      <p className="text-sm text-muted-foreground">
        Pídeselo a quien la administra. Entraste como{" "}
        <span className="font-medium text-foreground">{session.data?.user.email}</span>.
      </p>
      <Button variant="outline" className="mt-4 w-full" onClick={() => logout.mutate()}>
        Salir
      </Button>
    </AuthLayout>
  );
}

function MissingToken({ kind }: { kind: string }) {
  return (
    <AuthLayout
      title={`Falta el código de la ${kind}`}
      description="Abre el enlace completo tal y como lo recibiste."
      footer={
        <a href="/" className="text-muted-foreground hover:underline">
          Ir a la pantalla de entrada
        </a>
      }
    >
      <Button className="w-full" onClick={() => window.location.assign("/")}>
        Entrar
      </Button>
    </AuthLayout>
  );
}

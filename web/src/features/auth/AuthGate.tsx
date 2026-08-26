import { useQueryClient } from "@tanstack/react-query";
import { useEffect, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { useRouter } from "@/lib/router";
import { authKeys, useIsUnauthenticated, useSession } from "@/state/auth";
import { useMaintenance, useStream } from "@/state/queries";
import { MaintenanceScreen } from "@/features/maintenance/MaintenanceScreen";

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
  const maintenance = useMaintenance();
  const client = useQueryClient();
  const stream = useStream();

  // The socket is the other half of the session: when the server closes it with 4401 the
  // cookie is gone or revoked, and the cached `me` is a lie until it is re-asked.
  useEffect(() => {
    if (stream.unauthorised) client.invalidateQueries({ queryKey: authKeys.me });
  }, [stream.unauthorised, client]);

  if (session.isLoading || maintenance.isLoading) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <Spinner className="size-6 text-muted-foreground" />
      </div>
    );
  }

  // The door, and it is asked BEFORE the session is: a closed installation is a closed
  // installation whether or not the person looking at it has an account. The one
  // exception is the account that administers it, because the server lets that one
  // through and a notice it could not get past would leave nothing to reopen from. A
  // maintenance query that FAILED is not a closed door — `data` is undefined and the app
  // renders — because a server that is not answering says something else entirely, and
  // the screens behind this already know how to say it.
  if (maintenance.data?.active && !session.data?.user.is_admin) {
    return (
      <MaintenanceScreen
        state={maintenance.data}
        onRetry={() => {
          maintenance.refetch();
          session.refetch();
        }}
        canLogIn={unauthenticated}
      />
    );
  }

  if (unauthenticated) return <LoginScreen />;

  if (session.isError) {
    return (
      <AuthLayout title="El servidor no responde">
        <p className="text-body text-muted-foreground">
          {session.error instanceof Error ? session.error.message : "Error desconocido"}
        </p>
        <Button className="mt-4 w-full" onClick={() => session.refetch()}>
          Reintentar
        </Button>
      </AuthLayout>
    );
  }

  // Authenticated but a member of nothing at all used to be stopped here, with a
  // full-page notice outside the shell. It is not a question about the session, so it
  // stopped being the gate's: `App` renders the offer to create one in the middle of the
  // panel, and the guide, the account and the administration panel — none of which needs
  // an instance — stay reachable while there is no workspace.
  return <>{children}</>;
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

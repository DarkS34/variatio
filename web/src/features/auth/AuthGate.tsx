import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

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
import { useT, type Key } from "@/lib/i18n";

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
  // Read ONCE, into state. The two screens behind this strip the token out of the address
  // bar as soon as they have it — a secret does not belong in the history, the referrer or
  // a shared screenshot — and re-reading `location.search` on every render would find it
  // gone and greet the person with "the code is missing" halfway through their own form.
  const [token] = useState(() => new URLSearchParams(window.location.search).get("token") ?? "");

  if (path === "/invite") {
    return token ? <AcceptInvite token={token} /> : <MissingToken kind="auth.kindInvite" />;
  }
  if (path === "/reset") {
    return token ? <ResetPassword token={token} /> : <MissingToken kind="auth.kindLink" />;
  }

  return <Guarded>{children}</Guarded>;
}

function Guarded({ children }: { children: ReactNode }) {
  const { t } = useT();
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
      <AuthLayout title={t("auth.serverDown")}>
        <p className="text-body text-muted-foreground">
          {session.error instanceof Error ? session.error.message : t("auth.unknownError")}
        </p>
        <Button className="mt-4 w-full" onClick={() => session.refetch()}>
          {t("common.retry")}
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

function MissingToken({ kind }: { kind: Key }) {
  const { t } = useT();
  return (
    <AuthLayout
      title={t("auth.missingCode", { kind: t(kind) })}
      description={t("auth.missingCodeBody")}
      footer={
        <a href="/" className="text-muted-foreground hover:underline">
          {t("auth.backToLogin")}
        </a>
      }
    >
      <Button className="w-full" onClick={() => window.location.assign("/")}>
        {t("common.enter")}
      </Button>
    </AuthLayout>
  );
}

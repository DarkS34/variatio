import { useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { ApiError, api } from "@/lib/api";
import { useRouter } from "@/lib/router";
import { authKeys, useIsUnauthenticated, useSession } from "@/state/auth";
import { leaveLostWorkspace, useMaintenance, useStream } from "@/state/queries";
import { MaintenanceScreen } from "@/features/maintenance/MaintenanceScreen";

import { AcceptInvite } from "./AcceptInvite";
import { AuthLayout } from "./AuthLayout";
import { LoginScreen } from "./LoginScreen";
import { ResetPassword } from "./ResetPassword";
import { useT, withCatalogues, type Key } from "@/lib/i18n";

// The landing is public and is its own module, fetched only by a visitor: its demo draws
// the real screens over an in-memory server, which is most of the client.
const LandingScreen = lazy(() =>
  withCatalogues(import("@/landing/LandingScreen")).then((m) => ({ default: m.LandingScreen })),
);

const DemoPage = lazy(() =>
  withCatalogues(import("@/landing/DemoPage")).then((m) => ({ default: m.DemoPage })),
);

/** Where the login form is reached from the landing, since `/` is the landing for a visitor. */
export const LOGIN_PATH = "/login";

/** The landing's demo: the application over an in-memory server, public, on a page of its own. */
export const DEMO_PATH = "/demo";

/**
 * Nothing else in the app renders until this has an answer.
 *
 * Keeping the gate outside `App` rather than inside each screen is what makes "logged
 * out" a single state instead of one 401 per panel: no query fires, the WebSocket is
 * never opened, and the screens keep assuming there is a session, which is true whenever
 * they exist.
 *
 * Two routes are public because they are the ones you reach *without* an account: the
 * invitation link and the password-reset link. `/demo` is public too, and answered before
 * the session is asked for: while it is on screen the demo answers every request of the
 * client, and no live query of the page may meet it. And `/` is the landing for whoever
 * has no session (`Front`).
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
  if (path === DEMO_PATH) {
    return (
      <Suspense fallback={<Waiting />}>
        <DemoPage />
      </Suspense>
    );
  }

  return (
    <Front>
      <Guarded>{children}</Guarded>
    </Front>
  );
}

/**
 * `/` is the landing for a visitor and the application for an account.
 *
 * Decided by ONE reading of the session and of the door, taken before anything else mounts
 * and never kept live. That is the point: while the landing is on screen its demo answers
 * every request of the client (`lib/api.setTransport`), and a live session query out here
 * would be answered by it — the visitor would find themselves logged in as the demo's
 * teacher. A closed installation is still a closed one (`Guarded` draws the door), and an
 * account the cache already knows skips the reading, so the bar's own link to `/` never
 * remounts the application.
 */
function Front({ children }: { children: ReactNode }) {
  const { path } = useRouter();
  const client = useQueryClient();
  const asks = path === "/" && client.getQueryData(authKeys.me) === undefined;
  const [visitor, setVisitor] = useState<boolean | null>(null);

  useEffect(() => {
    if (!asks) {
      setVisitor(null);
      return;
    }
    let live = true;
    void Promise.allSettled([api.me(), api.maintenance()]).then(([session, door]) => {
      if (!live) return;
      const refused =
        session.status === "rejected" &&
        session.reason instanceof ApiError &&
        session.reason.status === 401;
      const closed = door.status === "fulfilled" && door.value.active;
      setVisitor(refused && !closed);
    });
    return () => {
      live = false;
    };
  }, [asks]);

  if (!asks || visitor === false) return <>{children}</>;
  if (visitor === null) return <Waiting />;
  return (
    <Suspense fallback={<Waiting />}>
      <LandingScreen />
    </Suspense>
  );
}

function Waiting() {
  return (
    <div className="flex min-h-full items-center justify-center">
      <Spinner className="size-6 text-muted-foreground" />
    </div>
  );
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

  // Closed with 4403: a teacher removed or paused this account in the subject on screen.
  useEffect(() => {
    if (stream.lost) leaveLostWorkspace(client);
  }, [stream.lost, client]);

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

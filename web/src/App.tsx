import { lazy, Suspense, useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { Link, useRouter } from "@/lib/router";
import { Dashboard } from "@/features/pipeline/Dashboard";
import { NoWorkspace } from "@/features/workspaces/NoWorkspace";
import { useHasWorkspace } from "@/state/auth";
import { usePipeline } from "@/state/queries";
import { useT } from "@/lib/i18n";

// Every screen except the panel loads on demand: the router is ours, so the split
// happens here rather than in a route table. The panel stays static because «/» is
// where a session lands, and a fallback flash on the landing route helps nobody.
const AccountScreen = lazy(() =>
  import("@/features/account/AccountScreen").then((m) => ({ default: m.AccountScreen })),
);
const AdminScreen = lazy(() =>
  import("@/features/admin/AdminScreen").then((m) => ({ default: m.AdminScreen })),
);
const BankScreen = lazy(() =>
  import("@/features/bank/BankScreen").then((m) => ({ default: m.BankScreen })),
);
const GuideScreen = lazy(() =>
  import("@/features/guide/GuideScreen").then((m) => ({ default: m.GuideScreen })),
);
const EvaluationScreen = lazy(() =>
  import("@/study/EvaluationScreen").then((m) => ({ default: m.EvaluationScreen })),
);
const KgScreen = lazy(() =>
  import("@/features/kg/KgScreen").then((m) => ({ default: m.KgScreen })),
);
const ProfileScreen = lazy(() =>
  import("@/features/profile/ProfileEditor").then((m) => ({ default: m.ProfileScreen })),
);
const GenerateScreen = lazy(() =>
  import("@/features/run/GenerateScreen").then((m) => ({ default: m.GenerateScreen })),
);
const RawScreen = lazy(() =>
  import("@/features/raw/RawScreen").then((m) => ({ default: m.RawScreen })),
);

// Which destinations need an instance to mean anything. Everything not listed here is
// about the person or the installation and works with no workspace at all: the guide is
// reading, «Mi perfil» is the account, and administration is where an administrator hands
// out access in the first place — locking them behind a workspace would leave the state
// with no way out of itself.
const NEEDS_WORKSPACE = [
  "/",
  "/raw",
  "/prepare/profile",
  "/prepare/graph",
  "/prepare/bank",
  "/generate",
  "/evaluate",
];

export function App() {
  const { t } = useT();
  const { path } = useRouter();
  const pipeline = usePipeline();
  const hasWorkspace = useHasWorkspace();
  const stage = (artifact: string) => pipeline.data?.stages.find((s) => s.artifact === artifact);

  const screen = () => {
    if (path === "/guide" || path.startsWith("/guide/")) {
      return <GuideScreen slug={path.slice("/guide/".length)} />;
    }

    // One message rather than six 403s. It is drawn as the panel whatever the route was,
    // because the panel is where the one thing to do here lives.
    if (!hasWorkspace && NEEDS_WORKSPACE.includes(path)) return <NoWorkspace />;

    switch (path) {
      case "/":
        return <Dashboard />;
      // The raw material is not a stage — it writes no artifact and nobody approves it —
      // so it is a destination of its own rather than a fourth `/prepare/…`.
      case "/raw":
        return <RawScreen />;
      case "/prepare/profile":
        return <ProfileScreen stage={stage("exemplars_profile")} />;
      case "/prepare/graph":
        return <KgScreen stage={stage("knowledge_graph")} />;
      case "/prepare/bank":
        return <BankScreen stage={stage("exemplars_bank")} />;
      case "/generate":
        return <GenerateScreen />;
      case "/evaluate":
        return <EvaluationScreen />;
      // The account of whoever is looking: their data, their variants and their accesses. Each
      // tab is a route so that «mis variantes» stays a link that can be bookmarked.
      case "/account":
        return <AccountScreen tab="cuenta" />;
      case "/account/variants":
        return <AccountScreen tab="variantes" />;
      case "/account/access":
        return <AccountScreen tab="accesos" />;
      // Where the variants lived when they were a screen of their own. Redirected rather than
      // duplicating the screen: old links still lead to where they are now.
      case "/variants":
        return <Redirect to="/account/variants" />;
      // Guarded on the server by `require_admin`; the route exists for everyone because
      // hiding it in the client is not a permission, and the panel says so itself if a
      // non-administrator reaches it by typing the URL.
      case "/admin":
        return <AdminScreen />;
      default:
        return (
          <EmptyState title={t("route.notFound")}>
            <Link to="/" className="text-primary underline-offset-4 hover:underline">
              {t("route.backToPanel")}
            </Link>
          </EmptyState>
        );
    }
  };

  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="flex justify-center py-16">
            <Spinner className="size-5 text-muted-foreground" />
          </div>
        }
      >
        {screen()}
      </Suspense>
    </AppShell>
  );
}

function Redirect({ to }: { to: string }) {
  const { navigate } = useRouter();
  useEffect(() => navigate(to, { replace: true }), [navigate, to]);
  return null;
}

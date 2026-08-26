import { lazy, Suspense, useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { Link, useRouter } from "@/lib/router";
import { Dashboard } from "@/features/pipeline/Dashboard";
import { usePipeline } from "@/state/queries";

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

export function App() {
  const { path } = useRouter();
  const pipeline = usePipeline();
  const stage = (artifact: string) => pipeline.data?.stages.find((s) => s.artifact === artifact);

  const screen = () => {
    if (path === "/guia" || path.startsWith("/guia/")) {
      return <GuideScreen slug={path.slice("/guia/".length)} />;
    }

    switch (path) {
      case "/":
        return <Dashboard />;
      case "/preparar/perfil":
        return <ProfileScreen stage={stage("exemplars_profile")} />;
      case "/preparar/grafo":
        return <KgScreen stage={stage("knowledge_graph")} />;
      case "/preparar/banco":
        return <BankScreen stage={stage("exemplars_bank")} />;
      case "/generar":
        return <GenerateScreen />;
      case "/evaluar":
        return <EvaluationScreen />;
      // The account of whoever is looking: their data, their variants and their accesses. Each
      // tab is a route so that «mis variantes» stays a link that can be bookmarked.
      case "/perfil":
        return <AccountScreen tab="cuenta" />;
      case "/perfil/variantes":
        return <AccountScreen tab="variantes" />;
      case "/perfil/accesos":
        return <AccountScreen tab="accesos" />;
      // Where the variants lived when they were a screen of their own. Redirected rather than
      // duplicating the screen: old links still lead to where they are now.
      case "/variantes":
        return <Redirect to="/perfil/variantes" />;
      // Guarded on the server by `require_admin`; the route exists for everyone because
      // hiding it in the client is not a permission, and the panel says so itself if a
      // non-administrator reaches it by typing the URL.
      case "/administracion":
        return <AdminScreen />;
      default:
        return (
          <EmptyState title="Esa página no existe">
            <Link to="/" className="text-primary underline-offset-4 hover:underline">
              Volver al panel
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

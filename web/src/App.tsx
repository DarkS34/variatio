import { useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/ui/misc";
import { Link, useRouter } from "@/lib/router";
import { AccountScreen } from "@/features/account/AccountScreen";
import { AdminScreen } from "@/features/admin/AdminScreen";
import { BankScreen } from "@/features/bank/BankScreen";
import { Dashboard } from "@/features/pipeline/Dashboard";
import { EvaluationScreen } from "@/study/EvaluationScreen";
import { KgScreen } from "@/features/kg/KgScreen";
import { ProfileScreen } from "@/features/profile/ProfileEditor";
import { GenerateScreen } from "@/features/run/GenerateScreen";
import { usePipeline } from "@/state/queries";

export function App() {
  const { path } = useRouter();
  const pipeline = usePipeline();
  const stage = (artifact: string) => pipeline.data?.stages.find((s) => s.artifact === artifact);

  const screen = () => {
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

  return <AppShell>{screen()}</AppShell>;
}

function Redirect({ to }: { to: string }) {
  const { navigate } = useRouter();
  useEffect(() => navigate(to, { replace: true }), [navigate, to]);
  return null;
}

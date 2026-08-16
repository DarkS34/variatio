import { AppShell } from "@/components/AppShell";
import { EmptyState } from "@/components/ui/misc";
import { Link, useRouter } from "@/lib/router";
import { AdminScreen } from "@/features/admin/AdminScreen";
import { BankScreen } from "@/features/bank/BankScreen";
import { Dashboard } from "@/features/pipeline/Dashboard";
import { EvaluationScreen } from "@/features/evaluation/EvaluationScreen";
import { GenerationsScreen } from "@/features/generations/GenerationsScreen";
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
      case "/variantes":
        return <GenerationsScreen />;
      case "/evaluar":
        return <EvaluationScreen />;
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

import { lazy, Suspense, useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { Link, useRouter } from "@/lib/router";
import { NoWorkspace } from "@/features/workspaces/NoWorkspace";
import { useHasWorkspace } from "@/state/auth";
import { currentStepPath } from "@/lib/steps";
import { usePipeline, useRaw } from "@/state/queries";
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
const TutorialScreen = lazy(() =>
  import("@/features/tutorial/TutorialScreen").then((m) => ({ default: m.TutorialScreen })),
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
      // «/» YA NO ES UNA PANTALLA, ES UNA RESPUESTA. El panel era la vista de la cadena
      // desde fuera, y desde que la barra ES la cadena no queda nada que mirar desde
      // fuera; lo que sí queda es la única pregunta que tiene quien entra — «¿y ahora
      // qué?» —, que esto contesta llevándote allí. Con la cadena entera aprobada lleva
      // a «Crear ejercicios», que es para lo que servía todo lo anterior.
      case "/":
        return <Landing />;
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
      // The account of whoever is looking: their data, the instances they can open and their
      // variants. Each tab is a route so that «mis variantes» stays a link that can be
      // bookmarked.
      case "/account":
        return <AccountScreen tab="cuenta" />;
      case "/account/workspaces":
        return <AccountScreen tab="workspaces" />;
      case "/account/variants":
        return <AccountScreen tab="variantes" />;
      // Where the accesses lived while the tab was called «Accesos».
      case "/account/access":
        return <Redirect to="/account/workspaces" />;
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

  // EL TUTORIAL VA FUERA DEL SHELL, como las pantallas de entrada. Lleva su propia
  // cabecera — la marca y «saltar» — y dentro del shell salían dos: la barra del recorrido
  // encima de una explicación de qué es el recorrido. Tampoco necesita instancia: explica,
  // entre otras cosas, cómo llegar a tener una.
  if (path === "/tutorial") {
    return (
      <Suspense
        fallback={
          <div className="flex justify-center py-16">
            <Spinner className="size-5 text-muted-foreground" />
          </div>
        }
      >
        <TutorialScreen />
      </Suspense>
    );
  }

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


/**
 * Where a session lands: the step that is next.
 *
 * It waits for both readings before deciding — `currentStepPath` over an empty pipeline
 * answers «step 1» for every workspace in existence, and redirecting there and then
 * bouncing away is worse than a second of nothing.
 */
function Landing() {
  const { navigate } = useRouter();
  const pipeline = usePipeline();
  const raw = useRaw();
  const slots = raw.data?.slots ?? [];
  const ready = pipeline.data !== undefined && raw.data !== undefined;

  useEffect(() => {
    if (!ready) return;
    const stocked = slots.length > 0 && slots.every((slot) => slot.files.length > 0);
    navigate(currentStepPath(pipeline.data!.stages, stocked), { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  return (
    <div className="flex justify-center py-16">
      <Spinner className="size-5 text-muted-foreground" />
    </div>
  );
}

import { lazy, Suspense, useEffect } from "react";

import { AppShell } from "@/components/AppShell";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { Link, useRouter } from "@/lib/router";
import { NoWorkspace } from "@/features/workspaces/NoWorkspace";
import { slideCount, slideOf } from "@/features/tutorial/slides";
import { useFeatures, useHasWorkspace } from "@/state/auth";
import { currentStepPath } from "@/lib/steps";
import type { Features } from "@/lib/types";
import { usePipeline, useRaw } from "@/state/queries";
import { useT, withCatalogues } from "@/lib/i18n";

// Every screen except the panel loads on demand: the router is ours, so the split
// happens here rather than in a route table. The panel stays static because "/" is
// where a session lands, and a fallback flash on the landing route helps nobody.
// The evaluation's and the tutor's screens are more than a split: they are only ever
// imported for an account the function is open to (`pnpm check:lazy`).
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
  withCatalogues(import("@/evaluation/EvaluationScreen")).then((m) => ({
    default: m.EvaluationScreen,
  })),
);
const KgScreen = lazy(() =>
  import("@/features/kg/KgScreen").then((m) => ({ default: m.KgScreen })),
);
const ProfileScreen = lazy(() =>
  import("@/features/profile/ProfileEditor").then((m) => ({ default: m.ProfileScreen })),
);
const GenerateScreen = lazy(() =>
  import("@/features/generate/GenerateScreen").then((m) => ({ default: m.GenerateScreen })),
);
const RawScreen = lazy(() =>
  import("@/features/raw/RawScreen").then((m) => ({ default: m.RawScreen })),
);
const TutorScreen = lazy(() =>
  withCatalogues(import("@/tutor/TutorScreen")).then((m) => ({ default: m.TutorScreen })),
);
const TutorialScreen = lazy(() =>
  import("@/features/tutorial/TutorialScreen").then((m) => ({ default: m.TutorialScreen })),
);

// Which destinations need an instance to mean anything. Everything not listed here is
// about the person or the installation and works with no workspace at all: the guide is
// reading, "Mi perfil" is the account, and administration is where an administrator hands
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
  "/tutor",
];

// The destinations that are an optional function's. Closed to the account, one is not a
// destination at all: the same "not found" as any route that does not exist, answered
// before anything asks whether there is a workspace for it, and its code is never fetched.
const FEATURE_OF: Partial<Record<string, keyof Features>> = {
  "/evaluate": "evaluation",
  "/tutor": "tutor",
};

export function App() {
  const { path } = useRouter();
  const pipeline = usePipeline();
  const hasWorkspace = useHasWorkspace();
  const features = useFeatures();
  const stage = (artifact: string) => pipeline.data?.stages.find((s) => s.artifact === artifact);

  const screen = () => {
    // The tutorial runs inside the shell, and the shell reads its slide from the PATH,
    // which is why there is one route per slide. `AppShell` reads it with the same count.
    const slide = slideOf(path, slideCount(features));
    if (slide !== null) return <TutorialScreen at={slide} />;

    if (path === "/guide" || path.startsWith("/guide/")) {
      return <GuideScreen slug={path.slice("/guide/".length)} />;
    }

    const feature = FEATURE_OF[path];
    if (feature && !features[feature]) return <NotFound />;

    // One message rather than six 403s. It is drawn as the panel whatever the route was,
    // because the panel is where the one thing to do here lives.
    if (!hasWorkspace && NEEDS_WORKSPACE.includes(path)) return <NoWorkspace />;

    switch (path) {
      // "/" is not a screen but an ANSWER. The bar IS the chain, so there is nothing left
      // to watch from outside it; what is left is the only question somebody entering has —
      // "and now what?" — which this answers by taking them there. With the whole chain
      // approved it lands on generating, which is what everything before it was for.
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
      // Reached only with the function open to the account (`FEATURE_OF`).
      case "/evaluate":
        return <EvaluationScreen />;
      case "/tutor":
        return <TutorScreen />;
      // The account of whoever is looking: their data, and the subjects they can open with
      // the exercises they generated in each. Each tab is a route so that it stays a link
      // that can be bookmarked.
      case "/account":
        return <AccountScreen tab="cuenta" />;
      case "/account/workspaces":
        return <AccountScreen tab="workspaces" />;
      // Where the exercises lived while they had a tab of their own; each subject now
      // carries its own.
      case "/account/variants":
        return <Redirect to="/account/workspaces" />;
      // Where the accesses lived while the tab was called "Accesos".
      case "/account/access":
        return <Redirect to="/account/workspaces" />;
      // Where the variants lived when they were a screen of their own. Redirected rather than
      // duplicating the screen: old links still lead to where they are now.
      case "/variants":
        return <Redirect to="/account/workspaces" />;
      // Guarded on the server by `require_admin`; the route exists for everyone because
      // hiding it in the client is not a permission, and the panel says so itself if a
      // non-administrator reaches it by typing the URL.
      case "/admin":
        return <AdminScreen />;
      default:
        return <NotFound />;
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

/** What a path with no screen behind it draws, for this account. */
function NotFound() {
  const { t } = useT();
  return (
    <EmptyState title={t("route.notFound")}>
      <Link to="/" className="text-primary underline-offset-4 hover:underline">
        {t("route.backToPanel")}
      </Link>
    </EmptyState>
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
 * answers "step 1" for every workspace in existence, and redirecting there and then
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

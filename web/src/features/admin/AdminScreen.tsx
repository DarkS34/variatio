import { ShieldCheck } from "lucide-react";
import { lazy, Suspense, useRef, useState, type ReactNode } from "react";

import { GuideLink } from "@/components/GuideLink";
import { InfoHint } from "@/components/ui/hint";
import { EmptyState, LoadError, Skeleton } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import type { AdminOverview, FeatureName } from "@/lib/types";
import { useSession } from "@/state/auth";
import { useAdminOverview } from "@/state/queries";

import type { EvaluationFilters } from "@/evaluation/types";

import { AccountsTab } from "./AccountsTab";
import { StatTile } from "./charts";
import { ConfigTab, StageSettings, useStagesDraft, type StagesDraft } from "./ConfigTab";
import { EngineTab } from "./EngineTab";
import { FeatureAccess, useAccessDrafts, type AccessDrafts } from "./FeatureAccess";
import { MaintenanceSwitch } from "./MaintenanceSwitch";
import { CONFIG_STAGES, stageOfFeature } from "./stages";
import { WorkspacesTab } from "./WorkspacesTab";
import { useT, withCatalogues } from "@/lib/i18n";
import { jobName } from "@/lib/names";

// The evaluation's reading is the evaluation's code, fetched when its tab is opened. The
// administrator reads it whatever the evaluation's mode: its routes are not behind it.
const EvaluationTab = lazy(() =>
  withCatalogues(import("@/evaluation/AdminEvaluationTab")).then((m) => ({
    default: m.EvaluationTab,
  })),
);

/**
 * The installation seen from outside: six tabs, one per thing an administrator runs.
 *
 * "Motor" is the machine and the process — the GPU, the tunnel, the models on disk, the
 * queue; "Configuración" is every value the registry exposes for the product's stages;
 * "Cuentas" decides who exists and where they get in; "Asignaturas" lists the instances and
 * what they weigh. Then, ruled off and each in its own colour like its door in the bar, one
 * tab per optional function: "Evaluaciones" and "Tutor", each holding who may use the
 * function, what it recorded where there is a reading, and its stage's settings. Both are
 * always here, whatever their mode: the administrator configures a function before opening
 * it to anybody. Each tab is its own file, because the screen that crosses every account
 * and every workspace is also the one that grows.
 */
export function AdminScreen() {
  const { t } = useT();
  const session = useSession();
  const [tab, setTab] = useState("motor");
  // The open stage of "Configuración" lives here and not in its tab, because a function's
  // tab opens it too: a setting folded there under another stage links to that stage.
  const [configStage, setConfigStage] = useState<string | null>(null);
  // So does the draft of the stages' settings, and for the same link: a change typed in a
  // function's tab is still pending on the stage the link opens, and back. And so does the
  // draft of who may use each function, which sits in that same tab above the link.
  const stagesDraft = useStagesDraft();
  const accessDrafts = useAccessDrafts();
  // The evaluation's reading filter lives here and not in its tab, because "Cuentas" sets it
  // ("ver sus sesiones") before switching over.
  const [filters, setFilters] = useState<EvaluationFilters>({});
  const tabs = useRef<HTMLDivElement>(null);

  const overview = useAdminOverview();

  // Every way to a stage's settings: a function's own stage is its tab, any other one is
  // "Configuración" open on it. Crossing tabs from the foot of a long one would land at the
  // foot of the next, so the bar of tabs comes back into view.
  const goToStage = (key: string) => {
    const feature = CONFIG_STAGES.find((stage) => stage.key === key)?.feature ?? null;
    const next = feature ?? "config";
    if (!feature) setConfigStage(key);
    if (next !== tab) {
      setTab(next);
      tabs.current?.scrollIntoView({ block: "start" });
    }
  };

  if (!session.data?.user.is_admin) {
    return (
      <EmptyState icon={<ShieldCheck className="size-6" />} title={t("admin.notAdmin")}>
        {t("admin.notAdmin.body")}
      </EmptyState>
    );
  }

  if (overview.isLoading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-5">
      <header className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-display font-expanded text-display">{t("admin.title")}</h1>
          <InfoHint label={t("admin.whatIsThis")}>{t("admin.whatIsThis.body")}</InfoHint>
        </div>
        <GuideLink slug="admin" />
      </header>

      <MaintenanceSwitch />

      {/* Above the tabs on purpose: three of the six render nothing without this data, the
          functions' two lose who may use them, and an empty tab with no explanation reads as
          a feature that does not exist. */}
      {overview.data ? (
        <Totals overview={overview.data} />
      ) : (
        <LoadError
          title={t("admin.unreadable")}
          error={overview.error}
          onRetry={overview.refetch}
        />
      )}

      {/* Cleared of the sticky header, which takes a second row of navigation below `xl`. */}
      <div ref={tabs} className="scroll-mt-44 xl:scroll-mt-24">
        <Tabs
          items={[
            { value: "motor", label: t("admin.tab.engine") },
            { value: "config", label: t("admin.tab.config") },
            { value: "cuentas", label: t("admin.tab.accounts") },
            { value: "workspaces", label: t("admin.tab.workspaces") },
            {
              value: "evaluation",
              label: t("admin.tab.evaluation"),
              tone: "evaluation",
              separated: true,
            },
            { value: "tutor", label: t("admin.tab.tutor"), tone: "tutor" },
          ]}
          value={tab}
          onChange={setTab}
        />
      </div>

      {tab === "evaluation" ? (
        <FeatureTab
          feature="evaluation"
          overview={overview.data}
          draft={stagesDraft}
          access={accessDrafts}
          onGo={goToStage}
        >
          <Suspense fallback={<Skeleton className="h-96" />}>
            <EvaluationTab filters={filters} onFilters={setFilters} />
          </Suspense>
        </FeatureTab>
      ) : null}

      {tab === "tutor" ? (
        <FeatureTab
          feature="tutor"
          overview={overview.data}
          draft={stagesDraft}
          access={accessDrafts}
          onGo={goToStage}
        />
      ) : null}

      {tab === "cuentas" && overview.data ? (
        <AccountsTab
          overview={overview.data}
          onInspect={(id) => {
            setFilters({ account: id });
            setTab("evaluation");
          }}
        />
      ) : null}

      {tab === "workspaces" && overview.data ? (
        <WorkspacesTab overview={overview.data} />
      ) : null}

      {tab === "motor" && overview.data ? <EngineTab overview={overview.data} /> : null}

      {tab === "config" ? (
        <ConfigTab stage={configStage} draft={stagesDraft} onGo={goToStage} />
      ) : null}
    </div>
  );
}

/**
 * One optional function's tab: who may use it, what it recorded (`children`, where it has a
 * reading), and its stage's settings, the same values «Configuración» edits.
 */
function FeatureTab({
  feature,
  overview,
  draft,
  access,
  onGo,
  children,
}: {
  feature: FeatureName;
  overview: AdminOverview | undefined;
  draft: StagesDraft;
  access: AccessDrafts;
  onGo: (stage: string) => void;
  children?: ReactNode;
}) {
  const { t } = useT();
  return (
    <div className="space-y-8">
      {overview ? (
        <FeatureAccess feature={feature} accounts={overview.accounts} drafts={access} />
      ) : null}
      {children}
      <StageSettings
        stage={stageOfFeature(feature).key}
        eyebrow={t("admin.tab.config")}
        draft={draft}
        onGo={onGo}
      />
    </div>
  );
}

function Totals({ overview }: { overview: AdminOverview }) {
  const { t, plural, language } = useT();
  const { totals, engine } = overview;
  return (
    <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5">
      <StatTile label={t("admin.stat.accounts")} value={totals.users} />
      <StatTile label={t("admin.stat.workspaces")} value={totals.workspaces} />
      <StatTile
        label={t("admin.stat.generations")}
        value={totals.generations.toLocaleString(language)}
      />
      <StatTile
        label={t("admin.stat.comparisons")}
        value={totals.evaluations}
        hint={t("admin.stat.decided", { n: totals.decided })}
      />
      <StatTile
        label={t("admin.stat.engine")}
        value={engine.busy ? t("admin.stat.busy") : t("admin.stat.free")}
        tone={engine.busy ? "accent" : "plain"}
        hint={
          engine.busy
            ? t("admin.stat.busyHint", {
                label: engine.job ? jobName(engine.job.kind, t, engine.job.label) : t("admin.stat.job"),
                n: engine.queued,
              })
            : plural("admin.warmContexts", engine.warm_contexts.length)
        }
      />
    </div>
  );
}

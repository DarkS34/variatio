import { BarChart3, KeyRound, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { lazy, Suspense, useRef, useState, type ReactNode } from "react";

import { GuideLink } from "@/components/GuideLink";
import { InfoHint } from "@/components/ui/hint";
import { EmptyState, LoadError, Skeleton } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { featureAccessOf, type AdminOverview, type FeatureName } from "@/lib/types";
import { useSession } from "@/state/auth";
import { useAdminFeatures, useAdminOverview } from "@/state/queries";

import type { EvaluationFilters } from "@/evaluation/types";

import { AccountsTab } from "./AccountsTab";
import {
  ConfigTab,
  StageSettings,
  useStagesDraft,
  useStageSummary,
  type StagesDraft,
} from "./ConfigTab";
import { EngineTab } from "./EngineTab";
import { FeatureAccess, useAccessDrafts, type AccessDrafts } from "./FeatureAccess";
import { MaintenanceSwitch } from "./MaintenanceSwitch";
import { SectionHeader, Sections, type SectionEntry } from "./Sections";
import { CONFIG_STAGES, stageOfFeature } from "./stages";
import { WorkspacesTab } from "./WorkspacesTab";
import { useT, withCatalogues } from "@/lib/i18n";

// The evaluation's reading is the evaluation's code, fetched when its section is opened. The
// administrator reads it whatever the evaluation's mode: its routes are not behind it.
const EvaluationTab = lazy(() =>
  withCatalogues(import("@/evaluation/AdminEvaluationTab")).then((m) => ({
    default: m.EvaluationTab,
  })),
);

/** The sections of an optional function's tab, in the order its list draws them. */
type FeatureSection = "access" | "analytics" | "settings";

/**
 * The installation seen from outside: six tabs, one per thing an administrator runs.
 *
 * "Motor" is the machine and the process — the GPU, the tunnel, the models on disk, the
 * queue; "Configuración" is every value the registry exposes for the product's stages;
 * "Cuentas" decides who exists and where they get in; "Asignaturas" lists the instances and
 * what they weigh. Then, ruled off and each in its own colour like its door in the bar, one
 * tab per optional function: "Evaluaciones" and "Tutor". Both are always here, whatever
 * their mode: the administrator configures a function before opening it to anybody.
 *
 * EVERY TAB IS DRAWN THE SAME WAY (`Sections`): the list of its sections on the left, each
 * row with the state of what it opens, and the section open on the right under one header.
 * (A tab with one section, «Asignaturas», has no list: its header and its table.) The list
 * is the tab's summary, so nothing above the tabs repeats it: the row of totals
 * that used to sit there said what the lists now say where it can be acted on. Each tab is
 * its own file, because the screen that crosses every account and every workspace is also
 * the one that grows.
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
  // The evaluation's reading filter lives here and not in its tab, so it survives a visit
  // to another tab of the panel.
  const [filters, setFilters] = useState<EvaluationFilters>({});
  // The section open in each function's tab lives here for the same link: a folded link
  // opens a function's settings from another tab.
  const [sections, setSections] = useState<Record<FeatureName, FeatureSection>>({
    evaluation: "access",
    tutor: "access",
  });
  const openSection = (feature: FeatureName, section: FeatureSection) =>
    setSections((held) => ({ ...held, [feature]: section }));
  const tabs = useRef<HTMLDivElement>(null);

  const overview = useAdminOverview();

  // Every way to a stage's settings: a function's own stage is the settings of its tab, any
  // other one is "Configuración" open on it. Crossing tabs from the foot of a long one would
  // land at the foot of the next, so the bar of tabs comes back into view.
  const goToStage = (key: string) => {
    const feature = CONFIG_STAGES.find((stage) => stage.key === key)?.feature ?? null;
    const next = feature ?? "config";
    if (feature) openSection(feature, "settings");
    else setConfigStage(key);
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
      {/* The door of the installation shares the title's line while it is open, and takes a
          line of its own, in red, while it is closed (`MaintenanceSwitch`). */}
      <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display font-expanded text-display">{t("admin.title")}</h1>
            <InfoHint label={t("admin.whatIsThis")}>{t("admin.whatIsThis.body")}</InfoHint>
          </div>
          <GuideLink slug="admin" />
        </div>
        <MaintenanceSwitch />
      </header>

      {/* Above the tabs on purpose: three of the six render nothing without this data, the
          functions' two lose who may use them, and an empty tab with no explanation reads as
          a feature that does not exist. */}
      {overview.data ? null : (
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
          section={sections.evaluation}
          onSection={(section) => openSection("evaluation", section)}
          overview={overview.data}
          draft={stagesDraft}
          access={accessDrafts}
          onGo={goToStage}
          analytics={
            <Suspense fallback={<Skeleton className="h-96" />}>
              <EvaluationTab filters={filters} onFilters={setFilters} />
            </Suspense>
          }
        />
      ) : null}

      {tab === "tutor" ? (
        <FeatureTab
          feature="tutor"
          section={sections.tutor}
          onSection={(section) => openSection("tutor", section)}
          overview={overview.data}
          draft={stagesDraft}
          access={accessDrafts}
          onGo={goToStage}
        />
      ) : null}

      {tab === "cuentas" && overview.data ? (
        <AccountsTab overview={overview.data} />
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
 * One optional function's tab, as the list every tab is: who may use it («Permisos de
 * uso»), what it recorded where it has a reading («Analíticas»), and its stage's settings
 * («Configuración»), the same values «Configuración» edits.
 *
 * Each row says its section's state: who the function is open to now, how much the reading
 * holds, how many settings — and what is changed there and not saved yet, since both drafts
 * outlive the section they were typed in.
 */
function FeatureTab({
  feature,
  section,
  onSection,
  overview,
  draft,
  access,
  onGo,
  analytics,
}: {
  feature: FeatureName;
  section: FeatureSection;
  onSection: (next: FeatureSection) => void;
  overview: AdminOverview | undefined;
  draft: StagesDraft;
  access: AccessDrafts;
  onGo: (stage: string) => void;
  /** The function's reading, for the one that has it. */
  analytics?: ReactNode;
}) {
  const { t, plural } = useT();
  const stage = stageOfFeature(feature);
  const features = useAdminFeatures();
  const summary = useStageSummary(stage.key, draft);
  const saved = features.data ? featureAccessOf(features.data, feature) : null;

  const items: SectionEntry[] = [
    {
      key: "access",
      label: t("feature.section.access"),
      mark: <KeyRound className="size-4" />,
      detail: !saved
        ? undefined
        : saved.mode === "all"
          ? t("feature.mode.all")
          : saved.mode === "selected" && saved.accounts.length > 0
            ? plural("acc.count", saved.accounts.length)
            : t("feature.mode.off"),
      pending: access.values[feature] ? 1 : 0,
    },
    ...(analytics
      ? [
          {
            key: "analytics",
            label: t("feature.section.analytics"),
            mark: <BarChart3 className="size-4" />,
            detail: overview ? plural("acc.comparisons", overview.totals.evaluations) : undefined,
          },
        ]
      : []),
    ...(summary
      ? [
          {
            key: "settings",
            label: t("admin.tab.config"),
            mark: <SlidersHorizontal className="size-4" />,
            detail: plural("cfg.nav.settings", summary.settings),
            pending: summary.pending,
          },
        ]
      : []),
  ];
  const open = items.some((item) => item.key === section) ? section : "access";

  return (
    <Sections
      label={t("feature.section.label", { name: t(stage.labelKey) })}
      items={items}
      value={open}
      onChange={(key) => onSection(key as FeatureSection)}
    >
      {open === "access" && overview ? (
        <FeatureAccess feature={feature} accounts={overview.accounts} drafts={access} />
      ) : null}

      {open === "analytics" ? (
        <>
          <SectionHeader
            title={t("feature.section.analytics")}
            description={t("feature.section.analyticsNote")}
          />
          {analytics}
        </>
      ) : null}

      {open === "settings" ? (
        <StageSettings
          stage={stage.key}
          title={t("admin.tab.config")}
          draft={draft}
          onGo={onGo}
        />
      ) : null}
    </Sections>
  );
}

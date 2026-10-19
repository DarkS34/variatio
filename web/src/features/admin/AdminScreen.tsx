import { ShieldCheck } from "lucide-react";
import { lazy, Suspense, useRef, useState } from "react";

import { InfoHint } from "@/components/ui/hint";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadError } from "@/components/ui/load-error";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import type { Door } from "@/lib/steps";
import type { GatedName } from "@/lib/types";
import { useSession } from "@/state/auth";
import { useAdminOverview } from "@/state/queries";

import type { EvaluationFilters } from "@/consumers/evaluation/types";

import { AccountsTab } from "./AccountsTab";
import { ConfigTab, useStagesDraft } from "./ConfigTab";
import { EngineTab } from "./EngineTab";
import { useAccessDrafts } from "./FeatureAccess";
import { FunctionsTab, type FeaturePart } from "./FunctionsTab";
import { MaintenanceSwitch } from "./MaintenanceSwitch";
import { CONFIG_STAGES } from "./stages";
import { WorkspacesTab } from "./WorkspacesTab";
import { useT, withCatalogues } from "@/lib/i18n";

// The evaluation's reading is the evaluation's code, fetched when its part is opened. The
// administrator reads it whatever the evaluation's mode: its routes are not behind it.
const EvaluationTab = lazy(() =>
  withCatalogues(import("@/consumers/evaluation/AdminEvaluationTab")).then((m) => ({
    default: m.EvaluationTab,
  })),
);

/**
 * The installation seen from outside: five tabs, one per thing an administrator runs.
 *
 * "Motor" is the machine and the process — the GPU, the tunnel, the models on disk, the
 * queue; "Configuración" is every value the registry exposes for the construction's stages;
 * "Cuentas" decides who exists and where they get in; "Asignaturas" lists the instances and
 * what they weigh. Then, ruled off, "Funciones": what the installation offers once a subject
 * is built — generating, the evaluation, the tutor and the free chat — each with who may
 * use it and its settings. Each is there whatever its mode: the administrator configures a
 * function before opening it to anybody.
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
  // The open stage of "Configuración" lives here and not in its tab, because «Funciones»
  // opens it too: a setting folded there under another stage links to that stage.
  const [configStage, setConfigStage] = useState<string | null>(null);
  // So does the draft of the stages' settings, and for the same link: a change typed in
  // «Funciones» is still pending on the stage the link opens, and back. And so does the
  // draft of who may use each function, which sits in that same tab above the link.
  const stagesDraft = useStagesDraft();
  const accessDrafts = useAccessDrafts();
  // The evaluation's reading filter lives here and not in its tab, so it survives a visit
  // to another tab of the panel.
  const [filters, setFilters] = useState<EvaluationFilters>({});
  // The function open in «Funciones», and the part open in each, live here for the same
  // link: a folded link opens a function's settings from another tab.
  const [door, setDoor] = useState<Door["key"]>("generate");
  const [parts, setParts] = useState<Record<GatedName, FeaturePart>>({
    generate: "access",
    evaluation: "access",
    tutor: "access",
    chat: "access",
  });
  const openPart = (name: GatedName, part: FeaturePart) =>
    setParts((held) => ({ ...held, [name]: part }));
  const tabs = useRef<HTMLDivElement>(null);

  const overview = useAdminOverview();

  // Every way to a stage's settings: a door's stage is its function in «Funciones», open on
  // its settings; any other one is "Configuración" open on it. Crossing tabs from the foot of
  // a long one would land at the foot of the next, so the bar of tabs comes back into view.
  const goToStage = (key: string) => {
    const stage = CONFIG_STAGES.find((entry) => entry.key === key);
    const next = stage?.door ? "functions" : "config";
    if (stage?.door) {
      setDoor(stage.door);
      if (stage.access) openPart(stage.access, "settings");
    } else setConfigStage(key);
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
        </div>
        <MaintenanceSwitch />
      </header>

      {/* Above the tabs on purpose: three of the five render nothing without this data,
          «Funciones» loses who may use each function, and an empty tab with no explanation reads as
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
            { value: "functions", label: t("admin.tab.functions"), separated: true },
          ]}
          value={tab}
          onChange={setTab}
        />
      </div>

      {tab === "functions" ? (
        <FunctionsTab
          door={door}
          onDoor={setDoor}
          parts={parts}
          onPart={openPart}
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

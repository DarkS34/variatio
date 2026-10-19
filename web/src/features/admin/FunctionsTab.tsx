import type { ReactNode } from "react";

import { SectionHeader, Sections, type SectionEntry } from "@/components/Sections";
import { DOOR_TONE } from "@/components/ui/tone";
import { Tabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n";
import { USES, type Door } from "@/lib/steps";
import { featureAccessOf, type AdminOverview, type GatedName } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAdminFeatures } from "@/state/queries";

import { StageSettings, useStageSummaries, type StagesDraft } from "./ConfigTab";
import { FeatureAccess, type AccessDrafts } from "./FeatureAccess";
import { stageOfDoor } from "./stages";

/** The parts of a function, in the order its tabs draw them. */
export type FeaturePart = "access" | "analytics" | "settings";

const STAGES = USES.map((door) => stageOfDoor(door.key).key);

/**
 * «Funciones»: what the installation offers once a subject is built, one row per door of the
 * bar — generating, the evaluation, the tutor and the free chat — in the bar's order.
 *
 * The user's requests (2026-10-19): the free chat is a function like the evaluation and the
 * tutor, and generating is one too, so the four leave «Configuración» and the two tabs of
 * their own for one list; and the administrator chooses who may use each of them. A row's line
 * says who may use it now; its badge counts what is changed there and not saved, both drafts
 * included, since they outlive the part they were typed in.
 *
 * A function opens its parts as tabs — «Permisos de uso», «Analíticas» (the evaluation's
 * reading) and «Configuración» — because stacking them down one page is what the list of
 * sections replaced on 2026-10-04.
 */
export function FunctionsTab({
  door,
  onDoor,
  parts,
  onPart,
  overview,
  draft,
  access,
  onGo,
  analytics,
}: {
  door: Door["key"];
  onDoor: (next: Door["key"]) => void;
  parts: Record<GatedName, FeaturePart>;
  onPart: (name: GatedName, part: FeaturePart) => void;
  overview: AdminOverview | undefined;
  draft: StagesDraft;
  access: AccessDrafts;
  onGo: (stage: string) => void;
  /** The evaluation's reading, drawn in its «Analíticas». */
  analytics: ReactNode;
}) {
  const { t, plural } = useT();
  const features = useAdminFeatures();
  const summaries = useStageSummaries(STAGES, draft);

  // Who may use a function, as its row says it.
  const accessLine = (name: GatedName) => {
    const saved = features.data ? featureAccessOf(features.data, name) : null;
    if (!saved) return undefined;
    if (saved.mode === "all") return t("feature.mode.all");
    if (saved.mode === "selected") {
      const subjects = saved.workspaces?.length ?? 0;
      if (saved.accounts.length > 0) return plural("acc.count", saved.accounts.length);
      if (subjects > 0) return plural("feature.state.subjectsN", subjects);
    }
    return t("feature.mode.off");
  };

  const items: SectionEntry[] = USES.map((entry) => {
    const summary = summaries[stageOfDoor(entry.key).key];
    const Icon = stageOfDoor(entry.key).icon!;
    return {
      key: entry.key,
      label: t(entry.labelKey),
      mark: <Icon className={cn("size-4", entry.feature && DOOR_TONE[entry.feature].face)} />,
      detail: accessLine(entry.access),
      pending: (summary?.pending ?? 0) + (access.values[entry.access] ? 1 : 0),
    };
  });
  const open = USES.find((entry) => entry.key === door) ?? USES[0];
  const stage = stageOfDoor(open.key).key;

  return (
    <Sections
      label={t("admin.tab.functions")}
      items={items}
      value={open.key}
      onChange={(key) => onDoor(key as Door["key"])}
    >
      <FunctionParts
        key={open.key}
        name={open.access}
        stage={stage}
        part={parts[open.access]}
        onPart={(part) => onPart(open.access, part)}
        hasSettings={Boolean(summaries[stage])}
        overview={overview}
        draft={draft}
        access={access}
        onGo={onGo}
        analytics={open.access === "evaluation" ? analytics : null}
      />
    </Sections>
  );
}

/**
 * One function: a row of tabs over the part open — who may use it, what it recorded where it
 * has a reading, and its stage's settings, the same values «Configuración» edits.
 */
function FunctionParts({
  name,
  stage,
  part,
  onPart,
  hasSettings,
  overview,
  draft,
  access,
  onGo,
  analytics,
}: {
  name: GatedName;
  stage: string;
  part: FeaturePart;
  onPart: (next: FeaturePart) => void;
  hasSettings: boolean;
  overview: AdminOverview | undefined;
  draft: StagesDraft;
  access: AccessDrafts;
  onGo: (stage: string) => void;
  analytics: ReactNode;
}) {
  const { t } = useT();
  const tabs = [
    { value: "access", label: t("feature.section.access") },
    ...(analytics ? [{ value: "analytics", label: t("feature.section.analytics") }] : []),
    ...(hasSettings ? [{ value: "settings", label: t("admin.tab.config") }] : []),
  ];
  const open = tabs.some((tab) => tab.value === part) ? part : "access";

  return (
    <>
      {tabs.length > 1 ? (
        <Tabs items={tabs} value={open} onChange={(next) => onPart(next as FeaturePart)} />
      ) : null}

      {open === "access" && overview ? (
        <FeatureAccess
          feature={name}
          accounts={overview.accounts}
          workspaces={overview.workspaces}
          drafts={access}
        />
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
        <StageSettings stage={stage} title={t("admin.tab.config")} draft={draft} onGo={onGo} />
      ) : null}
    </>
  );
}

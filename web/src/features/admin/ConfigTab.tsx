import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, RefreshCw, Save, Wrench } from "lucide-react";
import { useState, type Dispatch, type SetStateAction } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Alert, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { ReasoningLegend } from "@/features/admin/PhaseNode";
import { SectionHeader, Sections, type SectionEntry } from "@/features/admin/Sections";
import { DiffSummary, GroupCard, SETTING_LIST, sameValue } from "@/features/admin/SettingFields";
import {
  FlowNode,
  nodeKeys,
  Row,
  StageFlow,
  valueOf,
  type FlowContext,
} from "@/features/admin/StageFlow";
import {
  CONFIG_STAGES,
  homeOf,
  isCommon,
  isSharedInto,
  type ConfigStage,
} from "@/features/admin/stages";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { ConfigPayload, ConfigSetting, ReasoningLane, ReasoningPhase } from "@/lib/types";
import { cn } from "@/lib/utils";

// Drawn in "Administración → Motor", beside the meters that give them meaning, or not at
// all: the level the process logs at is read from `VARIATIO_LOG_LEVEL` by whoever reads
// the log. Every one of them belongs to no stage, and none gets a row here.
export const ENGINE_GROUPS = ["Motor", "Túnel SSH"]; // i18n-exempt
const UNLISTED_GROUPS = ["Registro"]; // i18n-exempt

// Drawn INSIDE another setting's field and therefore never as a row of its own: the level a
// locked model is called with is asked on that model's own line, in `generation.fixed_
// effort`. It still travels in the save bar's list of pending changes, which reads
// `payload.settings` unfiltered.
const DRAWN_ON_ANOTHER_ROW = ["generation.fixed_effort_levels"];

// A setting no stage claims: what an API older than the stages sends for everything, and
// what a registry addition without a stage would be. It gets a page rather than vanishing.
const OTHERS_KEY = "__otros__";

/**
 * THE CONFIGURATION, ONE SCREEN PER STAGE OF THE PATH.
 *
 * Each screen holds everything its stage's work reads: its calls down the page — model,
 * reasoning and sampling on each node, the call's own parameters under it — then what
 * governs the stage as a whole, then what every stage shares, and, folded, what it reads
 * of another stage's (a setting shared is still ONE value: changing it here changes it
 * there). Nothing is folded that is not also unfolded on its own stage's screen.
 *
 * The two optional functions' stages are not listed here: each is drawn in its function's
 * own tab, beside who may use it (`StageSettings`). The search still finds their settings
 * and edits them here, because a value is one wherever it is drawn.
 *
 * Which stage is open belongs to `AdminScreen`, which also opens one from a function's tab:
 * `onGo` is every way to another stage, the nav's and the folded links'. So does the draft
 * (`useStagesDraft`), which a folded link would otherwise leave behind in the tab it left.
 */
export function ConfigTab({
  stage,
  onGo,
  draft: held,
}: {
  stage: string | null;
  onGo: (stage: string) => void;
  draft: StagesDraft;
}) {
  const { t, plural } = useT();
  const screen = useConfigScreen(held);
  const [search, setSearch] = useState("");

  if (screen.query.isLoading) return <Skeleton className="h-96" />;
  const payload = screen.payload;
  if (!payload) {
    return (
      <LoadError
        title={t("cfg.unreadable")}
        error={screen.query.error}
        onRetry={screen.query.refetch}
      />
    );
  }
  const { draft } = screen;

  const visible = visibleOf(payload);
  const orphans = visible.filter((setting) => homeOf(setting) === null);
  const lanes = new Map((payload.pipeline ?? []).map((lane) => [lane.key, lane]));
  const served = new Set(payload.stages ?? []);
  const stages = CONFIG_STAGES.filter(
    (entry) =>
      entry.feature === null &&
      served.has(entry.key) &&
      visible.some((setting) => readsIn(setting, entry.key)),
  );
  const settingsOf = (key: string) =>
    key === OTHERS_KEY ? orphans : visible.filter((setting) => readsIn(setting, key));

  const pendingOf = (key: string) => {
    const keys = new Set(settingsOf(key).map((setting) => setting.key));
    return Object.keys(draft).filter((draftKey) => keys.has(draftKey)).length;
  };
  const ctx = contextOf(payload, screen);

  const activeKey =
    stage === OTHERS_KEY && orphans.length > 0
      ? OTHERS_KEY
      : (stages.find((entry) => entry.key === stage) ?? stages[0])?.key ?? OTHERS_KEY;
  const term = search.trim().toLowerCase();
  const matches = term
    ? visible.filter((setting) =>
        `${setting.name} ${setting.key} ${setting.group}`.toLowerCase().includes(term),
      )
    : null;

  const items: SectionEntry[] = [
    ...stages.map((entry) => ({
      key: entry.key,
      label: t(entry.labelKey),
      mark: <StageMark stage={entry} />,
      detail: plural("cfg.nav.settings", settingsOf(entry.key).length),
      pending: pendingOf(entry.key),
    })),
    ...(orphans.length > 0
      ? [
          {
            key: OTHERS_KEY,
            label: t("cfg.section.others"),
            mark: <Wrench className="size-4" />,
            detail: plural("cfg.nav.settings", orphans.length),
            pending: pendingOf(OTHERS_KEY),
          },
        ]
      : []),
  ];

  return (
    <Sections
      label={t("cfg.nav")}
      items={items}
      value={matches ? null : activeKey}
      onChange={(key) => {
        setSearch("");
        onGo(key);
      }}
      before={
        <Input
          aria-label={t("cfg.search")}
          placeholder={t("cfg.searchPlaceholder")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      }
      after={
        // What concerns every stage at once sits under their list: where a value comes
        // from, and reading the file again.
        <div className="space-y-2 px-1">
          <p className="text-small text-muted-foreground">{t("cfg.intro")}</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => screen.reload.mutate()}
            disabled={screen.reload.isPending}
          >
            {screen.reload.isPending ? <Spinner /> : <RefreshCw />}
            {t("cfg.reload")}
          </Button>
          <FormError error={screen.reload.error} />
        </div>
      }
    >
      <AppliedNotice applied={screen.applied} />
      {matches ? (
        <>
          <SectionHeader title={plural("cfg.matches", matches.length, { term: search.trim() })} />
          {matches.length > 0 ? (
            <Card>
              <CardContent className={cn(SETTING_LIST, "pt-5")}>
                {matches.map((setting) => (
                  <div key={setting.key} className="space-y-1.5">
                    <HomeCaption setting={setting} />
                    <Row setting={setting} ctx={ctx} />
                  </div>
                ))}
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : activeKey === OTHERS_KEY ? (
        <>
          <SectionHeader
            title={t("cfg.section.others")}
            description={t("cfg.section.othersDesc")}
          />
          <GroupCard
            title={null}
            settings={orphans}
            draft={draft}
            onChange={screen.setValue}
            onReset={(key) => screen.reset.mutate(key)}
            models={payload.models ?? null}
            offered={ctx.offered}
            levels={ctx.levels}
            onLevels={ctx.onLevels}
          />
        </>
      ) : (
        <StageView
          key={activeKey}
          stage={stages.find((entry) => entry.key === activeKey)!}
          lane={lanes.get(activeKey) ?? null}
          lanes={payload.pipeline ?? []}
          settings={settingsOf(activeKey)}
          ctx={ctx}
          onGo={onGo}
        />
      )}

      <DiffSummary settings={payload.settings} draft={draft} />
      <SaveBar screen={screen} />
    </Sections>
  );
}

/**
 * One stage's screen on its own, with its own save bar: what an optional function's tab
 * draws under who may use it.
 *
 * The same draft, save and reset as «Configuración», and the same screen: a setting it
 * shares with another stage is still ONE value, folded here and unfolded on its owner's
 * screen, which the folded link opens through `onGo` with the draft still pending. Nothing
 * at all when the server does not serve the stage, or serves it with nothing to set.
 */
export function StageSettings({
  stage,
  title,
  onGo,
  draft: held,
}: {
  stage: string;
  /** The section's name where the list it is opened from calls it something else. */
  title?: string;
  onGo: (stage: string) => void;
  draft: StagesDraft;
}) {
  const { t } = useT();
  const screen = useConfigScreen(held);

  if (screen.query.isLoading) return <Skeleton className="h-96" />;
  const payload = screen.payload;
  if (!payload) {
    return (
      <LoadError
        title={t("cfg.unreadable")}
        error={screen.query.error}
        onRetry={screen.query.refetch}
      />
    );
  }
  const entry = CONFIG_STAGES.find((candidate) => candidate.key === stage);
  const settings = visibleOf(payload).filter((setting) => readsIn(setting, stage));
  if (!entry || !(payload.stages ?? []).includes(stage) || settings.length === 0) return null;
  const lanes = payload.pipeline ?? [];

  return (
    <>
      <AppliedNotice applied={screen.applied} />
      <StageView
        stage={entry}
        title={title}
        lane={lanes.find((lane) => lane.key === stage) ?? null}
        lanes={lanes}
        settings={settings}
        ctx={contextOf(payload, screen)}
        onGo={onGo}
      />
      <DiffSummary settings={payload.settings} draft={screen.draft} />
      <SaveBar screen={screen} />
    </>
  );
}

/**
 * How much one stage's screen holds, for the row that opens it: its settings and how many
 * of them are changed and not saved. Null while unread, or when the server does not serve
 * the stage or serves it with nothing to set — the cases in which `StageSettings` draws
 * nothing, so no row should open it.
 */
export function useStageSummary(
  stage: string,
  held: StagesDraft,
): { settings: number; pending: number } | null {
  const query = useQuery({ queryKey: ["admin", "config"], queryFn: api.adminConfig });
  const payload = query.data;
  if (!payload || !(payload.stages ?? []).includes(stage)) return null;
  const settings = visibleOf(payload).filter((setting) => readsIn(setting, stage));
  if (settings.length === 0) return null;
  return {
    settings: settings.length,
    pending: settings.filter((setting) => setting.key in held.values).length,
  };
}

/** The stages' settings changed and not yet saved, and the way to change them. */
export type StagesDraft = {
  values: Record<string, unknown>;
  set: Dispatch<SetStateAction<Record<string, unknown>>>;
};

/**
 * Hold the stages' draft, for the screen that draws every tab of the panel.
 *
 * Three tabs draw stages' settings — «Configuración» and the two functions' — and a folded
 * link crosses from one to another, so the draft outlives the tab it was typed in: a change
 * left pending in «Tutor» is still pending in «Configuración», and its save bar saves it.
 * It is ONE draft because a setting is one value wherever it is drawn. The engine's draft
 * stays «Motor»'s own: no setting is in both, because the stages never draw the engine's.
 */
export function useStagesDraft(): StagesDraft {
  const [values, set] = useState<Record<string, unknown>>({});
  return { values, set };
}

type ConfigScreen = ReturnType<typeof useConfigScreen>;

/**
 * What a screen of the configuration edits through: the stored payload, the stages' draft
 * over it, and saving, resetting and re-reading.
 *
 * «Configuración» holds one and so does each function's stage in its own tab, all over the
 * draft `AdminScreen` holds; only one is mounted at a time.
 */
function useConfigScreen(held: StagesDraft) {
  const { t } = useT();
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: ["admin", "config"], queryFn: api.adminConfig });
  const { values: draft, set: setDraft } = held;
  const [applied, setApplied] = useState<string[] | null>(null);

  const invalidate = () => client.invalidateQueries({ queryKey: ["admin", "config"] });

  const save = useMutation({
    mutationFn: () => api.updateAdminConfig(draft),
    onSuccess: (payload) => {
      setDraft({});
      setApplied(payload.applied ?? null);
      invalidate();
      toast({ title: t("cfg.saved") });
    },
  });

  const reload = useMutation({
    mutationFn: () => api.reloadAdminConfig(),
    onSuccess: (payload) => {
      setApplied(payload.applied ?? null);
      invalidate();
      toast({ title: t("cfg.reloaded") });
    },
  });

  // Back to the registry's default, one setting at a time: the key leaves the file, so the
  // row reads "por defecto" again rather than a file value that happens to equal it.
  const reset = useMutation({
    mutationFn: (key: string) => api.resetAdminConfig([key]),
    onSuccess: (payload, key) => {
      setDraft((prev) => {
        const { [key]: _dropped, ...rest } = prev;
        return rest;
      });
      setApplied(payload.applied ?? null);
      invalidate();
      toast({ title: t("cfg.resetDone") });
    },
    onError: (error: Error) =>
      toast({ title: t("cfg.resetFailed"), description: error.message, tone: "danger" }),
  });

  const payload: ConfigPayload | null = query.data ?? null;
  const stored = new Map(
    (payload?.settings ?? []).map((setting) => [setting.key, setting.value ?? setting.default]),
  );
  const setValue = (key: string, value: unknown) =>
    setDraft((prev) => {
      if (sameValue(value, stored.get(key))) {
        const { [key]: _dropped, ...rest } = prev;
        return rest;
      }
      return { ...prev, [key]: value };
    });

  return {
    query,
    payload,
    draft,
    setValue,
    discard: () => setDraft({}),
    dirty: Object.keys(draft).length > 0,
    applied,
    save,
    reload,
    reset,
  };
}

/** The settings a stage's screen may draw: none of the engine's, nor one drawn inside another. */
function visibleOf(payload: ConfigPayload): ConfigSetting[] {
  return payload.settings.filter(
    (setting) =>
      !DRAWN_ON_ANOTHER_ROW.includes(setting.key) &&
      !ENGINE_GROUPS.includes(setting.group) &&
      !UNLISTED_GROUPS.includes(setting.group),
  );
}

/**
 * What every row and node reads and writes, built from the payload and the screen's draft.
 *
 * The offered models AS THEY STAND IN THE DRAFT, so "Esfuerzo ajustable" follows a model
 * added or removed above it in the same visit rather than the last save; and the level
 * declared for each locked one, read from the draft for the same reason.
 */
function contextOf(payload: ConfigPayload, screen: ConfigScreen): FlowContext {
  const byKey = new Map(payload.settings.map((setting) => [setting.key, setting]));
  const offeredSetting = byKey.get("generation.models");
  const offeredValue = offeredSetting ? valueOf(offeredSetting, screen.draft) : null;
  const levelsSetting = byKey.get("generation.fixed_effort_levels");
  const levelsValue = levelsSetting ? valueOf(levelsSetting, screen.draft) : null;
  return {
    byKey,
    draft: screen.draft,
    models: payload.models ?? null,
    onChange: screen.setValue,
    onReset: (key) => screen.reset.mutate(key),
    offered: Array.isArray(offeredValue) ? offeredValue.map(String) : [],
    levels:
      levelsValue && typeof levelsValue === "object" && !Array.isArray(levelsValue)
        ? (levelsValue as Record<string, string>)
        : {},
    onLevels: (next) => screen.setValue("generation.fixed_effort_levels", next),
  };
}

/** What the last save, reset or re-read obliged the server to redo, when it was anything. */
function AppliedNotice({ applied }: { applied: string[] | null }) {
  const { t } = useT();
  if (!applied || applied.length === 0) return null;
  return (
    <Alert tone="settled" title={t("cfg.applied")}>
      <ul className="list-disc space-y-0.5 pl-5">
        {applied.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </Alert>
  );
}

/** The screen's save bar, held at the foot of the window while the screen is in view. */
function SaveBar({ screen }: { screen: ConfigScreen }) {
  const { t, plural } = useT();
  return (
    <>
      <FormError error={screen.save.error} />
      <div className="sticky bottom-3 flex items-center gap-2 rounded-inner bg-popover p-3 shadow-overlay">
        <Button disabled={!screen.dirty || screen.save.isPending} onClick={() => screen.save.mutate()}>
          {screen.save.isPending ? <Spinner /> : <Save />}
          {t("common.save")}
        </Button>
        <Button variant="outline" disabled={!screen.dirty} onClick={screen.discard}>
          {t("common.discard")}
        </Button>
        {screen.dirty ? (
          <span className="text-small text-muted-foreground">
            {plural("cfg.unsaved", Object.keys(screen.draft).length)}
          </span>
        ) : null}
      </div>
    </>
  );
}

/** Whether `stage`'s screen draws `setting`: its own, one every stage shares, or one it reads. */
function readsIn(setting: ConfigSetting, stage: string): boolean {
  return (setting.stages ?? []).includes(stage);
}

/**
 * One stage: its calls, what governs it whole, what all stages share, and what it reads of
 * another's — each of those drawn only when it holds something.
 */
function StageView({
  stage,
  title,
  lane,
  lanes,
  settings,
  ctx,
  onGo,
}: {
  stage: ConfigStage;
  title?: string;
  lane: ReasoningLane | null;
  lanes: ReasoningLane[];
  settings: ConfigSetting[];
  ctx: FlowContext;
  onGo: (stage: string) => void;
}) {
  const { t } = useT();
  const own = settings.filter((setting) => homeOf(setting) === stage.key && !isCommon(setting));
  const phases = lane?.phases ?? [];
  const onNodes = new Set(phases.flatMap(nodeKeys));
  const phaseKeys = new Set(phases.map((phase) => phase.key));
  const underNode = (phase: ReasoningPhase) =>
    own.filter((setting) => setting.phase === phase.key && !onNodes.has(setting.key));
  const general = own.filter(
    (setting) => !onNodes.has(setting.key) && !(setting.phase && phaseKeys.has(setting.phase)),
  );
  const common = settings.filter(isCommon);
  const shared = settings.filter((setting) => isSharedInto(setting, stage.key));

  return (
    <>
      <SectionHeader title={title ?? t(stage.labelKey)} description={t(stage.descriptionKey)} />

      {phases.length > 0 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>{t("cfg.flow")}</CardTitle>
            <CardDescription>{t("cfg.flowDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <StageFlow lane={lane!} ctx={ctx} rowsOf={underNode} />
            <ReasoningLegend />
          </CardContent>
        </Card>
      ) : null}

      {general.length > 0 ? (
        <SettingsCard title={t("cfg.general")} settings={general} ctx={ctx} />
      ) : null}

      {common.length > 0 ? (
        <SettingsCard
          title={t("cfg.common")}
          description={t("cfg.commonDesc")}
          settings={common}
          ctx={ctx}
        />
      ) : null}

      {shared.length > 0 ? (
        <SharedBlock stage={stage} shared={shared} lanes={lanes} ctx={ctx} onGo={onGo} />
      ) : null}
    </>
  );
}

/**
 * What this stage reads of other stages' settings, folded: each value is ONE, unfolded on
 * its own stage's screen, so folding it here never hides the only copy.
 *
 * A call of another stage that this one makes too (the repair, the tagger) is drawn as its
 * node, with its sampling and its rows; a setting this stage reads without making the call
 * goes in a list under the name of the stage that owns it.
 */
function SharedBlock({
  stage,
  shared,
  lanes,
  ctx,
  onGo,
}: {
  stage: ConfigStage;
  shared: ConfigSetting[];
  lanes: ReasoningLane[];
  ctx: FlowContext;
  onGo: (stage: string) => void;
}) {
  const { t } = useT();
  // Another stage's call is THIS stage's too when its model is read here, not merely one
  // setting drawn under it: the plural suffixes sit under the graph's merge and are read
  // by the generation's checks, which never call the merge.
  const calls = lanes
    .flatMap((lane) => lane.phases.map((phase) => ({ lane, phase })))
    .filter(({ lane, phase }) => {
      if (lane.key === stage.key) return false;
      const model = ctx.byKey.get(phase.model);
      return Boolean(model && (model.stages ?? []).includes(stage.key));
    });
  const callKeys = new Set(calls.map(({ phase }) => phase.key));
  const drawn = new Set(calls.flatMap(({ phase }) => nodeKeys(phase)));
  const loose = shared.filter(
    (setting) => !drawn.has(setting.key) && !(setting.phase && callKeys.has(setting.phase)),
  );
  const looseHomes = [...new Set(loose.map((setting) => homeOf(setting)!))];

  return (
    <details className="surface group">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-5 py-4">
        <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
        <span className="font-expanded text-body">{t("cfg.shared", { n: shared.length })}</span>
        <span className="text-small text-muted-foreground">{t("cfg.sharedDesc")}</span>
      </summary>
      <div className="space-y-5 px-5 pb-5 pt-1">
        {calls.length > 0 ? (
          <ol>
            {calls.map(({ lane, phase }, index) => (
              <FlowNode
                key={phase.key}
                phase={phase}
                ctx={ctx}
                rows={shared.filter(
                  (setting) => setting.phase === phase.key && !drawn.has(setting.key),
                )}
                aside={<OwnerLink stageKey={lane.key} onGo={onGo} />}
                last={index === calls.length - 1}
              />
            ))}
          </ol>
        ) : null}
        {looseHomes.map((home) => (
          <div key={home} className="space-y-3">
            <OwnerLink stageKey={home} onGo={onGo} />
            <div className={SETTING_LIST}>
              {loose
                .filter((setting) => homeOf(setting) === home)
                .map((setting) => (
                  <Row key={setting.key} setting={setting} ctx={ctx} />
                ))}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}

function SettingsCard({
  title,
  description,
  settings,
  ctx,
}: {
  title: string;
  description?: string;
  settings: ConfigSetting[];
  ctx: FlowContext;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className={SETTING_LIST}>
        {settings.map((setting) => (
          <Row key={setting.key} setting={setting} ctx={ctx} />
        ))}
      </CardContent>
    </Card>
  );
}

/** The stage that owns a shared setting, as a way there. */
function OwnerLink({ stageKey, onGo }: { stageKey: string; onGo: (stage: string) => void }) {
  const { t } = useT();
  const stage = CONFIG_STAGES.find((entry) => entry.key === stageKey);
  if (!stage) return null;
  return (
    <button
      type="button"
      onClick={() => onGo(stage.key)}
      className="inline-flex items-center gap-1.5 text-small text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
    >
      <StageMark stage={stage} />
      {t("cfg.ownedBy", { stage: t(stage.labelKey) })}
    </button>
  );
}

/** Above a search result: the screen it lives on. */
function HomeCaption({ setting }: { setting: ConfigSetting }) {
  const { t } = useT();
  const stage = CONFIG_STAGES.find((entry) => entry.key === homeOf(setting));
  return (
    <p className="flex items-center gap-1.5 text-micro text-muted-foreground">
      {stage ? <StageMark stage={stage} /> : null}
      {stage ? t(stage.labelKey) : t("cfg.section.others")}
    </p>
  );
}

/** A stage's mark, as the bar draws it: its number, or the icon of its door. */
function StageMark({ stage }: { stage: ConfigStage }) {
  if (stage.icon) return <stage.icon className="size-4 shrink-0" />;
  return (
    <span className="rounded-sm flex size-4 shrink-0 items-center justify-center border border-current text-micro leading-none">
      {stage.number}
    </span>
  );
}

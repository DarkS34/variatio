import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, RefreshCw, Save, Wrench } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Alert, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { ReasoningLegend } from "@/features/admin/PhaseNode";
import { DiffSummary, GroupCard, sameValue } from "@/features/admin/SettingFields";
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
 */
export function ConfigTab() {
  const tr = useT();
  const { t, plural } = tr;
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: ["admin", "config"], queryFn: api.adminConfig });
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [applied, setApplied] = useState<string[] | null>(null);
  const [active, setActive] = useState(CONFIG_STAGES[0].key);
  const [search, setSearch] = useState("");

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

  if (query.isLoading) return <Skeleton className="h-96" />;
  if (!query.data)
    return <LoadError title={t("cfg.unreadable")} error={query.error} onRetry={query.refetch} />;
  const payload: ConfigPayload = query.data;

  const stored = new Map(
    payload.settings.map((setting) => [setting.key, setting.value ?? setting.default]),
  );
  const visible = payload.settings.filter(
    (setting) =>
      !DRAWN_ON_ANOTHER_ROW.includes(setting.key) &&
      !ENGINE_GROUPS.includes(setting.group) &&
      !UNLISTED_GROUPS.includes(setting.group),
  );
  const orphans = visible.filter((setting) => homeOf(setting) === null);
  const lanes = new Map((payload.pipeline ?? []).map((lane) => [lane.key, lane]));
  const served = new Set(payload.stages ?? []);
  const stages = CONFIG_STAGES.filter(
    (stage) => served.has(stage.key) && visible.some((setting) => readsIn(setting, stage.key)),
  );
  const settingsOf = (key: string) =>
    key === OTHERS_KEY ? orphans : visible.filter((setting) => readsIn(setting, key));

  const setValue = (key: string, value: unknown) =>
    setDraft((prev) => {
      if (sameValue(value, stored.get(key))) {
        const { [key]: _dropped, ...rest } = prev;
        return rest;
      }
      return { ...prev, [key]: value };
    });
  const dirty = Object.keys(draft).length > 0;
  const pendingOf = (key: string) => {
    const keys = new Set(settingsOf(key).map((setting) => setting.key));
    return Object.keys(draft).filter((draftKey) => keys.has(draftKey)).length;
  };

  // The offered models AS THEY STAND IN THE DRAFT, so "Esfuerzo ajustable" follows a model
  // added or removed above it in the same visit rather than the last save; and the level
  // declared for each locked one, read from the draft for the same reason.
  const byKey = new Map(payload.settings.map((setting) => [setting.key, setting]));
  const offeredSetting = byKey.get("generation.models");
  const offeredValue = offeredSetting ? valueOf(offeredSetting, draft) : null;
  const levelsSetting = byKey.get("generation.fixed_effort_levels");
  const levelsValue = levelsSetting ? valueOf(levelsSetting, draft) : null;
  const ctx: FlowContext = {
    byKey,
    draft,
    models: payload.models ?? null,
    onChange: setValue,
    onReset: (key) => reset.mutate(key),
    offered: Array.isArray(offeredValue) ? offeredValue.map(String) : [],
    levels:
      levelsValue && typeof levelsValue === "object" && !Array.isArray(levelsValue)
        ? (levelsValue as Record<string, string>)
        : {},
    onLevels: (next) => setValue("generation.fixed_effort_levels", next),
  };

  const activeKey =
    active === OTHERS_KEY && orphans.length > 0
      ? OTHERS_KEY
      : (stages.find((stage) => stage.key === active) ?? stages[0])?.key ?? OTHERS_KEY;
  const term = search.trim().toLowerCase();
  const matches = term
    ? visible.filter((setting) =>
        `${setting.name} ${setting.key} ${setting.group}`.toLowerCase().includes(term),
      )
    : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-small text-muted-foreground">{t("cfg.intro")}</p>
        <Button variant="outline" onClick={() => reload.mutate()} disabled={reload.isPending}>
          {reload.isPending ? <Spinner /> : <RefreshCw />}
          {t("cfg.reload")}
        </Button>
      </div>

      <FormError error={reload.error} />
      {applied && applied.length > 0 ? (
        <Alert tone="settled" title={t("cfg.applied")}>
          <ul className="list-disc space-y-0.5 pl-5">
            {applied.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      <div className="grid items-start gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <nav aria-label={t("cfg.nav")} className="space-y-2 lg:sticky lg:top-4">
          <Input
            aria-label={t("cfg.search")}
            placeholder={t("cfg.searchPlaceholder")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <ul className="flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
            {stages.map((stage) => (
              <NavItem
                key={stage.key}
                current={!matches && stage.key === activeKey}
                pending={pendingOf(stage.key)}
                onSelect={() => {
                  setSearch("");
                  setActive(stage.key);
                }}
                mark={<StageMark stage={stage} />}
                label={t(stage.labelKey)}
              />
            ))}
            {orphans.length > 0 ? (
              <NavItem
                current={!matches && activeKey === OTHERS_KEY}
                pending={pendingOf(OTHERS_KEY)}
                onSelect={() => {
                  setSearch("");
                  setActive(OTHERS_KEY);
                }}
                mark={<Wrench className="size-4 shrink-0" />}
                label={t("cfg.section.others")}
              />
            ) : null}
          </ul>
        </nav>

        <div className="min-w-0 space-y-4">
          {matches ? (
            <div className="space-y-3">
              <p className="text-small text-muted-foreground">
                {plural("cfg.matches", matches.length, { term: search.trim() })}
              </p>
              {matches.map((setting) => (
                <div key={setting.key} className="space-y-1">
                  <HomeCaption setting={setting} />
                  <Row setting={setting} ctx={ctx} />
                </div>
              ))}
            </div>
          ) : activeKey === OTHERS_KEY ? (
            <section className="space-y-4">
              <StageHeader
                mark={<Wrench className="size-4" />}
                title={t("cfg.section.others")}
                description={t("cfg.section.othersDesc")}
              />
              <GroupCard
                title={null}
                settings={orphans}
                draft={draft}
                onChange={setValue}
                onReset={(key) => reset.mutate(key)}
                models={payload.models ?? null}
                offered={ctx.offered}
                levels={ctx.levels}
                onLevels={ctx.onLevels}
              />
            </section>
          ) : (
            <StageView
              key={activeKey}
              stage={stages.find((stage) => stage.key === activeKey)!}
              lane={lanes.get(activeKey) ?? null}
              lanes={payload.pipeline ?? []}
              settings={settingsOf(activeKey)}
              ctx={ctx}
              onGo={(key) => setActive(key)}
            />
          )}

          <DiffSummary settings={payload.settings} draft={draft} />
        </div>
      </div>

      <FormError error={save.error} />

      <div className="sticky bottom-0 flex items-center gap-2 rounded-lg border border-border bg-card p-3 shadow-raised">
        <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? <Spinner /> : <Save />}
          {t("common.save")}
        </Button>
        <Button variant="outline" disabled={!dirty} onClick={() => setDraft({})}>
          {t("common.discard")}
        </Button>
        {dirty ? (
          <span className="text-small text-muted-foreground">
            {plural("cfg.unsaved", Object.keys(draft).length)}
          </span>
        ) : null}
      </div>
    </div>
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
  lane,
  lanes,
  settings,
  ctx,
  onGo,
}: {
  stage: ConfigStage;
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
    <section className="space-y-4">
      <StageHeader
        mark={<StageMark stage={stage} />}
        title={t(stage.labelKey)}
        description={t(stage.descriptionKey)}
      />

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
    </section>
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
    <details className="group rounded-lg border border-border bg-card">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3">
        <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
        <span className="font-expanded text-body">{t("cfg.shared", { n: shared.length })}</span>
        <span className="text-small text-muted-foreground">{t("cfg.sharedDesc")}</span>
      </summary>
      <div className="space-y-5 border-t border-border p-4">
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
          <div key={home} className="space-y-2">
            <OwnerLink stageKey={home} onGo={onGo} />
            {loose
              .filter((setting) => homeOf(setting) === home)
              .map((setting) => (
                <Row key={setting.key} setting={setting} ctx={ctx} />
              ))}
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
      <CardContent className="space-y-3">
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
    <span className="flex size-4 shrink-0 items-center justify-center border border-current text-micro leading-none">
      {stage.number}
    </span>
  );
}

function StageHeader({
  mark,
  title,
  description,
}: {
  mark: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-muted/40 text-muted-foreground">
        {mark}
      </span>
      <div className="min-w-0">
        <h2 className="font-expanded text-heading">{title}</h2>
        <p className="text-small text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

function NavItem({
  current,
  pending,
  onSelect,
  mark,
  label,
}: {
  current: boolean;
  pending: number;
  onSelect: () => void;
  mark: ReactNode;
  label: string;
}) {
  return (
    <li className="shrink-0 lg:shrink">
      <button
        type="button"
        aria-current={current ? "true" : undefined}
        onClick={onSelect}
        className={cn(
          "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-body transition-colors",
          current
            ? "border-border bg-card text-foreground shadow-raised"
            : "border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground",
        )}
      >
        {mark}
        <span className="min-w-0 flex-1 truncate">{label}</span>
        {pending > 0 ? <Badge variant="attention">{pending}</Badge> : null}
      </button>
    </li>
  );
}

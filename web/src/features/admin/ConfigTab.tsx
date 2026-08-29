import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  FlaskConical,
  Hammer,
  RefreshCw,
  Save,
  ScanSearch,
  ScrollText,
  SlidersHorizontal,
  Tags,
  Wrench,
} from "lucide-react";
import { useState } from "react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Alert, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ReasoningLegend, ReasoningPipeline } from "@/features/admin/ReasoningPipeline";
import {
  DiffSummary,
  GroupCard,
  sameValue,
  SettingRow,
} from "@/features/admin/SettingFields";
import { useT, type Key } from "@/lib/i18n";
import type { ConfigPayload, ConfigSetting, ReasoningLane } from "@/lib/types";

const REASONING_GROUP = "Razonamiento";
const MODELS_GROUP = "Modelos";
const PHASE_MODEL_PREFIX = "models.phases.";
const OTHERS_KEY = "__otros__";
export const ENGINE_GROUPS = ["Motor", "Túnel SSH"]; // i18n-exempt
const CEREBRAS_KEYS = [
  "engine.cerebras_base_url",
  "engine.cerebras_api_key",
  "engine.cerebras_models",
];

type Section = {
  key: string;
  // A section built from a group the table below does not claim carries the server's own
  // name, which has no key: `labelKey` is null there and the raw string is drawn instead.
  label: string | null;
  labelKey: Key | null;
  icon: LucideIcon;
  descriptionKey: Key | null;
  groups: string[];
};

// The registry's groups, folded into destinations a person can hold in their head: one
// sub-page per question the configuration answers, not one flat list of 132 rows. The
// group names are the server's; a group nobody claims below still gets a page of its own,
// so a registry addition never disappears from the screen.
const SECTIONS: Section[] = [
  // Every `groups` entry is a REGISTRY group name, matched against what the server sends.
  // Translating one would stop it matching, which is why they are literals and the labels
  // beside them are keys.
  {
    key: "modelos",
    label: null,
    labelKey: "cfg.section.models",
    icon: Brain,
    descriptionKey: "cfg.section.modelsDesc",
    groups: [MODELS_GROUP, REASONING_GROUP],
  },
  {
    key: "muestreo",
    label: null,
    labelKey: "cfg.section.sampling",
    icon: SlidersHorizontal,
    descriptionKey: "cfg.section.samplingDesc",
    groups: ["Muestreo", "Ventana de contexto"], // i18n-exempt
  },
  {
    key: "constructores",
    label: null,
    labelKey: "cfg.section.builders",
    icon: Hammer,
    descriptionKey: "cfg.section.buildersDesc",
    groups: ["Constructores"],
  },
  {
    key: "recuperacion",
    label: null,
    labelKey: "cfg.section.retrieval",
    icon: ScanSearch,
    descriptionKey: "cfg.section.retrievalDesc",
    groups: ["Recuperación"], // i18n-exempt
  },
  {
    key: "generacion",
    label: null,
    labelKey: "cfg.section.generation",
    icon: Tags,
    descriptionKey: "cfg.section.generationDesc",
    groups: ["Etiquetado y generación"], // i18n-exempt
  },
  {
    key: "evaluacion",
    label: null,
    labelKey: "cfg.section.evaluation",
    icon: FlaskConical,
    descriptionKey: "cfg.section.evaluationDesc",
    groups: ["Evaluación"], // i18n-exempt
  },
  {
    key: "registro",
    label: null,
    labelKey: "cfg.section.logging",
    icon: ScrollText,
    descriptionKey: "cfg.section.loggingDesc",
    groups: ["Registro"],
  },
];

export function ConfigTab() {
  const tr = useT();
  const { t, plural } = tr;
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: ["admin", "config"], queryFn: api.adminConfig });
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [applied, setApplied] = useState<string[] | null>(null);
  const [active, setActive] = useState("motor");
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
  // row reads «por defecto» again rather than a file value that happens to equal it.
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
  const engineName = String(
    ("engine.name" in draft ? draft["engine.name"] : stored.get("engine.name")) ?? "ollama",
  );
  const hidden = new Set(engineName === "cerebras+ollama" ? [] : CEREBRAS_KEYS);
  const named = new Set(payload.groups);
  const orphans = payload.settings.filter(
    (setting) => !named.has(setting.group) && !ENGINE_GROUPS.includes(setting.group),
  );
  const byGroup = (group: string) =>
    payload.settings.filter((setting) => setting.group === group && !hidden.has(setting.key));
  // «Motor» and «Túnel SSH» moved to «Administración → Motor» on 2026-08-28, so that each
  // setting sits beside the thing it governs. They are claimed here WITHOUT a section, or
  // the unclaimed-group fallback below would helpfully hand them a page of their own again
  // and the move would silently undo itself.
  const claimed = new Set([...SECTIONS.flatMap((section) => section.groups), ...ENGINE_GROUPS]);
  const sections: Section[] = [
    ...SECTIONS,
    ...payload.groups
      .filter((group) => !claimed.has(group))
      .map((group) => ({
        key: `grupo:${group}`,
        label: group,
        labelKey: null,
        icon: Wrench,
        descriptionKey: null,
        groups: [group],
      })),
    ...(orphans.length > 0
      ? [
          {
            key: OTHERS_KEY,
            label: null,
            labelKey: "cfg.section.others" as Key,
            icon: Wrench,
            descriptionKey: "cfg.section.othersDesc" as Key,
            groups: [],
          },
        ]
      : []),
  ].filter((section) =>
    section.key === OTHERS_KEY
      ? true
      : section.groups.some((group) => byGroup(group).length > 0),
  );
  const settingsOf = (section: Section) =>
    section.key === OTHERS_KEY ? orphans : section.groups.flatMap(byGroup);

  const setValue = (key: string, value: unknown) =>
    setDraft((prev) => {
      if (sameValue(value, stored.get(key))) {
        const { [key]: _dropped, ...rest } = prev;
        return rest;
      }
      return { ...prev, [key]: value };
    });
  const dirty = Object.keys(draft).length > 0;
  const pendingOf = (section: Section) => {
    const keys = new Set(settingsOf(section).map((setting) => setting.key));
    return Object.keys(draft).filter((key) => keys.has(key)).length;
  };

  const activeSection = sections.find((section) => section.key === active) ?? sections[0];
  const term = search.trim().toLowerCase();
  const matches = term
    ? payload.settings.filter((setting) =>
        `${setting.name} ${setting.key} ${setting.group}`.toLowerCase().includes(term),
      )
    : null;

  const row = (setting: ConfigSetting) => (
    <SettingRow
      key={setting.key}
      setting={setting}
      value={setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default)}
      onChange={(next) => setValue(setting.key, next)}
      onReset={() => reset.mutate(setting.key)}
      models={payload.models ?? null}
    />
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-small text-muted-foreground">
          {t("cfg.intro")}
        </p>
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
            {sections.map((section) => {
              const pending = pendingOf(section);
              const current = !matches && section.key === activeSection.key;
              return (
                <li key={section.key} className="shrink-0 lg:shrink">
                  <button
                    type="button"
                    aria-current={current ? "true" : undefined}
                    onClick={() => {
                      setSearch("");
                      setActive(section.key);
                    }}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-body transition-colors",
                      current
                        ? "border-border bg-card text-foreground shadow-raised"
                        : "border-transparent text-muted-foreground hover:bg-muted/50 hover:text-foreground",
                    )}
                  >
                    <section.icon className="size-4 shrink-0" />
                    <span className="min-w-0 flex-1 truncate">
                      {section.labelKey ? t(section.labelKey) : section.label}
                    </span>
                    {pending > 0 ? <Badge variant="attention">{pending}</Badge> : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="min-w-0 space-y-4">
          {matches ? (
            <div className="space-y-3">
              <p className="text-small text-muted-foreground">
                {plural("cfg.matches", matches.length, { term: search.trim() })}
              </p>
              {matches.map(row)}
            </div>
          ) : (
            <section key={activeSection.key} className="space-y-4">
              <div className="flex items-start gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-muted/40 text-muted-foreground">
                  <activeSection.icon className="size-4" />
                </span>
                <div className="min-w-0">
                  <h2 className="font-expanded text-heading">
                    {activeSection.labelKey ? t(activeSection.labelKey) : activeSection.label}
                  </h2>
                  {activeSection.descriptionKey ? (
                    <p className="text-small text-muted-foreground">
                      {t(activeSection.descriptionKey)}
                    </p>
                  ) : null}
                </div>
              </div>

              {activeSection.groups.includes(MODELS_GROUP) ? (
                <PipelineCard
                  lanes={payload.pipeline ?? []}
                  settings={payload.settings}
                  draft={draft}
                  models={payload.models ?? null}
                  onChange={setValue}
                  onReset={(key) => reset.mutate(key)}
                />
              ) : activeSection.key === OTHERS_KEY ? (
                <GroupCard
                  title={null}
                  settings={orphans}
                  draft={draft}
                  onChange={setValue}
                  onReset={(key) => reset.mutate(key)}
                  models={payload.models ?? null}
                />
              ) : (
                activeSection.groups
                  .filter((group) => byGroup(group).length > 0)
                  .map((group) => (
                    <GroupCard
                      key={group}
                      title={activeSection.groups.length > 1 ? group : null}
                      settings={byGroup(group)}
                      draft={draft}
                      onChange={setValue}
                      onReset={(key) => reset.mutate(key)}
                      models={payload.models ?? null}
                    />
                  ))
              )}
            </section>
          )}

          {"engine.name" in draft ? (
            <Alert tone="attention" title={t("cfg.engineChange")}>
              {t("cfg.engineChangeBody", {
                next: String(draft["engine.name"]),
                current: String(stored.get("engine.name")),
              })}
            </Alert>
          ) : null}

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

function PipelineCard({
  lanes,
  settings,
  draft,
  models,
  onChange,
  onReset,
}: {
  lanes: ReasoningLane[];
  settings: ConfigSetting[];
  draft: Record<string, unknown>;
  models: ConfigPayload["models"] | null;
  onChange: (key: string, value: unknown) => void;
  onReset: (key: string) => void;
}) {
  const { t } = useT();
  const phases = lanes.flatMap((lane) => lane.phases);
  const drawn = new Set([
    ...phases.map((phase) => phase.setting),
    ...phases.map((phase) => phase.effort),
    ...phases.map((phase) => phase.model).filter((key) => key.startsWith(PHASE_MODEL_PREFIX)),
  ]);
  const ofGroups = settings.filter(
    (setting) => setting.group === MODELS_GROUP || setting.group === REASONING_GROUP,
  );
  const residents = ofGroups.filter(
    (setting) => setting.group === MODELS_GROUP && !drawn.has(setting.key),
  );
  const rest = ofGroups.filter(
    (setting) => setting.group === REASONING_GROUP && !drawn.has(setting.key),
  );
  const inNodes = ofGroups.filter((setting) => drawn.has(setting.key));
  const current = (setting: ConfigSetting) =>
    setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default);
  const row = (setting: ConfigSetting) => (
    <SettingRow
      key={setting.key}
      setting={setting}
      value={current(setting)}
      onChange={(next) => onChange(setting.key, next)}
      onReset={() => onReset(setting.key)}
      models={models}
    />
  );

  return (
    <Card>
      <CardContent className="space-y-4 pt-4">
        {residents.map(row)}
        <p className="max-w-2xl text-small text-muted-foreground">
          {t("cfg.pipelineNote")}
        </p>
        <ReasoningPipeline
          lanes={lanes}
          settings={settings}
          draft={draft}
          models={models}
          onChange={onChange}
        />
        <ReasoningLegend />
        {inNodes.length > 0 ? (
          <details className="text-small text-muted-foreground">
            <summary className="cursor-pointer select-none">{t("cfg.whyEachNode")}</summary>
            <dl className="mt-2 space-y-3">
              {inNodes
                .filter((setting) => setting.doc && setting.name)
                .map((setting) => (
                  <div key={setting.key}>
                    <dt className="font-mono text-foreground">{setting.name}</dt>
                    <dd className="mt-0.5 whitespace-pre-wrap">{setting.doc}</dd>
                  </div>
                ))}
            </dl>
          </details>
        ) : null}
        {rest.map(row)}
      </CardContent>
    </Card>
  );
}

/** The settings whose value is a model name: the three residents and every phase override. */

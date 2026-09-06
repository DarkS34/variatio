import { useQuery } from "@tanstack/react-query";
import { Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { FormError } from "@/features/auth/AuthLayout";
import { DiffSummary, SettingRow, useConfigDraft } from "@/features/admin/SettingFields";
import { api } from "@/lib/api";
import { useT, type Key } from "@/lib/i18n";
import type { ConfigPayload, ConfigSetting } from "@/lib/types";

/* The engine's own settings, on the engine's own tab, so each sits beside the meter that
   says what it does: the local ones beside the GPU, the Cerebras ones beside the quota.
   That is what the two columns of this tab encode — the left one measures, the right sets.

   Addressed by KEY and not by group: the registry's "Motor" group spans both halves, so
   splitting by group puts the remote quota's ceilings under the local GPU. */
export const LOCAL_KEYS = [
  "engine.name",
  "engine.ollama_host",
  "engine.idle_unload_seconds",
  "engine.idle_unload_poll_seconds",
];

export const REMOTE_KEYS = [
  "engine.cerebras_base_url",
  "engine.cerebras_api_key",
  "engine.cerebras_models",
  "engine.cerebras_max_requests_minute",
  "engine.cerebras_max_tokens_minute",
  "engine.cerebras_max_requests_day",
  "engine.cerebras_max_tokens_day",
  "engine.cerebras_max_wait_seconds",
  // Last of the remote half, and the odd one out: the four above bound what the account may
  // SPEND, this one bounds how many jobs may spend it at once. It belongs here rather than
  // beside the local GPU because the GPU's own capacity is one and is not a setting.
  "engine.cerebras_max_concurrent_jobs",
];

const TUNNEL_GROUP = "Túnel SSH"; // i18n-exempt: the registry's own group name

export type EngineSettings = ReturnType<typeof useEngineSettings>;

export function useEngineSettings() {
  const query = useQuery({ queryKey: ["admin", "config"], queryFn: api.adminConfig });
  const payload: ConfigPayload | undefined = query.data;
  const stored = new Map(
    (payload?.settings ?? []).map((s) => [s.key, s.value ?? s.default] as const),
  );
  const config = useConfigDraft(stored);

  const pick = (keys: string[]) =>
    keys
      .map((key) => (payload?.settings ?? []).find((s) => s.key === key))
      .filter((s): s is ConfigSetting => Boolean(s));

  return {
    ...config,
    loading: query.isLoading,
    payload,
    stored,
    local: pick(LOCAL_KEYS),
    remote: pick(REMOTE_KEYS),
    tunnel: (payload?.settings ?? []).filter((s) => s.group === TUNNEL_GROUP),
  };
}

/* A settings card is drawn as a CONTROL and never as one more report: the ink rule down its
   leading edge is what separates it, at a glance, from the measuring cards it sits beside —
   the same distinction the screens elsewhere make by not putting a control and a report on
   one line. */
export function SettingsPanel({
  titleKey,
  noteKey,
  settings,
  config,
}: {
  titleKey: Key;
  noteKey: Key;
  settings: ConfigSetting[];
  config: EngineSettings;
}) {
  const { t } = useT();
  if (config.loading) return <Skeleton className="h-64" />;
  if (settings.length === 0) return null;

  return (
    <Card className="border-l-2 border-l-primary">
      <CardHeader className="pb-3">
        <CardTitle>{t(titleKey)}</CardTitle>
        <CardDescription>{t(noteKey)}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {settings.map((setting) => (
          <SettingRow
            key={setting.key}
            setting={setting}
            value={config.valueOf(setting)}
            onChange={(next) => config.change(setting.key, next)}
            onReset={() => config.reset.mutate(setting.key)}
            models={config.payload?.models ?? null}
          />
        ))}
      </CardContent>
    </Card>
  );
}

/* One bar for the whole tab, not one per card: what is pending is pending for the engine,
   and two save buttons on one screen is two ways to leave half a change behind. */
export function EngineSaveBar({ config }: { config: EngineSettings }) {
  const { t, plural } = useT();
  const engineChanged = "engine.name" in config.draft;

  return (
    <div className="space-y-3">
      {engineChanged ? (
        <Alert tone="attention" title={t("cfg.engineChange")}>
          {t("cfg.engineChangeBody", {
            next: String(config.draft["engine.name"]),
            current: String(config.stored.get("engine.name")),
          })}
        </Alert>
      ) : null}
      <DiffSummary settings={config.payload?.settings ?? []} draft={config.draft} />
      <FormError error={config.save.error} />
      <div className="sticky bottom-0 flex items-center gap-2 border border-border bg-card p-3 shadow-raised">
        <Button
          disabled={!config.dirty || config.save.isPending}
          onClick={() => config.save.mutate()}
        >
          {config.save.isPending ? <Spinner /> : <Save />}
          {t("common.save")}
        </Button>
        <Button variant="outline" disabled={!config.dirty} onClick={config.discard}>
          {t("common.discard")}
        </Button>
        {config.dirty ? (
          <span className="text-small text-muted-foreground">
            {plural("cfg.unsaved", Object.keys(config.draft).length)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

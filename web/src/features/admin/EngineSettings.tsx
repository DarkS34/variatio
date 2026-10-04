import { useQuery } from "@tanstack/react-query";
import { Save, Undo2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { FormError } from "@/features/auth/AuthLayout";
import {
  canReset,
  DiffSummary,
  formatValue,
  SETTING_LIST,
  SettingRow,
  useConfigDraft,
} from "@/features/admin/SettingFields";
import { api } from "@/lib/api";
import { useT, type Key } from "@/lib/i18n";
import type { ConfigPayload, ConfigSetting } from "@/lib/types";
import { cn } from "@/lib/utils";

/* The engine's own settings, on the engine's own tab, so each sits with the meter that
   says what it does: the choice of engine on "General", the local ones under the GPU, the
   Cerebras ones under the quota.

   Addressed by KEY and not by group: the registry's "Motor" group spans every screen, so
   splitting by group puts the remote quota's ceilings under the local GPU. */
const ENGINE_KEYS = ["engine.name"];

export const LOCAL_KEYS = [
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
    engine: pick(ENGINE_KEYS),
    local: pick(LOCAL_KEYS),
    remote: pick(REMOTE_KEYS),
    tunnel: (payload?.settings ?? []).filter((s) => s.group === TUNNEL_GROUP),
  };
}

/* A settings card is a CONTROL and never one more report: it is a block of its own, under
   the readings it governs — the same distinction the screens elsewhere make by not putting
   a control and a report on one line.

   WHAT THE PANEL CANNOT CHANGE IS NOT DRAWN AT ALL. A value the environment fixes, or one
   read from the file at start-up, is nothing an administrator can act on from here: on an
   installation configured from `.env` it was seven rows of disabled fields. A card left
   with nothing to set is not drawn either. */
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
  const open = settings.filter(changeable);
  if (open.length === 0) return null;
  const ceilings = open.filter((setting) => setting.key in CEILINGS);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>{t(titleKey)}</CardTitle>
        <CardDescription>{t(noteKey)}</CardDescription>
      </CardHeader>
      <CardContent className={SETTING_LIST}>
        {open.map((setting) =>
          setting.key in CEILINGS ? (
            setting === ceilings[0] ? (
              <Ceilings key="ceilings" settings={ceilings} config={config} />
            ) : null
          ) : (
            <SettingRow
              key={setting.key}
              setting={setting}
              value={config.valueOf(setting)}
              onChange={(next) => config.change(setting.key, next)}
              onReset={() => config.reset.mutate(setting.key)}
              models={config.payload?.models ?? null}
            />
          ),
        )}
      </CardContent>
    </Card>
  );
}

/** Whether the panel may write this setting: the registry allows it and no variable pins it. */
function changeable(setting: ConfigSetting): boolean {
  return setting.editable && setting.source !== "env";
}

/* The four ceilings of the quota are the limits of the four meters beside them, so they are
   set in the meters' own arrangement and under the meters' own names: minute over day,
   requests before tokens. Four boxed rows named after their variables said the same thing
   in four times the height, and left matching each to its meter to the reader. The
   variable's name stays one hover away. */
const CEILINGS: Record<string, Key> = {
  "engine.cerebras_max_requests_minute": "cere.meter.requestsMinute",
  "engine.cerebras_max_tokens_minute": "cere.meter.tokensMinute",
  "engine.cerebras_max_requests_day": "cere.meter.requestsDay",
  "engine.cerebras_max_tokens_day": "cere.meter.tokensDay",
};

function Ceilings({ settings, config }: { settings: ConfigSetting[]; config: EngineSettings }) {
  const { t } = useT();
  return (
    // A group and not a fieldset: a legend sits on its fieldset's edge, outside the padding
    // the list gives each of its rows.
    <div role="group" aria-labelledby="engine-ceilings" className="space-y-3">
      <p id="engine-ceilings" className="text-micro font-condensed uppercase text-muted-foreground">
        {t("eng.cfg.ceilings")}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {settings.map((setting) => (
          <CeilingField key={setting.key} setting={setting} config={config} />
        ))}
      </div>
    </div>
  );
}

/* A ceiling has a ceiling of its own: what the account admits, declared in the registry.
   A number typed above it is brought down to it as it is typed — the API would refuse the
   save anyway, and a field that takes 451 only to fail later teaches nothing. */
function CeilingField({ setting, config }: { setting: ConfigSetting; config: EngineSettings }) {
  const { t, language } = useT();
  const id = `config-${setting.key}`;
  const value = config.valueOf(setting);
  const pending = setting.key in config.draft;
  const maximum = setting.maximum ?? null;

  return (
    <div className="space-y-1" title={setting.name || setting.key}>
      <Label htmlFor={id}>{t(CEILINGS[setting.key])}</Label>
      <div className="flex items-center gap-1">
        <Input
          id={id}
          type="number"
          min={setting.minimum ?? undefined}
          max={maximum ?? undefined}
          step={1}
          aria-describedby={maximum === null ? undefined : `${id}-max`}
          value={value === null || value === undefined ? "" : String(value)}
          onChange={(event) => {
            const raw = event.target.value;
            if (raw === "") {
              config.change(setting.key, null);
              return;
            }
            const num = Number.parseInt(raw, 10);
            if (Number.isNaN(num)) return;
            config.change(setting.key, maximum === null ? num : Math.min(num, maximum));
          }}
          className={cn("nums", pending && "border-attention ring-1 ring-attention")}
        />
        {canReset(setting) ? (
          <Button
            variant="ghost"
            size="icon-sm"
            title={t("cfg.backTo", { value: formatValue(setting.default, t) })}
            aria-label={t("cfg.backTo", { value: formatValue(setting.default, t) })}
            onClick={() => config.reset.mutate(setting.key)}
          >
            <Undo2 />
          </Button>
        ) : null}
      </div>
      {maximum === null ? null : (
        <p id={`${id}-max`} className="nums text-small text-muted-foreground">
          {t("eng.cfg.ceilingMax", { n: maximum.toLocaleString(language) })}
        </p>
      )}
    </div>
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
      <div className="sticky bottom-3 flex items-center gap-2 rounded-inner bg-popover p-3 shadow-overlay">
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

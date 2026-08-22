import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Save } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Alert, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import type { ConfigImpact, ConfigPayload, ConfigSetting, ConfigSource } from "@/lib/types";

const SOURCE_LABELS: Record<ConfigSource, string> = {
  default: "por defecto",
  file: "en el fichero",
  env: "fijado por el entorno",
};

// Not tuning knobs of the same kind: `reindex` says so in its own message ("invalidará los
// contextos Y..."), which is why it outranks `contexts` rather than sitting beside it.
// `none` and `locked` carry no save-time warning of their own — nothing in the contract
// says what one would read — so they simply never win the highest-severity comparison.
const IMPACT_SEVERITY: Record<ConfigImpact, number> = {
  none: 0,
  engine: 1,
  contexts: 2,
  reindex: 3,
  locked: 4,
};

const IMPACT_MESSAGES: Partial<Record<ConfigImpact, string>> = {
  contexts: "Invalidará los contextos calientes; el próximo trabajo los reconstruye.",
  reindex: "Invalidará los contextos y volverá a embeber el índice de conceptos.",
  engine: "Reiniciará la conexión con el motor de inferencia.",
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "boolean") return value ? "activado" : "desactivado";
  return String(value);
}

export function ConfigTab() {
  const client = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: ["admin", "config"], queryFn: api.adminConfig });
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [applied, setApplied] = useState<string[] | null>(null);

  const invalidate = () => client.invalidateQueries({ queryKey: ["admin", "config"] });

  const save = useMutation({
    mutationFn: () => api.updateAdminConfig(draft),
    onSuccess: (payload) => {
      setDraft({});
      setApplied(payload.applied ?? null);
      invalidate();
      toast({ title: "Configuración guardada" });
    },
  });

  const reload = useMutation({
    mutationFn: () => api.reloadAdminConfig(),
    onSuccess: (payload) => {
      setApplied(payload.applied ?? null);
      invalidate();
      toast({ title: "Recargado desde el fichero" });
    },
  });

  if (query.isLoading) return <Skeleton className="h-96" />;
  if (!query.data) return null;
  const payload: ConfigPayload = query.data;

  const named = new Set(payload.groups);
  const orphans = payload.settings.filter((setting) => !named.has(setting.group));
  const setValue = (key: string, value: unknown) =>
    setDraft((prev) => ({ ...prev, [key]: value }));
  const dirty = Object.keys(draft).length > 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-small text-muted-foreground">
          Lo que la instalación tiene configurado ahora mismo: por defecto, desde el fichero o
          fijado por el entorno. Lo fijado por el entorno gana siempre, así que no se puede
          editar desde aquí.
        </p>
        <Button variant="outline" onClick={() => reload.mutate()} disabled={reload.isPending}>
          {reload.isPending ? <Spinner /> : <RefreshCw />}
          Recargar desde el fichero
        </Button>
      </div>

      <FormError error={reload.error} />
      {applied && applied.length > 0 ? (
        <Alert tone="settled" title="Aplicado">
          <ul className="list-disc space-y-0.5 pl-5">
            {applied.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      {payload.groups.map((group) => (
        <GroupCard
          key={group}
          title={group}
          settings={payload.settings.filter((setting) => setting.group === group)}
          draft={draft}
          onChange={setValue}
        />
      ))}

      {orphans.length > 0 ? (
        <GroupCard title="Otros" settings={orphans} draft={draft} onChange={setValue} />
      ) : null}

      <DiffSummary settings={payload.settings} draft={draft} />

      <FormError error={save.error} />

      <div className="sticky bottom-0 flex items-center gap-2 rounded-lg border border-border bg-card p-3 shadow-raised">
        <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? <Spinner /> : <Save />}
          Guardar
        </Button>
        <Button variant="outline" disabled={!dirty} onClick={() => setDraft({})}>
          Descartar
        </Button>
        {dirty ? (
          <span className="text-small text-muted-foreground">
            {Object.keys(draft).length} cambio(s) sin guardar
          </span>
        ) : null}
      </div>
    </div>
  );
}

function GroupCard({
  title,
  settings,
  draft,
  onChange,
}: {
  title: string;
  settings: ConfigSetting[];
  draft: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {settings.map((setting) => (
          <SettingRow
            key={setting.key}
            setting={setting}
            value={setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default)}
            onChange={(next) => onChange(setting.key, next)}
          />
        ))}
      </CardContent>
    </Card>
  );
}

function SettingRow({
  setting,
  value,
  onChange,
}: {
  setting: ConfigSetting;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  const label = setting.name || setting.key;
  const id = `config-${setting.key}`;
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {setting.secret ? (
            <div className="flex items-center justify-between gap-2">
              <span className="text-body">{label}</span>
              <Badge variant="outline">
                {setting.state === "configurada" ? "Configurada" : "Ausente"}
              </Badge>
            </div>
          ) : setting.kind === "bool" ? (
            <div className="flex items-center justify-between gap-2">
              <span className="text-body">{label}</span>
              <Switch
                checked={Boolean(value)}
                disabled={disabled}
                onCheckedChange={onChange}
                label={label}
              />
            </div>
          ) : setting.choices ? (
            <div className="space-y-1">
              <Label htmlFor={id}>{label}</Label>
              <Select
                id={id}
                value={String(value ?? "")}
                disabled={disabled}
                onChange={(event) => onChange(event.target.value)}
              >
                {setting.choices.map((choice) => (
                  <option key={choice} value={choice}>
                    {choice}
                  </option>
                ))}
              </Select>
            </div>
          ) : setting.kind === "int" || setting.kind === "float" ? (
            <div className="space-y-1">
              <Label htmlFor={id}>{label}</Label>
              <Input
                id={id}
                type="number"
                min={setting.minimum ?? undefined}
                max={setting.maximum ?? undefined}
                step={setting.kind === "float" ? "any" : 1}
                disabled={disabled}
                value={value === null || value === undefined ? "" : String(value)}
                onChange={(event) => {
                  const raw = event.target.value;
                  if (raw === "") {
                    onChange(null);
                    return;
                  }
                  const num = setting.kind === "int" ? Number.parseInt(raw, 10) : Number(raw);
                  if (Number.isNaN(num)) return;
                  onChange(num);
                }}
              />
            </div>
          ) : setting.kind === "list[str]" ? (
            <div className="space-y-1">
              <Label htmlFor={id}>{label}</Label>
              <Input
                id={id}
                disabled={disabled}
                value={Array.isArray(value) ? value.join(", ") : String(value ?? "")}
                onChange={(event) =>
                  onChange(
                    event.target.value
                      .split(",")
                      .map((part) => part.trim())
                      .filter(Boolean),
                  )
                }
              />
              <p className="text-small text-muted-foreground">Sepáralos con comas.</p>
            </div>
          ) : (
            <div className="space-y-1">
              <Label htmlFor={id}>{label}</Label>
              <Input
                id={id}
                disabled={disabled}
                value={String(value ?? "")}
                onChange={(event) => onChange(event.target.value)}
              />
            </div>
          )}
        </div>
        <Badge variant={setting.source === "file" ? "secondary" : "outline"}>
          {SOURCE_LABELS[setting.source]}
        </Badge>
      </div>

      {lockedByEnv ? (
        <p className="text-small text-muted-foreground">Lo fija {setting.env}.</p>
      ) : null}

      {setting.doc ? (
        <details className="text-small text-muted-foreground">
          <summary className="cursor-pointer select-none">Por qué este valor</summary>
          <p className="mt-1 whitespace-pre-wrap">{setting.doc}</p>
        </details>
      ) : null}
    </div>
  );
}

function DiffSummary({
  settings,
  draft,
}: {
  settings: ConfigSetting[];
  draft: Record<string, unknown>;
}) {
  const touched = settings.filter((setting) => setting.key in draft);
  if (touched.length === 0) return null;

  const highest = touched.reduce<ConfigImpact>(
    (acc, setting) => (IMPACT_SEVERITY[setting.impact] > IMPACT_SEVERITY[acc] ? setting.impact : acc),
    "none",
  );
  const warning = IMPACT_MESSAGES[highest];

  return (
    <div className="space-y-2 rounded-md border border-border bg-muted/30 p-3">
      <p className="text-small font-medium uppercase tracking-wide text-muted-foreground">
        Cambios pendientes ({touched.length})
      </p>
      <ul className="space-y-1 text-body">
        {touched.map((setting) => (
          <li key={setting.key} className="flex flex-wrap items-baseline gap-1.5">
            <span className="font-medium">{setting.name || setting.key}</span>
            <span className="text-muted-foreground">
              {formatValue(setting.value ?? setting.default)} → {formatValue(draft[setting.key])}
            </span>
          </li>
        ))}
      </ul>
      {warning ? (
        <Alert tone="attention" title="Antes de guardar">
          <p>{warning}</p>
        </Alert>
      ) : null}
    </div>
  );
}

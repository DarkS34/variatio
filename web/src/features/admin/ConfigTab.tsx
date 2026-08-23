import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Save, Undo2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Alert, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { bytes } from "@/lib/format";
import { ReasoningLegend, ReasoningPipeline } from "@/features/admin/ReasoningPipeline";
import type {
  ConfigImpact,
  ConfigPayload,
  ConfigSetting,
  ConfigSource,
  InstalledModel,
  ReasoningLane,
} from "@/lib/types";

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

function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if ((a ?? null) === null || (b ?? null) === null) return (a ?? null) === (b ?? null);
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((item, index) => sameValue(item, b[index]));
  }
  if (typeof a === "object" && typeof b === "object") {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  return false;
}

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
      toast({ title: "Valor por defecto restablecido" });
    },
    onError: (error: Error) =>
      toast({ title: "No se ha podido restablecer", description: error.message, tone: "danger" }),
  });

  if (query.isLoading) return <Skeleton className="h-96" />;
  if (!query.data) return null;
  const payload: ConfigPayload = query.data;

  const named = new Set(payload.groups);
  const orphans = payload.settings.filter((setting) => !named.has(setting.group));
  const stored = new Map(
    payload.settings.map((setting) => [setting.key, setting.value ?? setting.default]),
  );
  const setValue = (key: string, value: unknown) =>
    setDraft((prev) => {
      if (sameValue(value, stored.get(key))) {
        const { [key]: _dropped, ...rest } = prev;
        return rest;
      }
      return { ...prev, [key]: value };
    });
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

      {payload.groups.map((group) =>
        group === REASONING_GROUP ? null : group === MODELS_GROUP ? (
          <PipelineCard
            key={group}
            lanes={payload.pipeline ?? []}
            settings={payload.settings}
            draft={draft}
            models={payload.models ?? null}
            onChange={setValue}
            onReset={(key) => reset.mutate(key)}
          />
        ) : (
          <GroupCard
            key={group}
            title={group}
            settings={payload.settings.filter((setting) => setting.group === group)}
            draft={draft}
            onChange={setValue}
            onReset={(key) => reset.mutate(key)}
            models={payload.models ?? null}
          />
        ),
      )}

      {orphans.length > 0 ? (
        <GroupCard
          title="Otros"
          settings={orphans}
          draft={draft}
          onChange={setValue}
          onReset={(key) => reset.mutate(key)}
          models={payload.models ?? null}
        />
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
  onReset,
  models,
}: {
  title: string;
  settings: ConfigSetting[];
  draft: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  onReset: (key: string) => void;
  models: ConfigPayload["models"] | null;
}) {
  const current = (setting: ConfigSetting) =>
    setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default);
  const resident = settings.some((s) => s.key === "models.main") && models ? (
    <ResidencySummary
      settings={settings}
      current={current}
      models={models}
    />
  ) : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {resident}
        {settings.map((setting) => (
          <SettingRow
            key={setting.key}
            setting={setting}
            value={current(setting)}
            onChange={(next) => onChange(setting.key, next)}
            onReset={() => onReset(setting.key)}
            models={models}
          />
        ))}
      </CardContent>
    </Card>
  );
}

const REASONING_GROUP = "Razonamiento";
const MODELS_GROUP = "Modelos";
const PHASE_MODEL_PREFIX = "models.phases.";

// One card for the two groups the pipeline drawing already covers: the three residents as
// rows, then every phase as a node carrying BOTH its model and its reasoning switch, so a
// phase's two decisions are taken in one place. What neither the rows nor the nodes show
// (THINK_EFFORT) keeps its row below; what the nodes do show never gets a second row.
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
  const phases = lanes.flatMap((lane) => lane.phases);
  const drawn = new Set([
    ...phases.map((phase) => phase.setting),
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
  const pendingResets = inNodes.filter(
    (setting) =>
      setting.source === "file" && !setting.secret && !sameValue(setting.value, setting.default),
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle>Modelos y razonamiento</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {models ? <ResidencySummary settings={ofGroups} current={current} models={models} /> : null}
        {residents.map(row)}
        <p className="max-w-2xl text-small text-muted-foreground">
          Cada pista es una construcción; cada nodo, una llamada al modelo. Bajo cada nodo,
          qué modelo la atiende («principal» sigue a {residents.find((s) => s.key === "models.main")?.name ?? "LLM_MAIN"});
          el círculo dice si razona antes de contestar. Razonar y una gramática no conviven en
          esta pila, así que encender una fase que hoy responde con gramática se la quita y deja
          la forma en manos del analizador y de la reparación. Tres nodos no dependen de un
          ajuste: el guardián no razona, la variante la decide cada encargo y la reparación es
          su propia gramática.
        </p>
        <ReasoningPipeline
          lanes={lanes}
          settings={settings}
          draft={draft}
          models={models}
          onChange={onChange}
        />
        <ReasoningLegend />
        {pendingResets.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5 text-small text-muted-foreground">
            <span>Fijados en el fichero:</span>
            {pendingResets.map((setting) => (
              <Button
                key={setting.key}
                variant="ghost"
                size="sm"
                title={`Volver a ${formatValue(setting.default)}`}
                onClick={() => onReset(setting.key)}
              >
                <Undo2 />
                {setting.name}
              </Button>
            ))}
          </div>
        ) : null}
        {inNodes.length > 0 ? (
          <details className="text-small text-muted-foreground">
            <summary className="cursor-pointer select-none">Por qué cada nodo</summary>
            <dl className="mt-2 space-y-3">
              {inNodes
                .filter((setting) => setting.doc)
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
function isModelSetting(setting: ConfigSetting): boolean {
  return setting.key.startsWith("models.") && setting.kind === "str";
}

const OTHER = "__other__";

// The choice is among what the engine has on disk, because a name typed by hand is a typo
// waiting for the first call. «Otro…» keeps the free text for a model not pulled yet, and
// a phase keeps «Seguir al principal» (null) as its first option, which is what every
// override defaults to.
function ModelSelect({
  id,
  label,
  setting,
  value,
  disabled,
  models,
  onChange,
}: {
  id: string;
  label: string;
  setting: ConfigSetting;
  value: string | null;
  disabled: boolean;
  models: ConfigPayload["models"];
  onChange: (next: unknown) => void;
}) {
  const installed = models.installed;
  const known = installed.some((m) => m.model === value);
  const [other, setOther] = useState(() => Boolean(value) && !known);
  const residentVram = new Map(models.running.map((m) => [m.model, m.size_vram]));

  const describe = (model: InstalledModel) => {
    const vram = residentVram.get(model.model);
    if (vram) return `${model.model} — cargado, ${bytes(vram)} en VRAM`;
    return model.size ? `${model.model} — en disco, ${bytes(model.size)}` : model.model;
  };

  const selectValue = other ? OTHER : value ?? "";

  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Select
        id={id}
        value={selectValue}
        disabled={disabled}
        onChange={(event) => {
          const next = event.target.value;
          if (next === OTHER) {
            setOther(true);
            return;
          }
          setOther(false);
          onChange(next === "" ? null : next);
        }}
      >
        {setting.nullable ? <option value="">Seguir al principal</option> : null}
        {value && !known && !other ? <option value={value}>{value} — sin instalar</option> : null}
        {installed.map((model) => (
          <option key={model.model} value={model.model}>
            {describe(model)}
          </option>
        ))}
        <option value={OTHER}>Otro…</option>
      </Select>
      {other ? (
        <Input
          aria-label={`${label}: nombre del modelo`}
          placeholder="nombre:etiqueta, tal como lo conoce Ollama"
          disabled={disabled}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value || null)}
        />
      ) : null}
      {installed.length === 0 ? (
        <p className="text-small text-muted-foreground">
          El motor no responde: no se puede listar lo instalado, pero el nombre se puede escribir.
        </p>
      ) : null}
    </div>
  );
}

// The co-residency arithmetic, on screen: the three models the process keeps loaded, with
// what each one measures now (`/api/ps`, the only true reading) or, failing that, its size
// on disk, which is an approximation and is labelled as one. It is a sum and not a verdict:
// the VRAM total of the machine is not something this process can read from here.
function ResidencySummary({
  settings,
  current,
  models,
}: {
  settings: ConfigSetting[];
  current: (setting: ConfigSetting) => unknown;
  models: ConfigPayload["models"];
}) {
  const residents = ["models.main", "models.guardrail", "models.embedding"]
    .map((key) => settings.find((s) => s.key === key))
    .filter((s): s is ConfigSetting => Boolean(s))
    .map((s) => String(current(s) ?? ""))
    .filter(Boolean);
  const vram = new Map(models.running.map((m) => [m.model, m.size_vram]));
  const disk = new Map(models.installed.map((m) => [m.model, m.size]));

  let total = 0;
  let estimated = false;
  let unknown = 0;
  const rows = residents.map((name) => {
    const measured = vram.get(name);
    if (measured) {
      total += measured;
      return { name, text: `${bytes(measured)} en VRAM` };
    }
    const onDisk = disk.get(name);
    if (onDisk) {
      total += onDisk;
      estimated = true;
      return { name, text: `≈ ${bytes(onDisk)} (tamaño en disco)` };
    }
    unknown += 1;
    return { name, text: "sin instalar" };
  });

  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 text-small">
      <p className="font-medium uppercase tracking-wide text-muted-foreground">
        Residentes a la vez
      </p>
      <ul className="mt-1 space-y-0.5">
        {rows.map((row) => (
          <li key={row.name} className="flex flex-wrap justify-between gap-2">
            <span className="font-mono">{row.name}</span>
            <span className="text-muted-foreground nums">{row.text}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 nums">
        Suma: <strong>{bytes(total)}</strong>
        {estimated ? " — parte estimada por el tamaño en disco; el KV cache va aparte" : ""}
        {unknown > 0 ? ` — ${unknown} modelo(s) sin tamaño conocido` : ""}
      </p>
    </div>
  );
}

function SettingRow({
  setting,
  value,
  onChange,
  onReset,
  models,
}: {
  setting: ConfigSetting;
  value: unknown;
  onChange: (next: unknown) => void;
  onReset: () => void;
  models: ConfigPayload["models"] | null;
}) {
  const label = setting.name || setting.key;
  const id = `config-${setting.key}`;
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;
  // Only a value that actually left the default has anything to go back to; a file value
  // equal to the default is the same number with a different badge.
  const resettable =
    setting.source === "file" && !setting.secret && !sameValue(setting.value, setting.default);

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
          ) : models && isModelSetting(setting) ? (
            <ModelSelect
              id={id}
              label={label}
              setting={setting}
              value={value as string | null}
              disabled={disabled}
              models={models}
              onChange={onChange}
            />
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
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Badge variant={setting.source === "file" ? "secondary" : "outline"}>
            {SOURCE_LABELS[setting.source]}
          </Badge>
          {resettable ? (
            <Button
              variant="ghost"
              size="sm"
              title={`Volver a ${formatValue(setting.default)}`}
              onClick={onReset}
            >
              <Undo2 />
              Por defecto
            </Button>
          ) : null}
        </div>
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

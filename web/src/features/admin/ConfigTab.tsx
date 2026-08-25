import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  Cpu,
  FlaskConical,
  Hammer,
  RefreshCw,
  Save,
  ScanSearch,
  ScrollText,
  SlidersHorizontal,
  Tags,
  Undo2,
  Wrench,
} from "lucide-react";
import { useState } from "react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Alert, Checkbox, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { bytes } from "@/lib/format";
import { cn } from "@/lib/utils";
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

const REASONING_GROUP = "Razonamiento";
const MODELS_GROUP = "Modelos";
const PHASE_MODEL_PREFIX = "models.phases.";
const OTHERS_KEY = "__otros__";
const CEREBRAS_KEYS = [
  "engine.cerebras_base_url",
  "engine.cerebras_api_key",
  "engine.cerebras_models",
];

type Section = {
  key: string;
  label: string;
  icon: LucideIcon;
  description: string;
  groups: string[];
};

// The registry's groups, folded into destinations a person can hold in their head: one
// sub-page per question the configuration answers, not one flat list of 132 rows. The
// group names are the server's; a group nobody claims below still gets a page of its own,
// so a registry addition never disappears from the screen.
const SECTIONS: Section[] = [
  {
    key: "motor",
    label: "Motor",
    icon: Cpu,
    description:
      "El motor de inferencia, su anfitrión y el túnel SSH hasta la máquina de la GPU.",
    groups: ["Motor", "Túnel SSH"],
  },
  {
    key: "modelos",
    label: "Modelos y razonamiento",
    icon: Brain,
    description:
      "El recorrido completo, llamada a llamada: qué modelo atiende cada fase, si razona antes de contestar y con qué esfuerzo.",
    groups: [MODELS_GROUP, REASONING_GROUP],
  },
  {
    key: "muestreo",
    label: "Muestreo y contexto",
    icon: SlidersHorizontal,
    description:
      "Las temperaturas de cada tipo de llamada y la ventana de contexto (el KV cache) que se reserva a cada modelo.",
    groups: ["Muestreo", "Ventana de contexto"],
  },
  {
    key: "constructores",
    label: "Constructores",
    icon: Hammer,
    description:
      "Cómo se construyen el grafo, el perfil y el banco a partir del corpus en bruto: troceado, fusión, dominios y anclaje.",
    groups: ["Constructores"],
  },
  {
    key: "recuperacion",
    label: "Recuperación",
    icon: ScanSearch,
    description:
      "El índice de conceptos: prefijos de embedding, pesos, umbrales y cuántos candidatos se recuperan.",
    groups: ["Recuperación"],
  },
  {
    key: "generacion",
    label: "Etiquetado y generación",
    icon: Tags,
    description:
      "El etiquetador del banco y la generación de variantes: ejemplos few-shot, reintentos y el guardián.",
    groups: ["Etiquetado y generación"],
  },
  {
    key: "evaluacion",
    label: "Evaluación",
    icon: FlaskConical,
    description:
      "El estudio comparativo: los proveedores externos de los brazos de referencia y el estado de sus claves.",
    groups: ["Evaluación"],
  },
  {
    key: "registro",
    label: "Registro",
    icon: ScrollText,
    description: "Qué escribe el proceso en su registro y desde qué nivel.",
    groups: ["Registro"],
  },
];

export function ConfigTab() {
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

  const stored = new Map(
    payload.settings.map((setting) => [setting.key, setting.value ?? setting.default]),
  );
  const engineName = String(
    ("engine.name" in draft ? draft["engine.name"] : stored.get("engine.name")) ?? "ollama",
  );
  const hidden = new Set(engineName === "cerebras+ollama" ? [] : CEREBRAS_KEYS);
  const named = new Set(payload.groups);
  const orphans = payload.settings.filter((setting) => !named.has(setting.group));
  const byGroup = (group: string) =>
    payload.settings.filter((setting) => setting.group === group && !hidden.has(setting.key));
  const claimed = new Set(SECTIONS.flatMap((section) => section.groups));
  const sections: Section[] = [
    ...SECTIONS,
    ...payload.groups
      .filter((group) => !claimed.has(group))
      .map((group) => ({
        key: `grupo:${group}`,
        label: group,
        icon: Wrench,
        description: "",
        groups: [group],
      })),
    ...(orphans.length > 0
      ? [
          {
            key: OTHERS_KEY,
            label: "Otros",
            icon: Wrench,
            description: "Ajustes cuyo grupo no tiene sitio propio en el panel.",
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

      <div className="grid items-start gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <nav aria-label="Secciones de la configuración" className="space-y-2 lg:sticky lg:top-4">
          <Input
            aria-label="Buscar un ajuste"
            placeholder="Buscar un ajuste…"
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
                    <span className="min-w-0 flex-1 truncate">{section.label}</span>
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
                {matches.length} ajuste(s) para «{search.trim()}»
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
                  <h2 className="font-expanded text-heading">{activeSection.label}</h2>
                  {activeSection.description ? (
                    <p className="text-small text-muted-foreground">{activeSection.description}</p>
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
            <Alert tone="attention" title="Cambio de motor">
              Al guardar, los ajustes de ámbito motor (modelos, fases, ventanas de contexto y
              razonamiento) pasarán al perfil de «{String(draft["engine.name"])}». El perfil de
              «{String(stored.get("engine.name"))}» se conserva tal cual para cuando se vuelva.
            </Alert>
          ) : null}

          <DiffSummary settings={payload.settings} draft={draft} />
        </div>
      </div>

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
  title: string | null;
  settings: ConfigSetting[];
  draft: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  onReset: (key: string) => void;
  models: ConfigPayload["models"] | null;
}) {
  const current = (setting: ConfigSetting) =>
    setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default);

  return (
    <Card>
      {title ? (
        <CardHeader className="pb-2">
          <CardTitle>{title}</CardTitle>
        </CardHeader>
      ) : null}
      <CardContent className={cn("space-y-3", !title && "pt-4")}>
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

// One card for the two groups the pipeline drawing already covers: the three residents as
// rows, then every phase as a node carrying its model, its reasoning switch AND, while it
// reasons, its effort — a phase's three decisions are taken in one place. What no node
// shows keeps its row below; what the nodes do show never gets a second row.
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
          Cada pista es una construcción; cada nodo, una llamada al modelo. Bajo cada nodo,
          qué modelo la atiende («principal» sigue a {residents.find((s) => s.key === "models.main")?.name ?? "LLM_MAIN"});
          el círculo dice si razona antes de contestar y, mientras razona, el selector fija su
          esfuerzo. Razonar y una gramática no conviven en esta
          pila, así que encender una fase que hoy responde con gramática se la quita y deja la
          forma en manos del analizador y de la reparación. Tres nodos no dependen de un
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
        {inNodes.length > 0 ? (
          <details className="text-small text-muted-foreground">
            <summary className="cursor-pointer select-none">Por qué cada nodo</summary>
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
    if (model.remote) return `${model.model} — remoto (Cerebras)`;
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

function CerebrasModelsField({
  id,
  label,
  value,
  disabled,
  onChange,
}: {
  id: string;
  label: string;
  value: unknown;
  disabled: boolean;
  onChange: (next: unknown) => void;
}) {
  const catalog = useQuery({
    queryKey: ["admin", "config", "cerebras-catalog"],
    queryFn: api.adminCerebrasModels,
    staleTime: 60_000,
  });
  const selected = Array.isArray(value) ? value.map(String) : [];
  const listed = catalog.data?.source === "api" ? catalog.data.models : null;
  const toggle = (model: string, next: boolean) =>
    onChange(next ? [...selected, model] : selected.filter((name) => name !== model));

  if (catalog.isLoading) {
    return (
      <div className="space-y-1">
        <span className="text-body">{label}</span>
        <p className="flex items-center gap-2 text-small text-muted-foreground">
          <Spinner />
          Leyendo el catálogo de Cerebras…
        </p>
      </div>
    );
  }

  if (!listed) {
    return (
      <div className="space-y-1">
        <Label htmlFor={id}>{label}</Label>
        <Input
          id={id}
          disabled={disabled}
          value={selected.join(", ")}
          onChange={(event) =>
            onChange(
              event.target.value
                .split(",")
                .map((part) => part.trim())
                .filter(Boolean),
            )
          }
        />
        <p className="text-small text-muted-foreground">
          {catalog.data?.error ?? "El catálogo de Cerebras no responde."} Sepáralos con comas.
        </p>
      </div>
    );
  }

  const extras = selected.filter((name) => !listed.includes(name));
  return (
    <div className="space-y-1.5">
      <span className="text-body">{label}</span>
      <ul className="space-y-1.5">
        {listed.map((model) => (
          <li key={model} className="flex items-center gap-2">
            <Checkbox
              checked={selected.includes(model)}
              disabled={disabled}
              onCheckedChange={(next) => toggle(model, next)}
              label={`Enrutar ${model} a Cerebras`}
            />
            <span className="font-mono text-body">{model}</span>
          </li>
        ))}
        {extras.map((model) => (
          <li key={model} className="flex items-center gap-2">
            <Checkbox
              checked
              disabled={disabled}
              onCheckedChange={(next) => toggle(model, next)}
              label={`Enrutar ${model} a Cerebras`}
            />
            <span className="font-mono text-body">{model}</span>
            <Badge variant="outline">fuera del catálogo</Badge>
          </li>
        ))}
      </ul>
      <p className="text-small text-muted-foreground">
        La lista viene de la propia API de Cerebras. Lo marcado se sirve en remoto; todo lo demás
        sigue en Ollama.
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
          ) : setting.key === "engine.cerebras_models" ? (
            <CerebrasModelsField
              id={id}
              label={label}
              value={value}
              disabled={disabled}
              onChange={onChange}
            />
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
                onChange={(event) =>
                  onChange(event.target.value === "" && setting.nullable ? null : event.target.value)
                }
              >
                {setting.nullable ? <option value="">— sin fijar —</option> : null}
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

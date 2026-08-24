import { Braces, Brain, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";

import { Input, Select } from "@/components/ui/input";
import { bytes } from "@/lib/format";
import type {
  ConfigPayload,
  ConfigSetting,
  InstalledModel,
  ReasoningFixed,
  ReasoningLane,
  ReasoningPhase,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const FIXED_LABELS: Record<ReasoningFixed, string> = {
  grammar: "con gramática: no puede razonar",
  commission: "lo decide cada encargo",
  model: "el modelo no razona",
};

const FIXED_ICONS: Record<ReasoningFixed, typeof Braces> = {
  grammar: Braces,
  commission: UserRound,
  model: ShieldCheck,
};

type Models = ConfigPayload["models"];

export function ReasoningPipeline({
  lanes,
  settings,
  draft,
  models,
  onChange,
}: {
  lanes: ReasoningLane[];
  settings: ConfigSetting[];
  draft: Record<string, unknown>;
  models: Models | null;
  onChange: (key: string, value: unknown) => void;
}) {
  const byKey = new Map(settings.map((setting) => [setting.key, setting]));
  const current = (key: string) => {
    const setting = byKey.get(key);
    if (!setting) return null;
    return key in draft ? draft[key] : (setting.value ?? setting.default);
  };
  const main = current("models.main");
  const mainName = typeof main === "string" && main ? main : null;

  return (
    <ol className="space-y-5">
      {lanes.map((lane) => (
        <li key={lane.key} className="grid gap-2 md:grid-cols-[10rem_1fr] md:gap-4">
          <p className="pt-2 text-micro font-condensed uppercase tracking-wide text-muted-foreground">
            {lane.label}
          </p>
          <ol className="flex w-full items-start overflow-x-auto pb-1">
            {lane.phases.map((phase, index) => (
              <PhaseNode
                key={phase.key}
                phase={phase}
                setting={phase.setting ? byKey.get(phase.setting) ?? null : null}
                modelSetting={byKey.get(phase.model) ?? null}
                mainName={mainName}
                draft={draft}
                models={models}
                first={index === 0}
                last={index === lane.phases.length - 1}
                onChange={onChange}
              />
            ))}
          </ol>
        </li>
      ))}
    </ol>
  );
}

function PhaseNode({
  phase,
  setting,
  modelSetting,
  mainName,
  draft,
  models,
  first,
  last,
  onChange,
}: {
  phase: ReasoningPhase;
  setting: ConfigSetting | null;
  modelSetting: ConfigSetting | null;
  mainName: string | null;
  draft: Record<string, unknown>;
  models: Models | null;
  first: boolean;
  last: boolean;
  onChange: (key: string, value: unknown) => void;
}) {
  const line = <span aria-hidden className="mt-[17px] h-px min-w-3 flex-1 bg-border" />;
  const lead = first ? <span className="min-w-3 flex-1" /> : line;
  const trail = last ? <span className="min-w-3 flex-1" /> : line;
  const residentName = modelSetting
    ? String(
        (modelSetting.key in draft ? draft[modelSetting.key] : modelSetting.value ?? modelSetting.default) ?? "",
      )
    : "";

  return (
    <li className="flex min-w-0 basis-0 flex-1 items-start">
      {lead}
      <span className="flex w-28 flex-col items-center gap-1">
        {setting ? (
          <Toggle phase={phase} setting={setting} draft={draft} onChange={onChange} />
        ) : (
          <Fixed phase={phase} />
        )}
        <span className="text-center text-micro font-condensed uppercase leading-tight text-foreground">
          {phase.label}
        </span>
        {modelSetting && !modelSetting.key.startsWith("models.phases.") ? (
          <span
            className="max-w-full truncate font-mono text-micro text-muted-foreground"
            title={`Modelo: ${residentName}`}
          >
            {residentName}
          </span>
        ) : modelSetting ? (
          <NodeModel
            phase={phase}
            setting={modelSetting}
            mainName={mainName}
            draft={draft}
            models={models}
            onChange={onChange}
          />
        ) : null}
      </span>
      {trail}
    </li>
  );
}

const OTHER = "__other__";

// The same choice the «Modelos» rows offered, shrunk to fit under a node: what the engine has
// on disk, «principal» (null) first for an override, «Otro…» for a model not pulled yet. The
// select shows only the name; residency and size travel in the option text and the title.
function NodeModel({
  phase,
  setting,
  mainName,
  draft,
  models,
  onChange,
}: {
  phase: ReasoningPhase;
  setting: ConfigSetting;
  mainName: string | null;
  draft: Record<string, unknown>;
  models: Models | null;
  onChange: (key: string, value: unknown) => void;
}) {
  const pending = setting.key in draft;
  const raw = pending ? draft[setting.key] : (setting.value ?? setting.default);
  const value = typeof raw === "string" && raw ? raw : null;
  const installed = models?.installed ?? [];
  const known = installed.some((m) => m.model === value);
  const [other, setOther] = useState(() => Boolean(value) && !known);
  const residentVram = new Map((models?.running ?? []).map((m) => [m.model, m.size_vram]));
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;
  const effective = value ?? mainName;
  const label = `${phase.label}: modelo`;

  const describe = (model: InstalledModel) => {
    if (model.remote) return `${model.model} — remoto (Cerebras)`;
    const vram = residentVram.get(model.model);
    if (vram) return `${model.model} — cargado, ${bytes(vram)} en VRAM`;
    return model.size ? `${model.model} — en disco, ${bytes(model.size)}` : model.model;
  };
  const title = [
    effective ? `Modelo: ${effective}${value ? "" : " (sigue al principal)"}` : "Sin modelo",
    lockedByEnv ? `lo fija ${setting.env}` : null,
  ]
    .filter(Boolean)
    .join(" — ");

  return (
    <span className="flex w-full flex-col items-stretch gap-1">
      <Select
        aria-label={label}
        title={title}
        value={other ? OTHER : value ?? ""}
        disabled={disabled}
        onChange={(event) => {
          const next = event.target.value;
          if (next === OTHER) {
            setOther(true);
            return;
          }
          setOther(false);
          onChange(setting.key, next === "" ? null : next);
        }}
        className={cn(
          "h-7 px-1.5 font-mono text-micro",
          !value && !other && "text-muted-foreground",
          pending && "border-attention ring-1 ring-attention",
        )}
      >
        {setting.nullable ? (
          <option value="">{mainName ? `principal (${mainName})` : "principal"}</option>
        ) : null}
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
          aria-label={`${label}: nombre`}
          placeholder="nombre:etiqueta"
          disabled={disabled}
          value={value ?? ""}
          onChange={(event) => onChange(setting.key, event.target.value || null)}
          className="h-7 px-1.5 font-mono text-micro"
        />
      ) : null}
    </span>
  );
}

function Toggle({
  phase,
  setting,
  draft,
  onChange,
}: {
  phase: ReasoningPhase;
  setting: ConfigSetting;
  draft: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}) {
  const pending = setting.key in draft;
  const on = Boolean(pending ? draft[setting.key] : (setting.value ?? setting.default));
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;
  const title = [
    `${phase.label}: razonamiento ${on ? "activado" : "desactivado"}`,
    lockedByEnv ? `lo fija ${setting.env}` : null,
    phase.note || null,
  ]
    .filter(Boolean)
    .join(" — ");

  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={`${phase.label}: razonar antes de contestar`}
      title={title}
      disabled={disabled}
      onClick={() => onChange(setting.key, !on)}
      className={cn(
        "flex size-9 items-center justify-center rounded-full border-2 transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "disabled:cursor-not-allowed disabled:opacity-50",
        on
          ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
          : "border-border bg-background text-muted-foreground hover:border-foreground/40",
        pending && "ring-2 ring-attention ring-offset-2 ring-offset-background",
      )}
    >
      <Brain className="size-4" />
    </button>
  );
}

function Fixed({ phase }: { phase: ReasoningPhase }) {
  const fixed = phase.fixed ?? "grammar";
  const Icon = FIXED_ICONS[fixed];
  const title = [`${phase.label}: ${FIXED_LABELS[fixed]}`, phase.note || null]
    .filter(Boolean)
    .join(" — ");
  return (
    <span
      title={title}
      aria-label={title}
      className="flex size-9 items-center justify-center rounded-full border-2 border-dashed border-border bg-muted/40 text-muted-foreground"
    >
      <Icon className="size-4" />
    </span>
  );
}

export function ReasoningLegend() {
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-small text-muted-foreground">
      <li className="flex items-center gap-1.5">
        <span className="flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Brain className="size-3" />
        </span>
        razona
      </li>
      <li className="flex items-center gap-1.5">
        <span className="flex size-5 items-center justify-center rounded-full border border-border text-muted-foreground">
          <Brain className="size-3" />
        </span>
        responde sin razonar
      </li>
      <li className="flex items-center gap-1.5">
        <span className="flex size-5 items-center justify-center rounded-full border border-dashed border-border text-muted-foreground">
          <Braces className="size-3" />
        </span>
        fija: no depende de un ajuste
      </li>
      <li>bajo cada nodo, el modelo que atiende esa llamada</li>
    </ul>
  );
}

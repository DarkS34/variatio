import type { ReactNode } from "react";

import { Input, Label } from "@/components/ui/input";
import { PhaseNode } from "@/features/admin/PhaseNode";
import { SETTING_LIST, SettingRow } from "@/features/admin/SettingFields";
import { useT, type Key } from "@/lib/i18n";
import type { ConfigPayload, ConfigSetting, ReasoningLane, ReasoningPhase } from "@/lib/types";
import { cn } from "@/lib/utils";

type Models = ConfigPayload["models"];

const SAMPLING_PREFIX = "sampling.phases.";
const MODEL_PREFIX = "models.phases.";
const PARAMS = ["temperature", "top_k", "top_p"] as const;
type Param = (typeof PARAMS)[number];

const PARAM_LABELS: Record<Param, Key> = {
  temperature: "cfg.sampling.temperature",
  top_k: "cfg.sampling.topK",
  top_p: "cfg.sampling.topP",
};

/** What every row and node of a stage's screen reads and writes, passed down once. */
export type FlowContext = {
  byKey: Map<string, ConfigSetting>;
  draft: Record<string, unknown>;
  models: Models | null;
  onChange: (key: string, value: unknown) => void;
  onReset: (key: string) => void;
  /** The one row (`generation.fixed_effort`) that needs the offered models as they stand. */
  offered: string[];
  levels: Record<string, string>;
  onLevels: (next: Record<string, string>) => void;
};

/**
 * The keys a node draws in itself — its own model's select, its switch and effort, its
 * sampling — so they never get a row of their own under it.
 */
export function nodeKeys(phase: ReasoningPhase): string[] {
  return [
    `${MODEL_PREFIX}${phase.key}`,
    ...(phase.setting ? [phase.setting] : []),
    ...(phase.effort ? [phase.effort] : []),
    ...PARAMS.map((param) => `${SAMPLING_PREFIX}${phase.key}.${param}`),
  ];
}

/**
 * A stage's calls, down the page: each node with its sampling and then its own settings.
 *
 * `rowsOf` decides which settings sit under which node — the stage's own screen passes the
 * settings it owns, the shared block passes what this stage reads of another's.
 */
export function StageFlow({
  lane,
  ctx,
  rowsOf,
  asideOf,
}: {
  lane: ReasoningLane;
  ctx: FlowContext;
  rowsOf: (phase: ReasoningPhase) => ConfigSetting[];
  asideOf?: (phase: ReasoningPhase) => ReactNode;
}) {
  const phases = lane.phases;
  return (
    <ol>
      {phases.map((phase, index) => (
        <FlowNode
          key={phase.key}
          phase={phase}
          ctx={ctx}
          rows={rowsOf(phase)}
          aside={asideOf?.(phase)}
          last={index === phases.length - 1}
        />
      ))}
    </ol>
  );
}

export function FlowNode({
  phase,
  ctx,
  rows,
  aside,
  last,
}: {
  phase: ReasoningPhase;
  ctx: FlowContext;
  rows: ConfigSetting[];
  aside?: ReactNode;
  last: boolean;
}) {
  const { byKey, draft, models, onChange } = ctx;
  const modelSetting = byKey.get(phase.model) ?? null;
  return (
    <PhaseNode
      phase={phase}
      setting={phase.setting ? (byKey.get(phase.setting) ?? null) : null}
      effortSetting={phase.effort ? (byKey.get(phase.effort) ?? null) : null}
      modelSetting={modelSetting}
      modelBelow={rows.some((row) => row.key === phase.model)}
      draft={draft}
      models={models}
      last={last}
      aside={aside}
      onChange={onChange}
    >
      <SamplingFields phase={phase} ctx={ctx} />
      {rows.length > 0 ? (
        <div className={SETTING_LIST}>
          {rows.map((setting) => (
            <Row key={setting.key} setting={setting} ctx={ctx} />
          ))}
        </div>
      ) : null}
    </PhaseNode>
  );
}

/** One setting as a full row, wired to the screen's draft. */
export function Row({ setting, ctx }: { setting: ConfigSetting; ctx: FlowContext }) {
  return (
    <SettingRow
      setting={setting}
      value={valueOf(setting, ctx.draft)}
      onChange={(next) => ctx.onChange(setting.key, next)}
      onReset={() => ctx.onReset(setting.key)}
      models={ctx.models}
      offered={ctx.offered}
      levels={ctx.levels}
      onLevels={ctx.onLevels}
    />
  );
}

export function valueOf(setting: ConfigSetting, draft: Record<string, unknown>): unknown {
  return setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default);
}

/**
 * A call's temperature, top-k and top-p, on one line under its name.
 *
 * An empty field is inherited, and says from what: the temperature from the reasoning pair
 * by whether the call reasons now, or from the phase whose model it reads; top-k and top-p
 * from that phase, or from the model itself. A top-k cannot be sent to Cerebras, so on a
 * call served there the field is shown and not offered.
 */
function SamplingFields({ phase, ctx }: { phase: ReasoningPhase; ctx: FlowContext }) {
  const { t } = useT();
  const settings = PARAMS.map((param) => ctx.byKey.get(`${SAMPLING_PREFIX}${phase.key}.${param}`));
  if (settings.every((setting) => !setting)) return null;
  const remote = servedRemotely(phase, ctx);

  return (
    <fieldset className="space-y-1.5">
      <legend className="text-micro text-muted-foreground">{t("cfg.sampling.title")}</legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {PARAMS.map((param, index) => {
          const setting = settings[index];
          if (!setting) return null;
          return (
            <SamplingField
              key={param}
              param={param}
              setting={setting}
              ctx={ctx}
              inherited={inheritedText(phase, param, ctx, t)}
              unsupported={param === "top_k" && remote}
            />
          );
        })}
      </div>
    </fieldset>
  );
}

function SamplingField({
  param,
  setting,
  ctx,
  inherited,
  unsupported,
}: {
  param: Param;
  setting: ConfigSetting;
  ctx: FlowContext;
  inherited: string;
  unsupported: boolean;
}) {
  const { t } = useT();
  const id = `config-${setting.key}`;
  const value = valueOf(setting, ctx.draft);
  const pending = setting.key in ctx.draft;
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv || unsupported;
  const title = unsupported
    ? t("cfg.sampling.noTopK")
    : lockedByEnv
      ? t("cfg.fixedBy", { env: setting.env ?? "" })
      : undefined;

  return (
    <div className="space-y-1" title={title}>
      <Label htmlFor={id} className="text-small">
        {t(PARAM_LABELS[param])}
      </Label>
      <Input
        id={id}
        type="number"
        min={setting.minimum ?? undefined}
        max={setting.maximum ?? undefined}
        step={setting.kind === "float" ? "any" : 1}
        disabled={disabled}
        placeholder={setting.nullable ? inherited : undefined}
        value={value === null || value === undefined ? "" : String(value)}
        onChange={(event) => {
          const raw = event.target.value;
          if (raw === "") {
            // A call with a temperature of its own cannot be left without one.
            if (setting.nullable) ctx.onChange(setting.key, null);
            return;
          }
          const num = setting.kind === "int" ? Number.parseInt(raw, 10) : Number(raw);
          if (!Number.isNaN(num)) ctx.onChange(setting.key, num);
        }}
        className={cn("h-8", pending && "border-attention ring-1 ring-attention")}
      />
    </div>
  );
}

/** What an empty field of `phase` falls back to, said in the field itself. */
function inheritedText(
  phase: ReasoningPhase,
  param: Param,
  ctx: FlowContext,
  t: ReturnType<typeof useT>["t"],
): string {
  const parent = parentOf(phase);
  if (parent) {
    const own = ctx.byKey.get(`${SAMPLING_PREFIX}${parent}.${param}`);
    const value = own ? valueOf(own, ctx.draft) : null;
    if (value !== null && value !== undefined) {
      return t("cfg.sampling.fromPhase", { value: String(value) });
    }
  }
  if (param !== "temperature") return t("cfg.sampling.fromModel");
  const thinks = phase.setting
    ? Boolean(valueOf(ctx.byKey.get(phase.setting) ?? ({} as ConfigSetting), ctx.draft))
    : false;
  const pair = ctx.byKey.get(
    thinks ? "sampling.temperature_reasoning" : "sampling.temperature_deterministic",
  );
  const value = pair ? valueOf(pair, ctx.draft) : null;
  return t(thinks ? "cfg.sampling.fromReasoning" : "cfg.sampling.fromDeterministic", {
    value: String(value ?? "—"),
  });
}

/** The phase whose model this one reads with, whose sampling it inherits; null for its own. */
function parentOf(phase: ReasoningPhase): string | null {
  if (!phase.model.startsWith(MODEL_PREFIX)) return null;
  const parent = phase.model.slice(MODEL_PREFIX.length);
  return parent === phase.key ? null : parent;
}

/** Whether every model this call may be written with is served by Cerebras. */
function servedRemotely(phase: ReasoningPhase, ctx: FlowContext): boolean {
  const setting = ctx.byKey.get(phase.model);
  if (!setting || !ctx.models) return false;
  const value = valueOf(setting, ctx.draft);
  const names = Array.isArray(value) ? value.map(String) : value ? [String(value)] : [];
  const remote = new Set(
    ctx.models.installed.filter((model) => model.remote).map((model) => model.model),
  );
  return names.length > 0 && names.every((name) => remote.has(name));
}

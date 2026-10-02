import { Braces, Brain, CircleOff, Globe, ShieldCheck, Shuffle, UserRound } from "lucide-react";
import { useState, type ReactNode } from "react";

import { Input, Select } from "@/components/ui/input";
import { bytes } from "@/lib/format";
import type {
  ConfigPayload,
  ConfigSetting,
  InstalledModel,
  ReasoningFixed,
  ReasoningPhase,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT, type Key } from "@/lib/i18n";

const FIXED_LABELS: Record<ReasoningFixed, Key> = {
  grammar: "pipe.fixed.grammar",
  commission: "pipe.fixed.commission",
  model: "pipe.fixed.model",
  drawn: "pipe.fixed.drawn",
  external: "pipe.fixed.external",
  off: "pipe.fixed.off",
};

const FIXED_ICONS: Record<ReasoningFixed, typeof Braces> = {
  grammar: Braces,
  commission: UserRound,
  model: ShieldCheck,
  drawn: Shuffle,
  external: Globe,
  off: CircleOff,
};

type Models = ConfigPayload["models"];

/**
 * One call to the model, drawn as a stop on its stage's path, with what tunes it below.
 *
 * A stage runs DOWN and not across, and that is the whole of the layout: each stop is the
 * width of the column whatever its neighbours do, a model name fits without being cut,
 * and the call's own settings — its sampling, then its parameters — sit under its name, so
 * everything one call does is decided in one place. `last` withholds the connector.
 *
 * The header shows the model as a select when the node owns it, as nothing when the
 * setting is drawn as a row below (`modelBelow`), and as its name otherwise: the pictures
 * read with the PAGE phase's model on purpose, and a second select for one setting would
 * read as two controls.
 */
export function PhaseNode({
  phase,
  setting,
  effortSetting,
  modelSetting,
  modelBelow = false,
  draft,
  models,
  last,
  aside,
  onChange,
  children,
}: {
  phase: ReasoningPhase;
  setting: ConfigSetting | null;
  effortSetting: ConfigSetting | null;
  modelSetting: ConfigSetting | null;
  modelBelow?: boolean;
  draft: Record<string, unknown>;
  models: Models | null;
  last: boolean;
  /** Beside the name: where a call drawn on another stage's screen belongs. */
  aside?: ReactNode;
  onChange: (key: string, value: unknown) => void;
  children?: ReactNode;
}) {
  const { t } = useT();
  const thinks = setting
    ? Boolean(setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default))
    : false;
  const modelValue = modelSetting
    ? (modelSetting.key in draft
        ? draft[modelSetting.key]
        : modelSetting.value ?? modelSetting.default)
    : null;
  const residentName = Array.isArray(modelValue)
    ? modelValue.map(String).join(" · ")
    : String(modelValue ?? "") || "—";
  const ownModel = modelSetting?.key === `models.phases.${phase.key}`;

  return (
    <li className="relative grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-2.5 pb-5">
      {/* The stretch between this stop and the next one, behind the mark. */}
      {last ? null : (
        <span aria-hidden className="absolute bottom-0 left-[1.0625rem] top-9 w-px bg-border" />
      )}
      {setting ? (
        <Toggle phase={phase} setting={setting} draft={draft} onChange={onChange} />
      ) : (
        <Fixed phase={phase} />
      )}
      <div className="min-w-0 space-y-3 pt-1.5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <span
            className="font-condensed uppercase leading-tight text-small text-foreground"
            title={phase.note || undefined}
          >
            {phase.label}
          </span>
          {aside}
          <span className="flex min-w-0 flex-1 items-center gap-1.5 sm:max-w-md">
            {effortSetting && thinks ? (
              <NodeEffort phase={phase} setting={effortSetting} draft={draft} onChange={onChange} />
            ) : null}
            {modelSetting && ownModel ? (
              <NodeModel
                phase={phase}
                setting={modelSetting}
                draft={draft}
                models={models}
                onChange={onChange}
              />
            ) : modelSetting && !modelBelow ? (
              <span
                className="min-w-0 flex-1 truncate font-mono text-micro text-muted-foreground"
                title={t("pipe.modelTitle", { model: residentName })}
              >
                {residentName}
              </span>
            ) : null}
          </span>
        </div>
        {children}
      </div>
    </li>
  );
}

function NodeEffort({
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
  const { t } = useT();
  const pending = setting.key in draft;
  const raw = pending ? draft[setting.key] : (setting.value ?? setting.default);
  const value = typeof raw === "string" && raw ? raw : "low";
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;
  const title = [
    t("pipe.effortTitle", { phase: phase.label, level: value }),
    lockedByEnv ? t("pipe.lockedByEnv", { env: setting.env ?? "" }) : null,
  ]
    .filter(Boolean)
    .join(" — ");

  return (
    <Select
      aria-label={t("pipe.effortAria", { phase: phase.label })}
      title={title}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(setting.key, event.target.value)}
      className={cn(
        "h-7 w-[4.75rem] shrink-0 px-1 text-micro",
        pending && "border-attention ring-1 ring-attention",
      )}
    >
      {(setting.choices ?? []).map((choice) => (
        <option key={choice} value={choice}>
          {choice}
        </option>
      ))}
    </Select>
  );
}

const OTHER = "__other__";

// The same choice the "Modelos" rows offered, shrunk to fit under a node: what the engine has
// on disk, "principal" (null) first for an override, "Otro…" for a model not pulled yet. The
// select shows only the name; residency and size travel in the option text and the title.
function NodeModel({
  phase,
  setting,
  draft,
  models,
  onChange,
}: {
  phase: ReasoningPhase;
  setting: ConfigSetting;
  draft: Record<string, unknown>;
  models: Models | null;
  onChange: (key: string, value: unknown) => void;
}) {
  const { t } = useT();
  const pending = setting.key in draft;
  const raw = pending ? draft[setting.key] : (setting.value ?? setting.default);
  const value = typeof raw === "string" && raw ? raw : null;
  const installed = models?.installed ?? [];
  const known = installed.some((m) => m.model === value);
  const [other, setOther] = useState(() => Boolean(value) && !known);
  const residentVram = new Map((models?.running ?? []).map((m) => [m.model, m.size_vram]));
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;
  const effective = value;
  const label = t("pipe.modelLabel", { phase: phase.label });

  const describe = (model: InstalledModel) => {
    if (model.remote) return t("pipe.model.remote", { model: model.model });
    const vram = residentVram.get(model.model);
    if (vram) return t("pipe.model.loaded", { model: model.model, size: bytes(vram) });
    return model.size
      ? t("pipe.model.onDisk", { model: model.model, size: bytes(model.size) })
      : model.model;
  };
  const title = [
    effective
      ? t("pipe.modelTitle", { model: effective })
      : t("pipe.model.none"),
    lockedByEnv ? t("pipe.lockedByEnv", { env: setting.env ?? "" }) : null,
  ]
    .filter(Boolean)
    .join(" — ");

  return (
    <span className="flex min-w-0 flex-1 flex-col items-stretch gap-1">
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
          onChange(setting.key, next);
        }}
        className={cn(
          "h-7 px-1.5 font-mono text-micro",
          !value && !other && "text-muted-foreground",
          pending && "border-attention ring-1 ring-attention",
        )}
      >
        {value && !known && !other ? <option value={value}>{t("pipe.notInstalled", { model: value })}</option> : null}
        {installed.map((model) => (
          <option key={model.model} value={model.model}>
            {describe(model)}
          </option>
        ))}
        <option value={OTHER}>{t("pipe.other")}</option>
      </Select>
      {other ? (
        <Input
          aria-label={t("pipe.modelNameAria", { label })}
          placeholder={t("pipe.modelNamePlaceholder")}
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
  const { t } = useT();
  const pending = setting.key in draft;
  const on = Boolean(pending ? draft[setting.key] : (setting.value ?? setting.default));
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;
  const title = [
    t("pipe.thinkTitle", {
      phase: phase.label,
      state: on ? t("pipe.think.on") : t("pipe.think.off"),
    }),
    lockedByEnv ? t("pipe.lockedByEnv", { env: setting.env ?? "" }) : null,
    phase.note || null,
  ]
    .filter(Boolean)
    .join(" — ");

  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={t("pipe.thinkAria", { phase: phase.label })}
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
  const { t } = useT();
  const fixed = phase.fixed ?? "grammar";
  const Icon = FIXED_ICONS[fixed];
  const title = [`${phase.label}: ${t(FIXED_LABELS[fixed])}`, phase.note || null]
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
  const { t } = useT();
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-small text-muted-foreground">
      <li className="flex items-center gap-1.5">
        <span className="flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Brain className="size-3" />
        </span>
        {t("pipe.legend.reasons")}
      </li>
      <li className="flex items-center gap-1.5">
        <span className="flex size-5 items-center justify-center rounded-full border border-border text-muted-foreground">
          <Brain className="size-3" />
        </span>
        {t("pipe.legend.noReasoning")}
      </li>
      <li className="flex items-center gap-1.5">
        <span className="flex size-5 items-center justify-center rounded-full border border-dashed border-border text-muted-foreground">
          <Braces className="size-3" />
        </span>
        {t("pipe.legend.fixed")}
      </li>
      <li>{t("pipe.legend.stop")}</li>
    </ul>
  );
}

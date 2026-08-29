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
import { useT, type Key } from "@/lib/i18n";

const FIXED_LABELS: Record<ReasoningFixed, Key> = {
  grammar: "pipe.fixed.grammar",
  commission: "pipe.fixed.commission",
  model: "pipe.fixed.model",
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
  return (
    <ol className="grid items-start gap-x-5 gap-y-7 md:grid-cols-2 xl:grid-cols-4">
      {lanes.map((lane) => (
        <li key={lane.key} className="min-w-0">
          <p className="border-b border-border pb-1.5 text-micro font-condensed uppercase tracking-wide text-muted-foreground">
            {lane.label}
          </p>
          <ol className="pt-3">
            {lane.phases.map((phase, index) => (
              <PhaseNode
                key={phase.key}
                phase={phase}
                setting={phase.setting ? byKey.get(phase.setting) ?? null : null}
                effortSetting={phase.effort ? byKey.get(phase.effort) ?? null : null}
                modelSetting={byKey.get(phase.model) ?? null}
                draft={draft}
                models={models}
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

/**
 * One call to the model, drawn as a stop on its lane.
 *
 * The lane runs DOWN and not across, and that is the whole of the layout. Across, the mark
 * was a fixed width and the spacing between marks was elastic, so how the drawing looked
 * was a function of how many stops a lane happened to have — and they have 5, 13, 4 and 4.
 * The long one overflowed into a scroller with every label clipped to «TRANSCRIPCI» and
 * every select to «gemm», and the short ones were left with holes. Down the page each stop
 * is the width of its column whatever its neighbours do, a model name fits without being
 * cut, and nothing has to scroll sideways to be read.
 */
function PhaseNode({
  phase,
  setting,
  effortSetting,
  modelSetting,
  draft,
  models,
  last,
  onChange,
}: {
  phase: ReasoningPhase;
  setting: ConfigSetting | null;
  effortSetting: ConfigSetting | null;
  modelSetting: ConfigSetting | null;
  draft: Record<string, unknown>;
  models: Models | null;
  last: boolean;
  onChange: (key: string, value: unknown) => void;
}) {
  const { t } = useT();
  const thinks = setting
    ? Boolean(setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default))
    : false;
  const residentName = modelSetting
    ? String(
        (modelSetting.key in draft ? draft[modelSetting.key] : modelSetting.value ?? modelSetting.default) ?? "",
      )
    : "";
  const ownModel = Boolean(modelSetting?.key.startsWith("models.phases."));

  return (
    <li className="relative grid grid-cols-[2.25rem_minmax(0,1fr)] gap-x-2.5 pb-3">
      {/* The stretch between this stop and the next one. Behind the mark rather than
          between two of them, so a lane of thirteen draws one line and not twelve. */}
      {last ? null : (
        <span aria-hidden className="absolute bottom-0 left-[1.0625rem] top-9 w-px bg-border" />
      )}
      {setting ? (
        <Toggle phase={phase} setting={setting} draft={draft} onChange={onChange} />
      ) : (
        <Fixed phase={phase} />
      )}
      <span className="flex min-w-0 flex-col gap-1 pt-1.5">
        <span className="truncate font-condensed uppercase leading-tight text-small text-foreground">
          {phase.label}
        </span>
        {/* Effort and model share one line and the label has its own. The other way round
            left «ETIQUETABILIDAD» 83px at the narrowest column, which is the clipping this
            layout exists to end — and a node is identified by its name long before it is
            identified by how hard it thinks. */}
        <span className="flex items-center gap-1.5">
          {effortSetting && thinks ? (
            <NodeEffort phase={phase} setting={effortSetting} draft={draft} onChange={onChange} />
          ) : null}
          {modelSetting && !ownModel ? (
            <span
              className="min-w-0 flex-1 truncate font-mono text-micro text-muted-foreground"
              title={t("pipe.modelTitle", { model: residentName })}
            >
              {residentName}
            </span>
          ) : modelSetting ? (
            <NodeModel
              phase={phase}
              setting={modelSetting}
              draft={draft}
              models={models}
              onChange={onChange}
            />
          ) : null}
        </span>
      </span>
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

// The same choice the «Modelos» rows offered, shrunk to fit under a node: what the engine has
// on disk, «principal» (null) first for an override, «Otro…» for a model not pulled yet. The
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

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Undo2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { Alert, Checkbox, Spinner, Switch } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { bytes } from "@/lib/format";
import { EFFORT_LABELS, fixedEffort, type EffortLevel } from "@/features/generate/effort";
import { familyOf } from "@/features/generate/models";
import { useT, type Key, type Translate } from "@/lib/i18n";
import type {
  ConfigImpact,
  ConfigPayload,
  ConfigSetting,
  ConfigSource,
  InstalledModel,
} from "@/lib/types";
import { cn } from "@/lib/utils";

/* The field-level machinery of the configuration, shared by the two screens that edit
   settings: "Configuración" and the "Motor" tab. It is not imported from either — a page is
   not a library, and a second reader is when that stops being a matter of taste. */

export const SOURCE_LABELS: Record<ConfigSource, Key> = {
  default: "cfg.source.default",
  file: "cfg.source.file",
  env: "cfg.source.env",
};

// Not tuning knobs of the same kind: `reindex` says so in its own message ("invalidará los
// contextos Y..."), which is why it outranks `contexts` rather than sitting beside it.
// `none` and `locked` carry no save-time warning of their own — nothing in the contract
// says what one would read — so they simply never win the highest-severity comparison.
export const IMPACT_SEVERITY: Record<ConfigImpact, number> = {
  none: 0,
  engine: 1,
  contexts: 2,
  reindex: 3,
  locked: 4,
};

export const IMPACT_MESSAGES: Partial<Record<ConfigImpact, Key>> = {
  contexts: "cfg.impact.contexts",
  reindex: "cfg.impact.reindex",
  engine: "cfg.impact.engine",
};

export function sameValue(a: unknown, b: unknown): boolean {
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

export function formatValue(value: unknown, t: Translate["t"]): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "boolean") return t(value ? "cfg.on" : "cfg.off");
  // A map reads as its pairs: the one setting shaped like this is the effort each locked
  // model is called with, and `String()` on it says "[object Object]" in the save bar.
  if (typeof value === "object") {
    const pairs = Object.entries(value as Record<string, unknown>);
    return pairs.length ? pairs.map(([key, item]) => `${key}: ${String(item)}`).join(", ") : "—";
  }
  return String(value);
}


export function GroupCard({
  title,
  settings,
  draft,
  onChange,
  onReset,
  models,
  offered,
  levels,
  onLevels,
}: {
  title: string | null;
  settings: ConfigSetting[];
  draft: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  onReset: (key: string) => void;
  models: ConfigPayload["models"] | null;
  /** Forwarded to `SettingRow` for the one field whose rows ARE the offered models. */
  offered?: string[];
  /** The same field's other half: with which level each locked model is called. */
  levels?: Record<string, string>;
  onLevels?: (next: Record<string, string>) => void;
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
            offered={offered}
            levels={levels}
            onLevels={onLevels}
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

export function isModelSetting(setting: ConfigSetting): boolean {
  return setting.key.startsWith("models.") && setting.kind === "str";
}

const OTHER = "__other__";

// The choice is among what the engine has on disk, because a name typed by hand is a typo
// waiting for the first call. "Otro…" keeps the free text for a model not pulled yet, and
// a phase keeps "Seguir al principal" (null) as its first option, which is what every
// override defaults to.
export function ModelSelect({
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
  const { t } = useT();
  const installed = models.installed;
  const known = installed.some((m) => m.model === value);
  const [other, setOther] = useState(() => Boolean(value) && !known);
  const residentVram = new Map(models.running.map((m) => [m.model, m.size_vram]));

  const describe = (model: InstalledModel) => {
    if (model.remote) return t("cfg.modelRemote", { model: model.model });
    const vram = residentVram.get(model.model);
    if (vram) return t("cfg.modelLoaded", { model: model.model, size: bytes(vram) });
    return model.size
      ? t("cfg.modelOnDisk", { model: model.model, size: bytes(model.size) })
      : model.model;
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
        {setting.nullable ? (
          <option value="">
            {t("cfg.followMain")}
          </option>
        ) : null}
        {value && !known && !other ? (
          <option value={value}>{t("cfg.notInstalled", { model: value })}</option>
        ) : null}
        {installed.map((model) => (
          <option key={model.model} value={model.model}>
            {describe(model)}
          </option>
        ))}
        <option value={OTHER}>{t("cfg.other")}</option>
      </Select>
      {other ? (
        <Input
          aria-label={t("cfg.modelName", { label })}
          placeholder={t("eng.models.pullPlaceholder")}
          disabled={disabled}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value || null)}
        />
      ) : null}
      {installed.length === 0 ? (
        <p className="text-small text-muted-foreground">
          {t("cfg.noEngineList")}
        </p>
      ) : null}
    </div>
  );
}

export function CerebrasModelsField({
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
  const { t } = useT();
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
          {t("cfg.cerebrasLoading")}
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
          {catalog.data?.error ?? t("cfg.cerebrasDown")} {t("cfg.commaSeparated")}
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
              label={t("cfg.routeTo", { model })}
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
              label={t("cfg.routeTo", { model })}
            />
            <span className="font-mono text-body">{model}</span>
            <Badge variant="outline">{t("cfg.offCatalog")}</Badge>
          </li>
        ))}
      </ul>
      <p className="text-small text-muted-foreground">
        {t("cfg.cerebrasNote")}
      </p>
    </div>
  );
}

/**
 * Which models a commission may be written with, and which of them is the default.
 *
 * A LIST and not a single model: the difference between two offered models is minutes of
 * waiting against how much the model deliberates, which is the trade-off of whoever asks
 * for the exercise. What stays the installation's is the SHORTLIST.
 *
 * ORDER IS MEANING — the first one is what everything that does not choose is written with:
 * the CLI and any request naming none. Chosen ones are listed first,
 * in their stored order; checking one appends it. A list of one is legal and simply hides
 * the chooser on the generate screen.
 *
 * A name CAN BE TYPED, and that is not a convenience: the rows are the engine's listing,
 * which is empty whenever the engine does not answer — exactly when somebody comes here to
 * point the installation at another model. It also covers the model that is not pulled yet,
 * which is a supported state drawn as "sin instalar".
 */
export function GenerationModelsField({
  id,
  label,
  value,
  disabled,
  models,
  onChange,
}: {
  id: string;
  label: string;
  value: unknown;
  disabled: boolean;
  models: ConfigPayload["models"] | null;
  onChange: (next: unknown) => void;
}) {
  const { t } = useT();
  const selected = Array.isArray(value) ? value.map(String) : [];
  const installed = models?.installed ?? [];
  const residentVram = new Map((models?.running ?? []).map((m) => [m.model, m.size_vram]));
  // The chosen ones first, in the order they are offered in; then whatever else the engine
  // can serve. A name in neither is one the engine does not have, and it is kept visible:
  // dropping it would silently un-offer it on the next save.
  const rest = installed.map((m) => m.model).filter((m) => !selected.includes(m));
  const rows = [...selected, ...rest];
  const known = new Map(installed.map((m) => [m.model, m]));

  const toggle = (model: string, next: boolean) =>
    onChange(next ? [...selected, model] : selected.filter((name) => name !== model));
  const promote = (model: string) =>
    onChange([model, ...selected.filter((name) => name !== model)]);

  const [typed, setTyped] = useState("");
  const name = typed.trim();
  const addable = name !== "" && !selected.includes(name);
  const add = () => {
    if (!addable) return;
    onChange([...selected, name]);
    setTyped("");
  };

  return (
    <div className="space-y-1.5">
      <span className="text-body" id={id}>
        {label}
      </span>
      <ul aria-labelledby={id} className="space-y-1.5">
        {rows.map((model) => {
          const info = known.get(model);
          const chosen = selected.includes(model);
          const family = familyOf(model);
          const vram = residentVram.get(model);
          return (
            <li
              key={model}
              className={cn(
                "flex flex-wrap items-center gap-x-2 gap-y-1 border p-2",
                chosen ? "border-primary bg-primary/5" : "border-border",
              )}
            >
              <Checkbox
                checked={chosen}
                disabled={disabled}
                onCheckedChange={(next) => toggle(model, next)}
                label={t("cfg.offered.offer", { model })}
              />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-body font-medium">{family.label || model}</span>
                  <span className="font-mono text-[12px] text-muted-foreground">{model}</span>
                </span>
              </span>
              {chosen && model === selected[0] ? (
                <Badge variant="secondary">{t("cfg.offered.default")}</Badge>
              ) : null}
              {info?.remote ? <Badge variant="outline">{t("cfg.offered.remote")}</Badge> : null}
              {!info ? <Badge variant="outline">{t("cfg.offered.absent")}</Badge> : null}
              {vram ? (
                <span className="text-small nums text-muted-foreground">{bytes(vram)}</span>
              ) : null}
              {chosen && model !== selected[0] ? (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={disabled}
                  onClick={() => promote(model)}
                >
                  {t("cfg.offered.makeDefault")}
                </Button>
              ) : null}
            </li>
          );
        })}
      </ul>
      {selected.length === 0 ? (
        <p className="text-small text-destructive">{t("cfg.offered.none")}</p>
      ) : null}
      <div className="flex items-end gap-2">
        <div className="min-w-0 flex-1 space-y-1">
          <Label htmlFor={`${id}-add`}>{t("cfg.offered.addLabel")}</Label>
          <Input
            id={`${id}-add`}
            placeholder={t("eng.models.pullPlaceholder")}
            disabled={disabled}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              add();
            }}
          />
        </div>
        <Button variant="outline" size="sm" disabled={disabled || !addable} onClick={add}>
          {t("cfg.offered.add")}
        </Button>
      </div>
      <p className="text-small text-muted-foreground">
        {installed.length === 0 ? t("cfg.noEngineList") : t("cfg.offered.hint")}
      </p>
    </div>
  );
}


/**
 * Which offered models let their reasoning effort be adjusted when an exercise is asked for.
 *
 * One row per offered model, and the rows come from the OTHER setting's DRAFT rather than
 * from what is saved: unchecking a model above and locking it below in one visit has to
 * work, and the save bar sends both keys in one request.
 *
 * The switch is phrased positively — "can be adjusted" — while the setting stores the
 * negative. Not a mismatch to tidy: locking is the exception, so the setting's default is
 * the empty list, and what a person reads is the question they are answering.
 *
 * A name in the setting that is no longer offered keeps its row, at the foot and marked:
 * dropping it silently throws away a measurement the next save cannot recover, which is
 * also why the setting does not validate against the offer.
 *
 * A locked row also says with WHICH LEVEL it is called — the other half of the same
 * decision, so the same row. It writes into a second setting, so the level survives taking
 * the lock off for an afternoon: it is kept and simply not read.
 */
export function FixedEffortField({
  id,
  label,
  value,
  disabled,
  offered,
  levels,
  onChange,
  onLevels,
}: {
  id: string;
  label: string;
  value: unknown;
  disabled: boolean;
  offered: string[];
  /** `generation.fixed_effort_levels` as it stands in the draft, model to level. */
  levels: Record<string, string>;
  onChange: (next: unknown) => void;
  onLevels: (next: Record<string, string>) => void;
}) {
  const { t } = useT();
  const fixed = Array.isArray(value) ? value.map(String) : [];
  const orphans = fixed.filter((model) => !offered.includes(model));
  const rows = [...offered, ...orphans];

  const set = (model: string, adjustable: boolean) =>
    onChange(adjustable ? fixed.filter((name) => name !== model) : [...fixed, model]);

  // An empty choice is "the one the engine resolves", which is an absence and not a value:
  // it is what the setting means by a locked model it does not name.
  const setLevel = (model: string, level: string) => {
    if (level) {
      onLevels({ ...levels, [model]: level });
      return;
    }
    const { [model]: _dropped, ...rest } = levels;
    onLevels(rest);
  };

  return (
    <div className="space-y-1.5">
      <span className="text-body" id={id}>
        {label}
      </span>
      {rows.length === 0 ? (
        <p className="text-small text-muted-foreground">{t("cfg.effort.noModels")}</p>
      ) : (
        <ul aria-labelledby={id} className="space-y-1.5">
          {rows.map((model) => {
            const adjustable = !fixed.includes(model);
            const family = familyOf(model);
            // Read exactly as the generate screen reads it, through the same function, so
            // the note here cannot claim a level the form does not draw.
            const declared = adjustable ? null : fixedEffort(model, levels, family);
            return (
              <li
                key={model}
                className="flex flex-wrap items-center gap-x-2 gap-y-1 border border-border p-2"
              >
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-body font-medium">{family.label || model}</span>
                    <span className="font-mono text-[12px] text-muted-foreground">{model}</span>
                  </span>
                  <span className="mt-0.5 block text-small text-muted-foreground">
                    {adjustable
                      ? t("cfg.effort.adjustableNote", { levels: family.levels.length })
                      : declared
                        ? t("cfg.effort.fixedNoteLevel", {
                            level: t(EFFORT_LABELS[declared]).toLowerCase(),
                          })
                        : t("cfg.effort.fixedNote")}
                  </span>
                </span>
                {!offered.includes(model) ? (
                  <Badge variant="outline">{t("cfg.effort.notOffered")}</Badge>
                ) : null}
                {adjustable ? null : (
                  <Select
                    className="w-auto"
                    aria-label={t("cfg.effort.levelFor", { model })}
                    value={levels[model] ?? ""}
                    disabled={disabled}
                    onChange={(event) => setLevel(model, event.target.value)}
                  >
                    <option value="">{t("cfg.effort.engineLevel")}</option>
                    {family.levels.map((level: EffortLevel) => (
                      <option key={level} value={level}>
                        {t(EFFORT_LABELS[level])}
                      </option>
                    ))}
                  </Select>
                )}
                <Switch
                  checked={adjustable}
                  disabled={disabled}
                  onCheckedChange={(next) => set(model, next)}
                  label={t("cfg.effort.toggle", { model })}
                />
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-small text-muted-foreground">{t("cfg.effort.hint")}</p>
      <p className="text-small text-muted-foreground">{t("cfg.effort.hintLevel")}</p>
    </div>
  );
}


export function SettingRow({
  setting,
  value,
  onChange,
  onReset,
  models,
  offered,
  levels,
  onLevels,
}: {
  setting: ConfigSetting;
  value: unknown;
  onChange: (next: unknown) => void;
  onReset: () => void;
  models: ConfigPayload["models"] | null;
  /** The offered models as they stand in the draft. Only `generation.fixed_effort` reads
   *  it: its rows ARE that list, and it has to follow an edit made in the same visit. */
  offered?: string[];
  /** `generation.fixed_effort_levels` and its setter, for that same row: locking a model
   *  and saying at which level it is then called are one decision with two settings. */
  levels?: Record<string, string>;
  onLevels?: (next: Record<string, string>) => void;
}) {
  const { t } = useT();
  const label = setting.name || setting.key;
  const id = `config-${setting.key}`;
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;
  // Only a value that actually left the default has anything to go back to; a file value
  // equal to the default is the same number with a different badge. A row that cannot be
  // edited cannot be reset either — `settings.reset` refuses a locked key — so offering the
  // button there would be offering a call that answers 400.
  const resettable =
    setting.editable &&
    setting.source === "file" &&
    !setting.secret &&
    !sameValue(setting.value, setting.default);

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {setting.secret ? (
            <div className="flex items-center justify-between gap-2">
              <span className="text-body">{label}</span>
              <Badge variant="outline">
                {setting.state === "configurada" ? t("cfg.configured") : t("cfg.absent")}
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
          ) : setting.key === "generation.models" ? (
            <GenerationModelsField
              id={id}
              label={label}
              value={value}
              disabled={disabled}
              models={models}
              onChange={onChange}
            />
          ) : setting.key === "generation.fixed_effort" ? (
            <FixedEffortField
              id={id}
              label={label}
              value={value}
              disabled={disabled}
              offered={offered ?? []}
              levels={levels ?? {}}
              onChange={onChange}
              onLevels={onLevels ?? (() => undefined)}
            />
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
                {setting.nullable ? <option value="">{t("cfg.unset")}</option> : null}
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
              <p className="text-small text-muted-foreground">{t("cfg.commaSeparated")}</p>
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
            {t(SOURCE_LABELS[setting.source])}
          </Badge>
          {resettable ? (
            <Button
              variant="ghost"
              size="sm"
              title={t("cfg.backTo", { value: formatValue(setting.default, t) })}
              onClick={onReset}
            >
              <Undo2 />
              {t("cfg.default")}
            </Button>
          ) : null}
        </div>
      </div>

      {/* A disabled control with nothing beside it reads as a bug. The environment already
          said why; a setting the registry marks as not editable has to say so too, and
          where it IS changed — the file, and a restart. */}
      {lockedByEnv ? (
        <p className="text-small text-muted-foreground">
          {t("cfg.fixedBy", { env: setting.env ?? "" })}
        </p>
      ) : !setting.editable ? (
        <p className="text-small text-muted-foreground">{t("cfg.notEditable")}</p>
      ) : null}

      {setting.doc ? (
        <details className="text-small text-muted-foreground">
          <summary className="cursor-pointer select-none">{t("cfg.whyThisValue")}</summary>
          <p className="mt-1 whitespace-pre-wrap">{setting.doc}</p>
        </details>
      ) : null}
    </div>
  );
}

export function DiffSummary({
  settings,
  draft,
}: {
  settings: ConfigSetting[];
  draft: Record<string, unknown>;
}) {
  const { t } = useT();
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
        {t("cfg.pending", { n: touched.length })}
      </p>
      <ul className="space-y-1 text-body">
        {touched.map((setting) => (
          <li key={setting.key} className="flex flex-wrap items-baseline gap-1.5">
            <span className="font-medium">{setting.name || setting.key}</span>
            <span className="text-muted-foreground">
              {formatValue(setting.value ?? setting.default, t)} →{" "}
              {formatValue(draft[setting.key], t)}
            </span>
          </li>
        ))}
      </ul>
      {warning ? (
        <Alert tone="attention" title={t("cfg.beforeSaving")}>
          <p>{t(warning)}</p>
        </Alert>
      ) : null}
    </div>
  );
}


/* THE DRAFT IS PER SCREEN, NOT PER APPLICATION. Only one admin tab is mounted at a time,
   so two drafts can never be open at once; what this buys is that the "Motor" tab saves
   its sixteen settings without owning the other hundred and twenty-five. `sameValue` is
   what keeps a value typed back to what was stored from ever counting as a change. */
export function useConfigDraft(stored: Map<string, unknown>) {
  const { t } = useT();
  const client = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState<Record<string, unknown>>({});

  const save = useMutation({
    mutationFn: () => api.updateAdminConfig(draft),
    onSuccess: () => {
      setDraft({});
      client.invalidateQueries({ queryKey: ["admin", "config"] });
      client.invalidateQueries({ queryKey: ["health"] });
      toast({ title: t("cfg.saved") });
    },
  });

  const reset = useMutation({
    mutationFn: (key: string) => api.resetAdminConfig([key]),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin", "config"] });
      client.invalidateQueries({ queryKey: ["health"] });
    },
  });

  const change = (key: string, value: unknown) =>
    setDraft((current) => {
      const next = { ...current };
      if (sameValue(value, stored.get(key))) delete next[key];
      else next[key] = value;
      return next;
    });

  return {
    draft,
    change,
    discard: () => setDraft({}),
    save,
    reset,
    dirty: Object.keys(draft).length > 0,
    valueOf: (setting: ConfigSetting) =>
      setting.key in draft ? draft[setting.key] : (setting.value ?? setting.default),
  };
}


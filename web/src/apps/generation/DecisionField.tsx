import { Input } from "@/components/ui/input";
import { baseType, enumValues } from "@/features/profile/FieldEditor";
import { readableValue } from "@/lib/text";
import type { FieldSpec } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT, type Translate } from "@/lib/i18n";

function Choice({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "rounded-lg border px-3 py-1.5 text-body font-medium transition-colors",
        active
          ? "border-primary bg-primary/10 text-primary"
          : "border-border text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
}

/**
 * The control for one field the profile marks `decided_by: "user"`.
 *
 * `undefined` is the whole point: it means the field is not pinned, so the model picks
 * it. That is why every control offers "Cualquiera" explicitly instead of defaulting to
 * the first option — silently pinning "básico" because it happens to be first would put
 * a decision in the prompt that nobody made.
 */
export function DecisionField({
  name,
  spec,
  value,
  onChange,
}: {
  name: string;
  spec: FieldSpec;
  value: unknown;
  onChange: (next: unknown) => void;
}) {
  const { t } = useT();
  const type = baseType(spec.schema);
  const label = spec.description?.split(/[.:]/)[0]?.trim();

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-small text-muted-foreground">{name}</span>
        {label ? (
          <span className="min-w-0 truncate text-small text-muted-foreground/70">{label}</span>
        ) : null}
      </div>

      {type === "enum" ? (
        <div className="flex flex-wrap gap-1.5">
          {enumValues(spec.schema).map((option) => (
            <Choice
              key={option}
              label={readableValue(option)}
              active={value === option}
              onClick={() => onChange(value === option ? undefined : option)}
            />
          ))}
          <Choice
            label={t("decision.any")}
            active={value === undefined}
            onClick={() => onChange(undefined)}
          />
        </div>
      ) : type === "boolean" ? (
        <div className="flex flex-wrap gap-1.5">
          <Choice label={t("common.yes")} active={value === true} onClick={() => onChange(true)} />
          <Choice label={t("common.no")} active={value === false} onClick={() => onChange(false)} />
          <Choice
            label={t("decision.any")}
            active={value === undefined}
            onClick={() => onChange(undefined)}
          />
        </div>
      ) : (
        <Input
          aria-label={label}
          type={type === "integer" || type === "number" ? "number" : "text"}
          value={value === undefined || value === null ? "" : String(value)}
          placeholder={t("decision.anyModel", { any: t("decision.any") })}
          onChange={(event) => {
            const raw = event.target.value;
            if (!raw.trim()) return onChange(undefined);
            onChange(type === "integer" || type === "number" ? Number(raw) : raw);
          }}
        />
      )}
    </div>
  );
}

export function describeDecision(name: string, value: unknown, t: Translate["t"]): string {
  if (value === undefined || value === null || value === "")
    return t("decision.anyOf", { name: name });
  if (value === true) return t("decision.yesOf", { name: name });
  if (value === false) return t("decision.noOf", { name: name });
  return `${name}: ${value}`;
}

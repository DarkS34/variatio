import {
  ArrowDown,
  ArrowUp,
  Braces,
  Calculator,
  ChevronDown,
  Hash,
  List,
  ListChecks,
  Star,
  ToggleLeft,
  Trash2,
  Type,
} from "lucide-react";
import { useEffect, useState, type ComponentType, type ReactElement, type ReactNode } from "react";

import { useStageLocked, useStageLockedHint } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChipInput } from "@/components/ui/chips";
import { Field } from "@/components/ui/field";
import { InfoHint } from "@/components/ui/hint";
import { Input, Textarea } from "@/components/ui/input";
import type { FieldSpec } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT, type Key, type Translate } from "@/lib/i18n";

export type FieldType =
  | "string"
  | "enum"
  | "integer"
  | "number"
  | "boolean"
  | "array"
  | "object";

type TypeMeta = {
  value: FieldType;
  labelKey: Key;
  icon: ComponentType<{ className?: string }>;
  captionKey: Key;
};

const TYPES: TypeMeta[] = [
  { value: "string", labelKey: "fieldType.string", icon: Type, captionKey: "fieldType.string.caption" },
  { value: "enum", labelKey: "fieldType.enum", icon: ListChecks, captionKey: "fieldType.enum.caption" },
  { value: "integer", labelKey: "fieldType.integer", icon: Hash, captionKey: "fieldType.integer.caption" },
  { value: "number", labelKey: "fieldType.number", icon: Calculator, captionKey: "fieldType.number.caption" },
  { value: "boolean", labelKey: "fieldType.boolean", icon: ToggleLeft, captionKey: "fieldType.boolean.caption" },
  { value: "array", labelKey: "fieldType.array", icon: List, captionKey: "fieldType.array.caption" },
  { value: "object", labelKey: "fieldType.object", icon: Braces, captionKey: "fieldType.object.caption" },
];

const ITEM_TYPES = TYPES.filter((meta) => meta.value !== "array" && meta.value !== "object");

const META: Record<FieldType, TypeMeta> = Object.fromEntries(
  TYPES.map((meta) => [meta.value, meta]),
) as Record<FieldType, TypeMeta>;

// Mirrors ExemplarsProfile.NAME_RE and RESERVED_FIELD_NAMES: the names become Python
// identifiers, so accents and ñ are out even though the vocabulary itself is Spanish.
const NAME_PATTERN = /^[a-z][a-z0-9_]*$/;

const RESERVED = ["item_type", "id", "source", "concepts", "primary_concept"];

export function nameError(
  candidate: string,
  taken: string[],
  { t }: Translate,
  current?: string,
): string | null {
  const value = candidate.trim();
  if (!value) return t("field.name.empty");
  if (!NAME_PATTERN.test(value)) return t("field.name.pattern");
  if (value !== current && taken.includes(value)) return t("field.name.taken");
  return null;
}

export function fieldNameError(
  candidate: string,
  taken: string[],
  tr: Translate,
  current?: string,
): string | null {
  const error = nameError(candidate, taken, tr, current);
  if (error) return error;
  if (RESERVED.includes(candidate.trim()))
    return tr.t("field.name.reserved", { name: candidate.trim() });
  return null;
}

export function baseType(schema: Record<string, any>): FieldType {
  if (Array.isArray(schema.enum)) return "enum";
  const type = schema.type;
  if (Array.isArray(type))
    return (type.find((entry: unknown) => entry && entry !== "null") ?? "string") as FieldType;
  return (type ?? "string") as FieldType;
}

function typeAllowsNull(schema: Record<string, any>): boolean {
  const type = schema.type;
  return Array.isArray(type) && type.some((entry: unknown) => entry === null || entry === "null");
}

function enumAllowsNull(schema: Record<string, any>): boolean {
  return Array.isArray(schema.enum) && schema.enum.some((value: unknown) => value === null);
}

export function isNullable(schema: Record<string, any>): boolean {
  return typeAllowsNull(schema) || enumAllowsNull(schema);
}

export function enumValues(schema: Record<string, any>): string[] {
  return (Array.isArray(schema.enum) ? schema.enum : [])
    .filter((value: unknown) => value !== null)
    .map(String);
}

export function describeType(schema: Record<string, any>, { t, plural }: Translate): string {
  const type = baseType(schema);
  if (type === "enum") return plural("field.options", enumValues(schema).length);
  if (type === "array")
    return t("fieldType.arrayOf", {
      type: t(META[baseType(schema.items ?? {})].labelKey).toLowerCase(),
    });
  return t(META[type].labelKey);
}

function rebuild(schema: Record<string, any>, type: FieldType, nullable: boolean) {
  const next: Record<string, any> = {};

  if (type === "enum") {
    const values: unknown[] = enumValues(schema);
    next.type = nullable ? ["string", "null"] : "string";
    next.enum = nullable ? [...values, null] : values;
  } else if (type === "array") {
    next.type = nullable ? ["array", "null"] : "array";
    next.items = schema.items ?? { type: "string" };
  } else {
    next.type = nullable ? [type, "null"] : type;
    if (type === "string") {
      if (schema.minLength !== undefined) next.minLength = schema.minLength;
      if (schema.maxLength !== undefined) next.maxLength = schema.maxLength;
    }
    if (type === "integer" || type === "number") {
      if (schema.minimum !== undefined) next.minimum = schema.minimum;
      if (schema.maximum !== undefined) next.maximum = schema.maximum;
    }
  }

  if ("default" in schema && baseType(schema) === type) next.default = schema.default;
  return next;
}

function TypePicker({
  value,
  onChange,
  options = TYPES,
  disabled = false,
}: {
  value: FieldType;
  onChange: (next: FieldType) => void;
  options?: TypeMeta[];
  disabled?: boolean;
}) {
  const { t } = useT();
  const lockedHint = useStageLockedHint();
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map(({ value: option, labelKey, icon: Icon, captionKey }) => (
        <button
          key={option}
          type="button"
          disabled={disabled}
          title={disabled ? t(lockedHint) : t(captionKey)}
          aria-pressed={value === option}
          onClick={() => onChange(option)}
          className={cn(
            "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-small font-medium transition-colors",
            value === option
              ? "border-primary bg-primary/10 text-primary"
              : "border-border text-muted-foreground hover:bg-accent hover:text-foreground",
            disabled && "cursor-default opacity-60 hover:bg-transparent hover:text-muted-foreground",
          )}
        >
          <Icon className="size-3.5" />
          {t(labelKey)}
        </button>
      ))}
    </div>
  );
}

function Segmented({
  value,
  options,
  onChange,
  disabled = false,
  title,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (next: string) => void;
  disabled?: boolean;
  title?: string;
}) {
  return (
    <div
      title={title}
      className={cn(
        // `flex w-full` and not `inline-flex`: the ground already fills the container, so
        // with the buttons bunched to the left the right half is grey and means nothing.
        // With `flex-1` each option takes exactly its share.
        "flex w-full items-center gap-1 rounded-lg bg-muted p-1",
        disabled && "opacity-60",
      )}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          disabled={disabled}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "flex-1 rounded-md px-3 py-1 text-small font-medium transition-colors",
            value === option.value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
            disabled && "cursor-not-allowed hover:text-muted-foreground",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/**
 * The local label wrapper, and every control in this editor already goes through it — so
 * delegating to `Field` is what binds all nine at once instead of nine by hand.
 *
 * The hint stays OUTSIDE the <label>. It is a button, and a button inside a label makes
 * two click targets out of one: clicking to focus the field would sometimes open the hint
 * instead. `Field` renders the label itself, so the hint sits beside it in a row of its own.
 */
function Row({
  label,
  hint,
  error,
  description,
  children,
  className,
}: {
  label: string;
  hint?: ReactNode;
  error?: ReactNode;
  description?: ReactNode;
  children: ReactElement;
  className?: string;
}) {
  return (
    <Field
      label={
        hint ? (
          <span className="inline-flex items-center gap-1.5">
            {label}
            <InfoHint label={label}>{hint}</InfoHint>
          </span>
        ) : (
          label
        )
      }
      error={error}
      description={description}
      className={className}
    >
      {children}
    </Field>
  );
}

export function FieldEditor({
  name,
  spec,
  isPrimary,
  open,
  first,
  last,
  taken,
  onToggleOpen,
  onChange,
  onRename,
  onRemove,
  onMakePrimary,
  onMove,
}: {
  name: string;
  spec: FieldSpec;
  isPrimary: boolean;
  open: boolean;
  first: boolean;
  last: boolean;
  taken: string[];
  onToggleOpen: () => void;
  onChange: (next: FieldSpec) => void;
  onRename: (next: string) => void;
  onRemove: () => void;
  onMakePrimary: () => void;
  onMove: (direction: -1 | 1) => void;
}) {
  const tr = useT();
  const { t } = tr;
  const locked = useStageLocked();
  // What a control that is disabled RIGHT NOW should say about itself: the two locked
  // states name different ways out, so one sentence for both sends half the readers to a
  // button that is not on their screen.
  const lockedHint = useStageLockedHint();
  const [nameDraft, setNameDraft] = useState(name);

  useEffect(() => setNameDraft(name), [name]);

  const schema = spec.schema ?? {};
  const type = baseType(schema);
  const nullable = isNullable(schema);
  const Icon = META[type].icon;
  const nameError = nameDraft.trim() === name ? null : fieldNameError(nameDraft, taken, tr, name);
  const canBePrimary = type === "string";

  const setSchema = (patch: Record<string, any>) =>
    onChange({ ...spec, schema: { ...schema, ...patch } });
  const setType = (next: FieldType) => onChange({ ...spec, schema: rebuild(schema, next, nullable) });
  const setNullable = (next: boolean) => onChange({ ...spec, schema: rebuild(schema, type, next) });

  const commitName = () => {
    const next = nameDraft.trim();
    if (next === name || fieldNameError(next, taken, tr, name)) return;
    onRename(next);
  };

  const lengthInvalid =
    schema.minLength !== undefined &&
    schema.maxLength !== undefined &&
    schema.minLength > schema.maxLength;
  const rangeInvalid =
    schema.minimum !== undefined && schema.maximum !== undefined && schema.minimum > schema.maximum;
  const enumMismatch = type === "enum" && typeAllowsNull(schema) && !enumAllowsNull(schema);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border bg-card transition-colors",
        isPrimary ? "border-primary/40" : "border-border",
        open && "shadow-sm",
      )}
    >
      <div className="flex items-center gap-2 pr-2">
        <button
          type="button"
          onClick={onToggleOpen}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-center gap-2 p-3 text-left transition-colors hover:bg-accent/40"
        >
          <ChevronDown
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform",
              !open && "-rotate-90",
            )}
          />
          <Icon className="size-4 shrink-0 text-primary" />
          <span className="shrink-0 font-mono text-body font-medium">{name}</span>
          {isPrimary ? (
            <Badge className="shrink-0" title={t("field.primary.title")}>
              <Star className="fill-current" />
              {t("field.primary.badge")}
            </Badge>
          ) : null}
          <Badge variant="outline" className="shrink-0">
            {describeType(schema, tr)}
          </Badge>
          <Badge variant={nullable ? "outline" : "secondary"} className="shrink-0">
            {nullable ? t("field.optional") : t("field.obligatory")}
          </Badge>
          {!open && spec.description ? (
            <span className="min-w-0 truncate text-small text-muted-foreground">
              {spec.description}
            </span>
          ) : null}
        </button>

        <div className="flex shrink-0 items-center gap-0.5">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onMakePrimary}
            disabled={isPrimary || !canBePrimary || locked}
            title={
              isPrimary
                ? t("field.primary.already")
                : locked
                  ? t(lockedHint)
                  : canBePrimary
                    ? t("field.primary.make")
                    : t("field.primary.onlyText")
            }
          >
            <Star className={cn(isPrimary && "fill-current text-primary")} />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onMove(-1)}
            disabled={first || locked}
            title={locked ? t(lockedHint) : t("field.moveUp")}
          >
            <ArrowUp />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onMove(1)}
            disabled={last || locked}
            title={locked ? t(lockedHint) : t("field.moveDown")}
          >
            <ArrowDown />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onRemove}
            disabled={isPrimary || locked}
            title={
              isPrimary
                ? t("field.primary.noDelete")
                : locked
                  ? t(lockedHint)
                  : t("field.delete")
            }
            className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 />
          </Button>
        </div>
      </div>

      {open ? (
        <div className="animate-fade-in space-y-4 border-t border-border p-4">
          {/* What it is called and what it is, in two columns and in that order, with
              "Obligatoriedad" under the name: the type picker is seven buttons in two rows
              plus its explanation, so the column beside it would be a text field over a
              hand's width of nothing. The three questions about the FORM of a field are
              together and the two columns end level.

              Neither "Longitud" nor "Rango" nor "Quién lo decide" is asked: all three are
              the shape of the schema and not of the subject — a minimum and a maximum of
              characters are a constraint nobody can set without measuring, and who decides a
              field is a decision about the generate form. What the profile brings is kept in
              the artifact and simply not asked about; the two notices below stay, because an
              imported profile can carry an impossible range and it has to be visible. */}
          <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
            <div className="space-y-4">
              <Row
                label={t("field.name.label")}
                hint={t("field.name.hint")}
                error={nameError}
              >
                <Input
                  value={nameDraft}
                  readOnly={locked}
                  onChange={(event) => setNameDraft(event.target.value)}
                  onBlur={commitName}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") event.currentTarget.blur();
                    if (event.key === "Escape") setNameDraft(name);
                  }}
                  className={cn("font-mono", nameError && "border-destructive")}
                />
              </Row>

              <Row label={t("field.required.label")} hint={t("field.required.hint")}>
                <Segmented
                  value={nullable ? "optional" : "required"}
                  disabled={locked}
                  title={locked ? t(lockedHint) : undefined}
                  onChange={(next) => setNullable(next === "optional")}
                  options={[
                    { value: "required", label: t("field.required.required") },
                    { value: "optional", label: t("field.required.optional") },
                  ]}
                />
              </Row>
            </div>

            <Row label={t("field.type.label")} description={t(META[type].captionKey)}>
              <TypePicker value={type} onChange={setType} disabled={locked} />
            </Row>
          </div>

          {lengthInvalid ? (
            <p className="text-small text-destructive">{t("field.length.invalid")}</p>
          ) : null}
          {rangeInvalid ? (
            <p className="text-small text-destructive">{t("field.range.invalid")}</p>
          ) : null}

          {type === "enum" ? (
            <Row
              label={t("field.enum.label")}
              hint={t("field.enum.hint")}
              error={enumValues(schema).length === 0 ? t("field.enum.empty") : null}
              description={
                enumMismatch ? (
                  <span className="flex items-center gap-2 text-attention">
                    {t("field.enum.mismatch")}
                    {locked ? null : (
                      <button
                        type="button"
                        onClick={() => setNullable(true)}
                        className="underline underline-offset-2"
                      >
                        {t("field.enum.fix")}
                      </button>
                    )}
                  </span>
                ) : null
              }
            >
              <ChipInput
                values={enumValues(schema)}
                disabled={locked}
                onChange={(values) =>
                  setSchema({ enum: nullable ? [...values, null] : values })
                }
                placeholder={t("field.enum.placeholder")}
                hint={
                  nullable ? t("field.enum.nullableHint") : t("field.enum.chipHint")
                }
              />
            </Row>
          ) : null}

          {/* Two real controls here, so the chips leave the field and name themselves: a
              label binds to exactly one, and pointing it at the picker while the chips sit
              underneath would be a label that lies about what it names. */}
          {type === "array" ? (
            <div className="space-y-2">
              <Row label={t("field.items.label")}>
                <TypePicker
                  disabled={locked}
                  value={baseType(schema.items ?? {})}
                  onChange={(next) =>
                    setSchema({
                      items:
                        next === "enum"
                          ? { type: "string", enum: enumValues(schema.items ?? {}) }
                          : { type: next },
                    })
                  }
                  options={ITEM_TYPES}
                />
              </Row>
              {baseType(schema.items ?? {}) === "enum" ? (
                <ChipInput
                  aria-label={t("field.items.values")}
                  disabled={locked}
                  values={enumValues(schema.items ?? {})}
                  onChange={(values) => setSchema({ items: { type: "string", enum: values } })}
                  placeholder={t("field.items.placeholder")}
                />
              ) : null}
            </div>
          ) : null}

          {type === "object" ? (
            <p className="rounded-lg border border-dashed border-border p-3 text-small text-muted-foreground">
              {t("field.object.note")}
            </p>
          ) : null}

          <Row label={t("field.description.label")} hint={t("field.description.hint")}>
            <Textarea
              autoGrow
              value={spec.description ?? ""}
              readOnly={locked}
              onChange={(event) => onChange({ ...spec, description: event.target.value })}
              placeholder={t("field.description.placeholder")}
              className="min-h-16"
            />
          </Row>

        </div>
      ) : null}
    </div>
  );
}

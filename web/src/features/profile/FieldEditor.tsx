import {
  ArrowDown,
  ArrowUp,
  Braces,
  Calculator,
  ChevronDown,
  FileSearch,
  Hash,
  List,
  ListChecks,
  Star,
  ToggleLeft,
  Trash2,
  Type,
  Wand2,
} from "lucide-react";
import { useEffect, useState, type ComponentType, type ReactElement, type ReactNode } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { LOCKED_HINT, useStageLocked } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChipInput } from "@/components/ui/chips";
import { Field } from "@/components/ui/field";
import { InfoHint } from "@/components/ui/hint";
import { Input, Textarea } from "@/components/ui/input";
import type { FieldSpec } from "@/lib/types";
import { cn } from "@/lib/utils";

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
  label: string;
  icon: ComponentType<{ className?: string }>;
  caption: string;
};

const TYPES: TypeMeta[] = [
  { value: "string", label: "Texto", icon: Type, caption: "Texto libre: una línea o varios párrafos." },
  { value: "enum", label: "Opciones", icon: ListChecks, caption: "Uno de una lista cerrada de valores." },
  { value: "integer", label: "Entero", icon: Hash, caption: "Número sin decimales." },
  { value: "number", label: "Decimal", icon: Calculator, caption: "Número con decimales." },
  { value: "boolean", label: "Sí / No", icon: ToggleLeft, caption: "Verdadero o falso." },
  { value: "array", label: "Lista", icon: List, caption: "Varios valores del mismo tipo." },
  { value: "object", label: "Objeto", icon: Braces, caption: "Objeto libre: su interior no se valida." },
];

const ITEM_TYPES = TYPES.filter((meta) => meta.value !== "array" && meta.value !== "object");

const META: Record<FieldType, TypeMeta> = Object.fromEntries(
  TYPES.map((meta) => [meta.value, meta]),
) as Record<FieldType, TypeMeta>;

// Mirrors ExemplarsProfile.NAME_RE and RESERVED_FIELD_NAMES: the names become Python
// identifiers, so accents and ñ are out even though the vocabulary itself is Spanish.
const NAME_PATTERN = /^[a-z][a-z0-9_]*$/;

const RESERVED = ["item_type", "id", "source", "concepts", "primary_concept"];

export function nameError(candidate: string, taken: string[], current?: string): string | null {
  const value = candidate.trim();
  if (!value) return "El nombre no puede estar vacío";
  if (!NAME_PATTERN.test(value))
    return "En minúsculas, sin tildes ni ñ: solo a-z, números y guiones bajos, empezando por letra";
  if (value !== current && taken.includes(value)) return "Ya existe uno con ese nombre";
  return null;
}

export function fieldNameError(candidate: string, taken: string[], current?: string): string | null {
  const error = nameError(candidate, taken, current);
  if (error) return error;
  if (RESERVED.includes(candidate.trim()))
    return `«${candidate.trim()}» está reservado por el sistema`;
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

export function describeType(schema: Record<string, any>): string {
  const type = baseType(schema);
  if (type === "enum") {
    const total = enumValues(schema).length;
    return total === 1 ? "1 opción" : `${total} opciones`;
  }
  if (type === "array") return `lista de ${META[baseType(schema.items ?? {})].label.toLowerCase()}`;
  return META[type].label;
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
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map(({ value: option, label, icon: Icon, caption }) => (
        <button
          key={option}
          type="button"
          disabled={disabled}
          title={disabled ? LOCKED_HINT : caption}
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
          {label}
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
        "inline-flex items-center gap-1 rounded-lg bg-muted p-1",
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
            "rounded-md px-3 py-1 text-small font-medium transition-colors",
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

function NumberBox({
  value,
  onChange,
  placeholder,
  disabled = false,
}: {
  value: number | undefined;
  onChange: (next: number | undefined) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  return (
    <Input
      type="number"
      aria-label={placeholder}
      readOnly={disabled}
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(event) =>
        onChange(event.target.value === "" ? undefined : Number(event.target.value))
      }
      className="h-8 w-24"
    />
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
  const locked = useStageLocked();
  const [nameDraft, setNameDraft] = useState(name);
  const [showRaw, setShowRaw] = useState(false);
  const [editingRaw, setEditingRaw] = useState(false);
  const [rawText, setRawText] = useState("");
  const [rawError, setRawError] = useState<string | null>(null);

  useEffect(() => setNameDraft(name), [name]);

  const schema = spec.schema ?? {};
  const type = baseType(schema);
  const nullable = isNullable(schema);
  const Icon = META[type].icon;
  const nameError = nameDraft.trim() === name ? null : fieldNameError(nameDraft, taken, name);
  const canBePrimary = type === "string";
  // Mirrors ExemplarsProfile._validate_decided_by: the primary field IS the item, and a
  // list or a free object has no choice to put in front of whoever asks for the item.
  const undecidable =
    isPrimary || ((type === "array" || type === "object") && !Array.isArray(schema.enum));
  const decidedBy = spec.decided_by ?? "model";

  const setSchema = (patch: Record<string, any>) =>
    onChange({ ...spec, schema: { ...schema, ...patch } });
  const setType = (next: FieldType) => onChange({ ...spec, schema: rebuild(schema, next, nullable) });
  const setNullable = (next: boolean) => onChange({ ...spec, schema: rebuild(schema, type, next) });

  const commitName = () => {
    const next = nameDraft.trim();
    if (next === name || fieldNameError(next, taken, name)) return;
    onRename(next);
  };

  const applyRaw = () => {
    try {
      const parsed = JSON.parse(rawText);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        setRawError("El campo debe ser un objeto");
        return;
      }
      if (
        typeof parsed.schema !== "object" ||
        parsed.schema === null ||
        Array.isArray(parsed.schema)
      ) {
        setRawError("El campo debe declarar un objeto 'schema'");
        return;
      }
      setRawError(null);
      onChange(parsed as FieldSpec);
      setEditingRaw(false);
    } catch (error) {
      setRawError((error as Error).message);
    }
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
            <Badge className="shrink-0" title="Es el texto que se etiqueta y se embebe">
              <Star className="fill-current" />
              primario
            </Badge>
          ) : null}
          <Badge variant="outline" className="shrink-0">
            {describeType(schema)}
          </Badge>
          <Badge variant={nullable ? "outline" : "secondary"} className="shrink-0">
            {nullable ? "opcional" : "obligatorio"}
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
                ? "Ya es el campo primario"
                : locked
                  ? LOCKED_HINT
                  : canBePrimary
                    ? "Marcar como campo primario"
                    : "Solo un campo de texto puede ser el primario"
            }
          >
            <Star className={cn(isPrimary && "fill-current text-primary")} />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onMove(-1)}
            disabled={first || locked}
            title={locked ? LOCKED_HINT : "Subir"}
          >
            <ArrowUp />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onMove(1)}
            disabled={last || locked}
            title={locked ? LOCKED_HINT : "Bajar"}
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
                ? "El campo primario no se puede borrar"
                : locked
                  ? LOCKED_HINT
                  : "Eliminar campo"
            }
            className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 />
          </Button>
        </div>
      </div>

      {open ? (
        <div className="animate-fade-in space-y-4 border-t border-border p-4">
          <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
            <Row
              label="Nombre"
              hint="Es la clave del campo en cada ítem generado."
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

            <Row label="Tipo" description={META[type].caption}>
              <TypePicker value={type} onChange={setType} disabled={locked} />
            </Row>
          </div>

          <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
            <Row
              label="Obligatoriedad"
              hint="Un campo opcional puede quedar sin valor en un ítem; uno obligatorio siempre debe traerlo."
            >
              <Segmented
                value={nullable ? "optional" : "required"}
                disabled={locked}
                title={locked ? LOCKED_HINT : undefined}
                onChange={(next) => setNullable(next === "optional")}
                options={[
                  { value: "required", label: "Obligatorio" },
                  { value: "optional", label: "Opcional" },
                ]}
              />
            </Row>

            <Row
              label="Quién lo decide"
              hint="«Quien genera» hace que la pantalla de generación pregunte por este campo antes de lanzar. «El modelo» lo deja fuera del formulario y lo redacta él."
            >
              <Segmented
                value={decidedBy}
                disabled={undecidable || locked}
                title={
                  isPrimary
                    ? "El campo primario es el ítem en sí: no es una preferencia que se elija antes de generar"
                    : undecidable
                      ? "Una lista o un objeto libre no admiten un control con el que elegir antes de generar"
                      : locked
                        ? LOCKED_HINT
                        : undefined
                }
                onChange={(next) =>
                  onChange({ ...spec, decided_by: next === "user" ? "user" : undefined })
                }
                options={[
                  { value: "model", label: "El modelo" },
                  { value: "user", label: "Quien genera" },
                ]}
              />
            </Row>

            {type === "string" ? (
              <Row label="Longitud" hint="En caracteres. Déjalo vacío para no limitar.">
                <div className="flex items-center gap-2">
                  <NumberBox
                    value={schema.minLength}
                    disabled={locked}
                    placeholder="mín"
                    onChange={(next) => setSchema({ minLength: next })}
                  />
                  <span className="text-small text-muted-foreground">—</span>
                  <NumberBox
                    value={schema.maxLength}
                    disabled={locked}
                    placeholder="máx"
                    onChange={(next) => setSchema({ maxLength: next })}
                  />
                </div>
              </Row>
            ) : null}

            {type === "integer" || type === "number" ? (
              <Row label="Rango" hint="Valores mínimo y máximo aceptados. Vacío = sin límite.">
                <div className="flex items-center gap-2">
                  <NumberBox
                    value={schema.minimum}
                    disabled={locked}
                    placeholder="mín"
                    onChange={(next) => setSchema({ minimum: next })}
                  />
                  <span className="text-small text-muted-foreground">—</span>
                  <NumberBox
                    value={schema.maximum}
                    disabled={locked}
                    placeholder="máx"
                    onChange={(next) => setSchema({ maximum: next })}
                  />
                </div>
              </Row>
            ) : null}
          </div>

          {lengthInvalid ? (
            <p className="text-small text-destructive">La longitud mínima supera a la máxima.</p>
          ) : null}
          {rangeInvalid ? (
            <p className="text-small text-destructive">El valor mínimo supera al máximo.</p>
          ) : null}

          {type === "enum" ? (
            <Row
              label="Valores permitidos"
              hint="El modelo solo podrá responder con uno de estos valores. Haz clic en un valor para editarlo."
              error={
                enumValues(schema).length === 0
                  ? "Un campo de opciones necesita al menos un valor."
                  : null
              }
              description={
                enumMismatch ? (
                  <span className="flex items-center gap-2 text-attention">
                    El tipo admite vacío pero la lista de opciones no lo incluye, así que el
                    pipeline lo tratará como obligatorio.
                    {locked ? null : (
                      <button
                        type="button"
                        onClick={() => setNullable(true)}
                        className="underline underline-offset-2"
                      >
                        Corregir
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
                placeholder="básico, intermedio, avanzado…"
                hint={
                  nullable
                    ? "Al ser opcional, el valor vacío también se acepta."
                    : "Enter o coma para añadir. Retroceso borra el último."
                }
              />
            </Row>
          ) : null}

          {/* Two real controls here, so the chips leave the field and name themselves: a
              label binds to exactly one, and pointing it at the picker while the chips sit
              underneath would be a label that lies about what it names. */}
          {type === "array" ? (
            <div className="space-y-2">
              <Row label="Tipo de cada elemento">
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
                  aria-label="Valores que puede tomar cada elemento"
                  disabled={locked}
                  values={enumValues(schema.items ?? {})}
                  onChange={(values) => setSchema({ items: { type: "string", enum: values } })}
                  placeholder="Valores que puede tomar cada elemento…"
                />
              ) : null}
            </div>
          ) : null}

          {type === "object" ? (
            <p className="rounded-lg border border-dashed border-border p-3 text-small text-muted-foreground">
              Se valida como objeto libre: su contenido no se comprueba. Descríbelo bien abajo, es
              lo único que guía al modelo.
            </p>
          ) : null}

          <Row label="Descripción" hint="Viaja al modelo dentro del esquema: di qué contiene el campo, no cómo escribirlo.">
            <Textarea
              value={spec.description ?? ""}
              readOnly={locked}
              onChange={(event) => onChange({ ...spec, description: event.target.value })}
              placeholder="Qué contiene este campo"
              className="min-h-16"
            />
          </Row>

          <div className="grid gap-3 md:grid-cols-2">
            <Field
              label={
                <span className="inline-flex items-center gap-1.5">
                  <FileSearch className="size-3.5" />
                  Cómo extraerlo
                  <InfoHint label="Guía de extracción">
                    Se usa al construir el banco desde los documentos: dónde está el campo y qué
                  recortar.
                  </InfoHint>
                </span>
              }
            >
              <Textarea
                value={spec.guidance?.extraction ?? ""}
                readOnly={locked}
                onChange={(event) =>
                  onChange({
                    ...spec,
                    guidance: { ...spec.guidance, extraction: event.target.value || undefined },
                  })
                }
                placeholder="Cómo localizar este campo en los documentos"
                className="min-h-24 text-small"
              />
            </Field>
            <Field
              label={
                <span className="inline-flex items-center gap-1.5">
                  <Wand2 className="size-3.5" />
                  Cómo generarlo
                  <span className="rounded bg-muted px-1.5 py-0.5 text-micro font-condensed text-muted-foreground">
                    solo a mano
                  </span>
                </span>
              }
              description="El constructor no lo rellena: lo general va en las reglas de la modalidad. Escríbelo solo cuando este campo concreto necesite un matiz que las reglas no cubren."
            >
              <Textarea
                value={spec.guidance?.generation ?? ""}
                readOnly={locked}
                onChange={(event) =>
                  onChange({
                    ...spec,
                    guidance: { ...spec.guidance, generation: event.target.value || undefined },
                  })
                }
                placeholder="Vacío salvo que este campo necesite un matiz propio"
                className="min-h-24 text-small"
              />
            </Field>
          </div>

          <div className="space-y-2 border-t border-border pt-3">
            <button
              type="button"
              onClick={() => {
                setEditingRaw(false);
                setRawError(null);
                setShowRaw(!showRaw);
              }}
              className="flex items-center gap-1.5 text-small text-muted-foreground transition-colors hover:text-foreground"
            >
              <Braces className="size-3.5" />
              {showRaw ? "Ocultar el JSON del campo" : "Ver el JSON del campo"}
            </button>

            {showRaw ? (
              <div className="animate-fade-in space-y-2">
                {editingRaw ? (
                  <>
                    <Textarea
                      aria-label="JSON del campo"
                      value={rawText}
                      onChange={(event) => setRawText(event.target.value)}
                      className="min-h-48 font-mono text-small"
                      spellCheck={false}
                    />
                    {rawError ? <p className="text-small text-destructive">{rawError}</p> : null}
                    <div className="flex gap-2">
                      <Button size="sm" onClick={applyRaw}>
                        Aplicar campo
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditingRaw(false)}>
                        Cancelar
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
                    <CodeBlock
                      code={JSON.stringify(spec, null, 2)}
                      language="json"
                      maxHeight="16rem"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={locked}
                      title={locked ? LOCKED_HINT : undefined}
                      onClick={() => {
                        setRawText(JSON.stringify(spec, null, 2));
                        setRawError(null);
                        setEditingRaw(true);
                      }}
                    >
                      Editar a mano
                    </Button>
                  </>
                )}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

import { useMutation } from "@tanstack/react-query";
import { CircleCheck, GripVertical, Plus, Save, TriangleAlert, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { StageGate } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Alert, Separator, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import type { ContentProfile, FieldSpec, StageState } from "@/lib/types";
import { useInvalidateChain, useProfile } from "@/state/queries";

const SCALARS = ["string", "integer", "number", "boolean", "object"] as const;

function baseType(schema: Record<string, any>): string {
  if (schema.enum) return "enum";
  const type = schema.type;
  if (Array.isArray(type)) return type.find((t: unknown) => t && t !== "null") ?? "string";
  if (type === "array") return "array";
  return type ?? "string";
}

function isNullable(schema: Record<string, any>): boolean {
  const type = schema.type;
  return Array.isArray(type) && type.some((t: unknown) => t === "null" || t === null);
}

function describeType(schema: Record<string, any>): string {
  const base = baseType(schema);
  const suffix = isNullable(schema) ? " · opcional" : "";
  if (base === "enum") return `enum (${(schema.enum ?? []).length} valores)${suffix}`;
  if (base === "array") return `lista de ${baseType(schema.items ?? { type: "string" })}${suffix}`;
  return base + suffix;
}

function FieldCard({
  name,
  spec,
  isPrimary,
  onChange,
  onRename,
  onRemove,
}: {
  name: string;
  spec: FieldSpec;
  isPrimary: boolean;
  onChange: (next: FieldSpec) => void;
  onRename: (next: string) => void;
  onRemove: () => void;
}) {
  const [rawMode, setRawMode] = useState(false);
  const [rawText, setRawText] = useState(() => JSON.stringify(spec.schema, null, 2));
  const [rawError, setRawError] = useState<string | null>(null);

  const type = baseType(spec.schema);
  const nullable = isNullable(spec.schema);

  const setSchema = (patch: Record<string, any>) =>
    onChange({ ...spec, schema: { ...spec.schema, ...patch } });

  const changeType = (next: string) => {
    const schema: Record<string, any> = {};
    if (next === "enum") {
      schema.type = nullable ? ["string", "null"] : "string";
      schema.enum = spec.schema.enum ?? [];
    } else if (next === "array") {
      schema.type = "array";
      schema.items = spec.schema.items ?? { type: "string" };
    } else {
      schema.type = nullable ? [next, "null"] : next;
    }
    onChange({ ...spec, schema });
  };

  const changeNullable = (next: boolean) => {
    const base = type === "enum" ? "string" : type;
    if (type === "array") {
      setSchema({ type: next ? ["array", "null"] : "array" });
      return;
    }
    setSchema({ type: next ? [base, "null"] : base });
  };

  const applyRaw = () => {
    try {
      const parsed = JSON.parse(rawText);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        setRawError("El esquema debe ser un objeto");
        return;
      }
      setRawError(null);
      onChange({ ...spec, schema: parsed });
      setRawMode(false);
    } catch (error) {
      setRawError((error as Error).message);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <GripVertical className="size-4 shrink-0 text-muted-foreground" />
          <Input
            value={name}
            onChange={(event) => onRename(event.target.value)}
            className="h-8 max-w-56 font-mono text-sm"
          />
          {isPrimary ? <Badge>campo primario</Badge> : null}
          <Badge variant="outline">{describeType(spec.schema)}</Badge>
          <Button
            variant="ghost"
            size="icon-sm"
            className="ml-auto"
            onClick={onRemove}
            disabled={isPrimary}
            title={isPrimary ? "El campo primario no se puede borrar" : "Eliminar campo"}
          >
            <X />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-[10rem_auto_1fr]">
          <div className="space-y-1">
            <Label>Tipo</Label>
            <Select value={type} onChange={(event) => changeType(event.target.value)}>
              {[...SCALARS, "enum", "array"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1">
            <Label>Opcional</Label>
            <div className="flex h-9 items-center">
              <Switch checked={nullable} onCheckedChange={changeNullable} label="permite null" />
            </div>
          </div>
          {type === "string" || type === "enum" ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>minLength</Label>
                <Input
                  type="number"
                  value={spec.schema.minLength ?? ""}
                  onChange={(event) =>
                    setSchema({
                      minLength: event.target.value === "" ? undefined : Number(event.target.value),
                    })
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>maxLength</Label>
                <Input
                  type="number"
                  value={spec.schema.maxLength ?? ""}
                  onChange={(event) =>
                    setSchema({
                      maxLength: event.target.value === "" ? undefined : Number(event.target.value),
                    })
                  }
                />
              </div>
            </div>
          ) : null}
          {type === "integer" || type === "number" ? (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>minimum</Label>
                <Input
                  type="number"
                  value={spec.schema.minimum ?? ""}
                  onChange={(event) =>
                    setSchema({
                      minimum: event.target.value === "" ? undefined : Number(event.target.value),
                    })
                  }
                />
              </div>
              <div className="space-y-1">
                <Label>maximum</Label>
                <Input
                  type="number"
                  value={spec.schema.maximum ?? ""}
                  onChange={(event) =>
                    setSchema({
                      maximum: event.target.value === "" ? undefined : Number(event.target.value),
                    })
                  }
                />
              </div>
            </div>
          ) : null}
        </div>

        {type === "enum" ? (
          <div className="space-y-1">
            <Label>Valores permitidos (uno por línea)</Label>
            <Textarea
              value={(spec.schema.enum ?? []).join("\n")}
              onChange={(event) =>
                setSchema({
                  enum: event.target.value
                    .split("\n")
                    .map((line) => line.trim())
                    .filter(Boolean),
                })
              }
              className="min-h-24 font-mono text-xs"
            />
          </div>
        ) : null}

        <div className="space-y-1">
          <Label>Descripción</Label>
          <Textarea
            value={spec.description ?? ""}
            onChange={(event) => onChange({ ...spec, description: event.target.value })}
            placeholder="Qué contiene este campo"
            className="min-h-16"
          />
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-1">
            <Label>Guía de extracción</Label>
            <Textarea
              value={spec.guidance?.extraction ?? ""}
              onChange={(event) =>
                onChange({
                  ...spec,
                  guidance: { ...spec.guidance, extraction: event.target.value || undefined },
                })
              }
              placeholder="Cómo localizar este campo en los documentos"
              className="min-h-24 text-xs"
            />
          </div>
          <div className="space-y-1">
            <Label>Guía de generación</Label>
            <Textarea
              value={spec.guidance?.generation ?? ""}
              onChange={(event) =>
                onChange({
                  ...spec,
                  guidance: { ...spec.guidance, generation: event.target.value || undefined },
                })
              }
              placeholder="Cómo debe redactarse al generar"
              className="min-h-24 text-xs"
            />
          </div>
        </div>

        <div>
          {rawMode ? (
            <div className="space-y-2">
              <Textarea
                value={rawText}
                onChange={(event) => setRawText(event.target.value)}
                className="min-h-32 font-mono text-xs"
              />
              {rawError ? <p className="text-xs text-destructive">{rawError}</p> : null}
              <div className="flex gap-2">
                <Button size="sm" onClick={applyRaw}>
                  Aplicar esquema
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setRawMode(false)}>
                  Cancelar
                </Button>
              </div>
            </div>
          ) : (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setRawText(JSON.stringify(spec.schema, null, 2));
                setRawMode(true);
              }}
            >
              Editar el esquema como JSON
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function ProfileEditor() {
  const query = useProfile();
  const invalidate = useInvalidateChain();

  const [draft, setDraft] = useState<ContentProfile | null>(null);
  const [tab, setTab] = useState("form");
  const [rawText, setRawText] = useState("");
  const [rawError, setRawError] = useState<string | null>(null);
  const [validation, setValidation] = useState<{ valid: boolean; error: string | null } | null>(null);

  useEffect(() => {
    if (query.data?.profile && draft === null) {
      setDraft(query.data.profile);
      setRawText(JSON.stringify(query.data.profile, null, 2));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data]);

  const dirty = useMemo(
    () => Boolean(draft && query.data?.profile && JSON.stringify(draft) !== JSON.stringify(query.data.profile)),
    [draft, query.data],
  );

  // The real validator lives in the pipeline; asking it means the message here is
  // literally the error the run would raise, not a guess re-implemented in the browser.
  useEffect(() => {
    if (!draft) return;
    const handle = window.setTimeout(() => {
      api
        .validateProfile(draft)
        .then(setValidation)
        .catch(() => setValidation(null));
    }, 400);
    return () => window.clearTimeout(handle);
  }, [draft]);

  const save = useMutation({
    mutationFn: (profile: ContentProfile) => api.saveProfile(profile),
    onSuccess: () => {
      invalidate();
      query.refetch();
    },
  });

  if (query.isLoading) return <Skeleton className="h-96" />;

  if (!query.data?.exists || !draft) {
    return (
      <Alert tone="info" title="Todavía no hay perfil de contenido">
        <p>Constrúyelo desde el panel para poder revisarlo.</p>
      </Alert>
    );
  }

  const update = (patch: Partial<ContentProfile>) => setDraft({ ...draft, ...patch });

  const renameField = (from: string, to: string) => {
    if (!to || to === from) return;
    const fields: Record<string, FieldSpec> = {};
    for (const [key, value] of Object.entries(draft.fields)) fields[key === from ? to : key] = value;
    update({ fields, primary_field: draft.primary_field === from ? to : draft.primary_field });
  };

  const applyRaw = () => {
    try {
      const parsed = JSON.parse(rawText);
      setRawError(null);
      setDraft(parsed);
    } catch (error) {
      setRawError((error as Error).message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          items={[
            { value: "form", label: "Formulario" },
            { value: "raw", label: "JSON crudo" },
          ]}
          value={tab}
          onChange={(next) => {
            if (next === "raw") setRawText(JSON.stringify(draft, null, 2));
            setTab(next);
          }}
        />

        {validation ? (
          validation.valid ? (
            <span className="flex items-center gap-1.5 text-xs text-[var(--success)]">
              <CircleCheck className="size-3.5" />
              El perfil carga correctamente
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-destructive">
              <TriangleAlert className="size-3.5" />
              {validation.error}
            </span>
          )
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          {dirty ? <Badge variant="warning">sin guardar</Badge> : null}
          <Button
            onClick={() => save.mutate(draft)}
            disabled={!dirty || save.isPending || validation?.valid === false}
          >
            {save.isPending ? <Spinner /> : <Save />}
            Guardar
          </Button>
        </div>
      </div>

      {save.isError ? (
        <Alert tone="danger" title="No se pudo guardar">
          <p>{(save.error as Error).message}</p>
        </Alert>
      ) : null}

      {query.data.is_autogenerated ? (
        <Alert tone="warning" title="Estás revisando el borrador autogenerado">
          <p>
            Al guardar se escribirá como <code className="font-mono">content_profile.json</code>, que
            es el que usará el pipeline a partir de entonces.
          </p>
        </Alert>
      ) : null}

      {tab === "raw" ? (
        <div className="space-y-2">
          <Textarea
            value={rawText}
            onChange={(event) => setRawText(event.target.value)}
            className="min-h-[32rem] font-mono text-xs"
            spellCheck={false}
          />
          {rawError ? <p className="text-xs text-destructive">{rawError}</p> : null}
          <Button size="sm" onClick={applyRaw}>
            Aplicar al formulario
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Contexto del contenido</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {Object.entries(draft.content_context).map(([key, value]) => (
                <div key={key} className="flex gap-2">
                  <Input
                    value={key}
                    className="max-w-56 font-mono text-xs"
                    onChange={(event) => {
                      const context: Record<string, string> = {};
                      for (const [k, v] of Object.entries(draft.content_context))
                        context[k === key ? event.target.value : k] = v;
                      update({ content_context: context });
                    }}
                  />
                  <Input
                    value={value}
                    onChange={(event) =>
                      update({
                        content_context: { ...draft.content_context, [key]: event.target.value },
                      })
                    }
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      const context = { ...draft.content_context };
                      delete context[key];
                      update({ content_context: context });
                    }}
                  >
                    <X />
                  </Button>
                </div>
              ))}
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  update({ content_context: { ...draft.content_context, nueva_clave: "" } })
                }
              >
                <Plus />
                Añadir clave
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Reglas generales de generación</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {draft.general_generation_rules.map((rule, index) => (
                <div key={index} className="flex gap-2">
                  <span className="mt-2 w-5 shrink-0 text-right text-xs text-muted-foreground">
                    {index + 1}
                  </span>
                  <Textarea
                    value={rule}
                    className="min-h-16 text-sm"
                    onChange={(event) => {
                      const rules = [...draft.general_generation_rules];
                      rules[index] = event.target.value;
                      update({ general_generation_rules: rules });
                    }}
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() =>
                      update({
                        general_generation_rules: draft.general_generation_rules.filter(
                          (_, i) => i !== index,
                        ),
                      })
                    }
                  >
                    <X />
                  </Button>
                </div>
              ))}
              <Button
                size="sm"
                variant="ghost"
                onClick={() =>
                  update({ general_generation_rules: [...draft.general_generation_rules, ""] })
                }
              >
                <Plus />
                Añadir regla
              </Button>
            </CardContent>
          </Card>

          <div className="flex items-center gap-3">
            <div className="flex shrink-0 items-center gap-1.5">
              <Label>Campo primario</Label>
              <InfoHint label="Qué es el campo primario">
                El texto que se etiqueta y se embebe: define de qué trata cada ítem y es contra lo
                que se emparejan los conceptos.
              </InfoHint>
            </div>
            <Select
              value={draft.primary_field}
              onChange={(event) => update({ primary_field: event.target.value })}
              className="max-w-64"
            >
              {Object.keys(draft.fields).map((field) => (
                <option key={field} value={field}>
                  {field}
                </option>
              ))}
            </Select>
          </div>

          <Separator />

          <div className="space-y-3">
            {Object.entries(draft.fields).map(([name, spec]) => (
              <FieldCard
                key={name}
                name={name}
                spec={spec}
                isPrimary={name === draft.primary_field}
                onChange={(next) => update({ fields: { ...draft.fields, [name]: next } })}
                onRename={(next) => renameField(name, next)}
                onRemove={() => {
                  const fields = { ...draft.fields };
                  delete fields[name];
                  update({ fields });
                }}
              />
            ))}
            <Button
              variant="outline"
              onClick={() =>
                update({
                  fields: {
                    ...draft.fields,
                    nuevo_campo: { schema: { type: "string" }, description: "" },
                  },
                })
              }
            >
              <Plus />
              Añadir campo
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ProfileScreen({ stage }: { stage: StageState | undefined }) {
  return (
    <StageGate
      stage={stage}
      title="1 · Perfil de contenido"
      description={
        <>
          Define qué es un ítem: sus campos, sus tipos y las guías que el modelo sigue al
          extraerlos y al generarlos. Cambiarlo después de extraer el banco lo invalida, porque
          los ítems se extrajeron contra el esquema anterior.
        </>
      }
    >
      <ProfileEditor />
    </StageGate>
  );
}

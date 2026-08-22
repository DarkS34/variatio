import { useMutation } from "@tanstack/react-query";
import {
  ChevronsDownUp,
  ChevronsUpDown,
  CircleCheck,
  Plus,
  Save,
  Star,
  TriangleAlert,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { StageGate } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import type { ExemplarsProfile, FieldSpec, ItemTypeSpec, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { embedFields } from "@/lib/profile";
import { useInvalidateChain, useProfile } from "@/state/queries";

import { FieldEditor, baseType, fieldNameError, nameError } from "./FieldEditor";

function AddInline({
  placeholder,
  cta,
  onAdd,
  validate,
  mono = true,
}: {
  placeholder: string;
  cta: string;
  onAdd: (value: string) => void;
  validate?: (value: string) => string | null;
  mono?: boolean;
}) {
  const [text, setText] = useState("");
  const error = text.trim() ? (validate?.(text.trim()) ?? null) : null;

  const submit = () => {
    const value = text.trim();
    if (!value || error) return;
    onAdd(value);
    setText("");
  };

  return (
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1">
        <Input
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={placeholder}
          className={mono ? "font-mono text-sm" : "text-sm"}
        />
        {error ? <p className="mt-1 text-xs text-destructive">{error}</p> : null}
      </div>
      <Button variant="outline" onClick={submit} disabled={!text.trim() || Boolean(error)}>
        <Plus />
        {cta}
      </Button>
    </div>
  );
}

function ContextRow({
  name,
  value,
  taken,
  onRename,
  onChange,
  onRemove,
}: {
  name: string;
  value: string;
  taken: string[];
  onRename: (next: string) => void;
  onChange: (next: string) => void;
  onRemove: () => void;
}) {
  const [draft, setDraft] = useState(name);
  useEffect(() => setDraft(name), [name]);

  const trimmed = draft.trim();
  const error =
    trimmed === name
      ? null
      : !trimmed
        ? "La clave no puede estar vacía"
        : taken.includes(trimmed)
          ? "Esa clave ya existe"
          : null;

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => {
            if (trimmed !== name && !error) onRename(trimmed);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") event.currentTarget.blur();
            if (event.key === "Escape") setDraft(name);
          }}
          className={cn("h-8 w-48 shrink-0 font-mono text-xs", error && "border-destructive")}
        />
        <Input
          value={value}
          placeholder="valor"
          className="h-8 text-sm"
          onChange={(event) => onChange(event.target.value)}
        />
        <Button
          variant="ghost"
          size="icon-sm"
          title={`Quitar ${name}`}
          className="shrink-0 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
          onClick={onRemove}
        >
          <X />
        </Button>
      </div>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

function TypeStrip({
  keys,
  active,
  labels,
  counts,
  onSelect,
  onAdd,
  onRemove,
}: {
  keys: string[];
  active: string;
  labels: Record<string, string>;
  counts: Record<string, number>;
  onSelect: (key: string) => void;
  onAdd: (key: string) => void;
  onRemove: (key: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold tracking-tight">Modalidades de ítem</h2>
        <Badge variant="outline">{keys.length}</Badge>
        <InfoHint label="Qué son las modalidades">
          Cada modalidad es una forma distinta de plantear la tarea — una pregunta con
          alternativas, un encargo de escribir código, un fallo que corregir — y tiene su propio
          esquema de campos, su campo primario y sus reglas. Al generar se elige una, y el
          few-shot solo usa ejemplares de esa misma modalidad. La primera es la de por defecto.
        </InfoHint>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {keys.map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => onSelect(key)}
            className={cn(
              "group flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-left transition-colors",
              key === active ? "border-primary bg-primary/5" : "border-border hover:bg-accent/40",
            )}
          >
            <span className="text-sm font-medium">{labels[key] || key}</span>
            <Badge variant="outline">{counts[key]}</Badge>
            {keys.length > 1 ? (
              <span
                role="button"
                tabIndex={-1}
                title={`Quitar la modalidad ${key}`}
                className="rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                onClick={(event) => {
                  event.stopPropagation();
                  if (window.confirm(`¿Quitar la modalidad «${key}» y todos sus campos?`))
                    onRemove(key);
                }}
              >
                <X className="size-3.5" />
              </span>
            ) : null}
          </button>
        ))}
      </div>

      <AddInline
        placeholder="nueva_modalidad"
        cta="Añadir modalidad"
        onAdd={onAdd}
        validate={(key) => nameError(key, keys)}
      />
    </div>
  );
}

export function ProfileEditor() {
  const query = useProfile();
  const invalidate = useInvalidateChain();

  const [draft, setDraft] = useState<ExemplarsProfile | null>(null);
  const [activeType, setActiveType] = useState<string | null>(null);
  const [tab, setTab] = useState("form");
  const [open, setOpen] = useState<string[]>([]);
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
    mutationFn: (profile: ExemplarsProfile) => api.saveProfile(profile),
    onSuccess: () => {
      invalidate();
      query.refetch();
    },
  });

  if (query.isLoading) return <Skeleton className="h-96" />;

  if (!query.data?.exists || !draft) return null;

  const update = (patch: Partial<ExemplarsProfile>) => setDraft({ ...draft, ...patch });

  const typeKeys = Object.keys(draft.item_types);
  const activeKey = activeType && typeKeys.includes(activeType) ? activeType : typeKeys[0];
  const spec = draft.item_types[activeKey];

  const updateType = (patch: Partial<ItemTypeSpec>) =>
    update({ item_types: { ...draft.item_types, [activeKey]: { ...spec, ...patch } } });

  const names = Object.keys(spec.fields);
  const rules = spec.general_generation_rules ?? [];
  const indexed = embedFields(spec);

  // Kept in declared order rather than click order, and the primary is never removable:
  // it is what guarantees the text carries the item at all.
  const toggleIndexed = (name: string) => {
    if (name === spec.primary_field) return;
    const next = indexed.includes(name)
      ? indexed.filter((entry) => entry !== name)
      : [...indexed, name];
    const ordered = names.filter((field) => next.includes(field));
    updateType({ embed_fields: ordered });
  };

  const addType = (key: string) => {
    update({
      item_types: {
        ...draft.item_types,
        [key]: {
          label: key,
          description: "",
          primary_field: "enunciado",
          general_generation_rules: [],
          fields: {
            enunciado: {
              schema: { type: "string" },
              description: "",
              guidance: { extraction: "", generation: "" },
            },
          },
        },
      },
    });
    setActiveType(key);
    setOpen([]);
  };

  const removeType = (key: string) => {
    const item_types = { ...draft.item_types };
    delete item_types[key];
    update({ item_types });
    if (key === activeKey) setActiveType(Object.keys(item_types)[0] ?? null);
  };

  const renameField = (from: string, to: string) => {
    if (!to || to === from) return;
    const fields: Record<string, FieldSpec> = {};
    for (const [key, value] of Object.entries(spec.fields)) fields[key === from ? to : key] = value;
    updateType({
      fields,
      primary_field: spec.primary_field === from ? to : spec.primary_field,
      embed_fields: indexed.map((entry) => (entry === from ? to : entry)),
    });
    setOpen((current) => current.map((entry) => (entry === from ? to : entry)));
  };

  const moveField = (name: string, direction: -1 | 1) => {
    const entries = Object.entries(spec.fields);
    const index = entries.findIndex(([key]) => key === name);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= entries.length) return;
    const next = [...entries];
    [next[index], next[target]] = [next[target], next[index]];
    updateType({ fields: Object.fromEntries(next) });
  };

  const addField = (name: string) => {
    updateType({ fields: { ...spec.fields, [name]: { schema: { type: "string" }, description: "" } } });
    setOpen((current) => [...current, name]);
  };

  const removeField = (name: string) => {
    const fields = { ...spec.fields };
    delete fields[name];
    updateType({ fields, embed_fields: indexed.filter((entry) => entry !== name) });
    setOpen((current) => current.filter((entry) => entry !== name));
  };

  const renameContextKey = (from: string, to: string) => {
    const context: Record<string, string> = {};
    for (const [key, value] of Object.entries(draft.content_context))
      context[key === from ? to : key] = value;
    update({ content_context: context });
  };

  const applyRaw = () => {
    try {
      const parsed = JSON.parse(rawText);
      setRawError(null);
      setDraft(parsed);
      setActiveType(null);
    } catch (error) {
      setRawError((error as Error).message);
    }
  };

  const allOpen = open.length === names.length && names.length > 0;

  return (
    <div className="space-y-4">
      <div className="sticky top-14 z-20 -mx-4 flex flex-wrap items-center gap-3 border-b border-border bg-background/90 px-4 py-3 backdrop-blur">
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
            <span className="flex min-w-0 items-center gap-1.5 text-xs text-destructive">
              <TriangleAlert className="size-3.5 shrink-0" />
              <span className="truncate" title={validation.error ?? undefined}>
                {validation.error}
              </span>
            </span>
          )
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          {dirty ? <Badge variant="attention">sin guardar</Badge> : null}
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
              <div className="flex items-center gap-2">
                <CardTitle>Contexto del contenido</CardTitle>
                <InfoHint label="Qué es el contexto">
                  Pares clave/valor que acompañan a cada prompt: asignatura, idioma, lenguaje de
                  programación… Lo que no cambia entre ítems ni entre modalidades.
                </InfoHint>
                <Badge variant="outline" className="ml-auto">
                  {Object.keys(draft.content_context).length}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="grid gap-2 lg:grid-cols-2">
              {Object.entries(draft.content_context).map(([key, value]) => (
                <ContextRow
                  key={key}
                  name={key}
                  value={value}
                  taken={Object.keys(draft.content_context)}
                  onRename={(next) => renameContextKey(key, next)}
                  onChange={(next) =>
                    update({ content_context: { ...draft.content_context, [key]: next } })
                  }
                  onRemove={() => {
                    const context = { ...draft.content_context };
                    delete context[key];
                    update({ content_context: context });
                  }}
                />
              ))}

              {Object.keys(draft.content_context).length === 0 ? (
                <p className="text-xs text-destructive">
                  El contexto no puede quedar vacío: añade al menos una clave.
                </p>
              ) : null}

              <AddInline
                placeholder="nueva_clave"
                cta="Añadir"
                onAdd={(key) => update({ content_context: { ...draft.content_context, [key]: "" } })}
                validate={(key) => (key in draft.content_context ? "Esa clave ya existe" : null)}
              />
            </CardContent>
          </Card>

          <TypeStrip
            keys={typeKeys}
            active={activeKey}
            labels={Object.fromEntries(
              typeKeys.map((key) => [key, draft.item_types[key].label || key]),
            )}
            counts={Object.fromEntries(
              typeKeys.map((key) => [key, Object.keys(draft.item_types[key].fields).length]),
            )}
            onSelect={(key) => {
              setActiveType(key);
              setOpen([]);
            }}
            onAdd={addType}
            onRemove={removeType}
          />

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <CardTitle>Identidad de la modalidad</CardTitle>
                  <InfoHint label="Para qué sirve">
                    La descripción la leen dos prompts: el extractor, para decidir a qué modalidad
                    pertenece cada ejercicio del documento, y el generador, para saber qué forma
                    debe tener el ítem. Escríbela discriminante: qué la distingue de las demás.
                  </InfoHint>
                  <code className="ml-auto font-mono text-xs text-muted-foreground">
                    {activeKey}
                  </code>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="space-y-1">
                  <Label>Nombre legible</Label>
                  <Input
                    value={spec.label ?? ""}
                    placeholder="Pregunta tipo test"
                    className="text-sm"
                    onChange={(event) => updateType({ label: event.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Descripción</Label>
                  <Textarea
                    value={spec.description ?? ""}
                    placeholder="Qué es esta modalidad y cómo se reconoce en el material"
                    className="min-h-20 text-sm"
                    onChange={(event) => updateType({ description: event.target.value })}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <CardTitle>Reglas de generación</CardTitle>
                  <InfoHint label="Qué son las reglas">
                    Se añaden a los prompts de generación DE ESTA MODALIDAD, sea cual sea el campo.
                    Una regla que solo tiene sentido aquí (exigir docstring, pedir cuatro
                    alternativas) va aquí, no en las demás. Para lo específico de un campo usa su
                    guía de generación.
                  </InfoHint>
                  <Badge variant="outline" className="ml-auto">
                    {rules.length}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {rules.map((rule, index) => (
                  <div key={index} className="flex items-start gap-2">
                    <span className="mt-2 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] tabular-nums text-muted-foreground">
                      {index + 1}
                    </span>
                    <Textarea
                      value={rule}
                      className="min-h-16 text-sm"
                      placeholder="Una regla por bloque"
                      onChange={(event) => {
                        const next = [...rules];
                        next[index] = event.target.value;
                        updateType({ general_generation_rules: next });
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title="Quitar regla"
                      className="mt-1 shrink-0 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      onClick={() =>
                        updateType({
                          general_generation_rules: rules.filter((_, i) => i !== index),
                        })
                      }
                    >
                      <X />
                    </Button>
                  </div>
                ))}

                {rules.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Sin reglas: el modelo solo seguirá las guías de cada campo.
                  </p>
                ) : null}

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => updateType({ general_generation_rules: [...rules, ""] })}
                >
                  <Plus />
                  Añadir regla
                </Button>
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <h2 className="text-sm font-semibold tracking-tight">
              Campos de «{spec.label || activeKey}»
            </h2>
            <Badge variant="outline">{names.length}</Badge>
            <InfoHint label="Qué son los campos">
              Definen qué es un ítem de esta modalidad: el esquema contra el que se validan tanto
              los extraídos del banco como los generados. El campo marcado con{" "}
              <Star className="inline size-3" /> es el primario: el texto que se etiqueta y se
              embebe.
            </InfoHint>
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto"
              onClick={() => setOpen(allOpen ? [] : names)}
            >
              {allOpen ? <ChevronsDownUp /> : <ChevronsUpDown />}
              {allOpen ? "Contraer todo" : "Expandir todo"}
            </Button>
          </div>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex flex-wrap items-center gap-2 text-sm">
                Campos que se indexan
                <InfoHint label="Qué se indexa">
                  Los campos que se leen JUNTOS para decidir qué concepto del currículo practica
                  el ítem. Añade aquí lo que RECIBE con el enunciado quien lo resuelve —el código a
                  analizar, el material de partida—: cuando el enunciado es una fórmula fija
                  («¿qué imprime este código?»), el concepto está ahí y no en el enunciado. No
                  marques la solución: medido sobre este banco, incluirla empeora el acierto.
                </InfoHint>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {names.map((name) => {
                const on = indexed.includes(name);
                const locked = name === spec.primary_field;
                return (
                  <button
                    key={name}
                    type="button"
                    disabled={locked}
                    onClick={() => toggleIndexed(name)}
                    title={locked ? "El campo primario siempre se indexa" : undefined}
                    className={cn(
                      "rounded-md border px-2 py-1 font-mono text-xs transition-colors",
                      on
                        ? "border-primary/40 bg-primary/10 text-foreground"
                        : "border-border text-muted-foreground hover:bg-muted",
                      locked && "cursor-default opacity-90",
                    )}
                  >
                    {locked ? <Star className="mr-1 inline size-3" /> : null}
                    {name}
                  </button>
                );
              })}
            </CardContent>
          </Card>

          {baseType(spec.fields[spec.primary_field]?.schema ?? {}) !== "string" ? (
            <Alert tone="attention" title="El campo primario no es de texto">
              <p>
                <code className="font-mono">{spec.primary_field}</code> es el texto que se embebe y
                se etiqueta contra el grafo; con otro tipo el emparejamiento con conceptos pierde
                sentido.
              </p>
            </Alert>
          ) : null}

          <div className="space-y-2">
            {Object.entries(spec.fields).map(([name, field], index) => (
              <FieldEditor
                key={name}
                name={name}
                spec={field}
                isPrimary={name === spec.primary_field}
                open={open.includes(name)}
                first={index === 0}
                last={index === names.length - 1}
                taken={names}
                onToggleOpen={() =>
                  setOpen((current) =>
                    current.includes(name)
                      ? current.filter((entry) => entry !== name)
                      : [...current, name],
                  )
                }
                onChange={(next) => updateType({ fields: { ...spec.fields, [name]: next } })}
                onRename={(next) => renameField(name, next)}
                onRemove={() => removeField(name)}
                onMakePrimary={() =>
                  updateType({
                    primary_field: name,
                    embed_fields: names.filter(
                      (field) => field === name || indexed.includes(field),
                    ),
                  })
                }
                onMove={(direction) => moveField(name, direction)}
              />
            ))}
          </div>

          <AddInline
            placeholder="nombre_del_campo"
            cta="Añadir campo"
            onAdd={addField}
            validate={(name) => fieldNameError(name, names)}
          />
        </div>
      )}
    </div>
  );
}

export function ProfileScreen({ stage }: { stage: StageState | undefined }) {
  return (
    <StageGate
      stage={stage}
      title="2 · Perfil de ejemplares"
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

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
import { Input, Textarea } from "@/components/ui/input";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import type { ContentProfile, FieldSpec, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useInvalidateChain, useProfile } from "@/state/queries";

import { FieldEditor, baseType, fieldNameError } from "./FieldEditor";

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

export function ProfileEditor() {
  const query = useProfile();
  const invalidate = useInvalidateChain();

  const [draft, setDraft] = useState<ContentProfile | null>(null);
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
        <p>
          Púlsalo en «Construir», aquí arriba, para inferirlo de los ejemplares en bruto. El
          progreso aparece en esta misma pantalla.
        </p>
      </Alert>
    );
  }

  const update = (patch: Partial<ContentProfile>) => setDraft({ ...draft, ...patch });
  const names = Object.keys(draft.fields);

  const renameField = (from: string, to: string) => {
    if (!to || to === from) return;
    const fields: Record<string, FieldSpec> = {};
    for (const [key, value] of Object.entries(draft.fields)) fields[key === from ? to : key] = value;
    update({ fields, primary_field: draft.primary_field === from ? to : draft.primary_field });
    setOpen((current) => current.map((entry) => (entry === from ? to : entry)));
  };

  const moveField = (name: string, direction: -1 | 1) => {
    const entries = Object.entries(draft.fields);
    const index = entries.findIndex(([key]) => key === name);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= entries.length) return;
    const next = [...entries];
    [next[index], next[target]] = [next[target], next[index]];
    update({ fields: Object.fromEntries(next) });
  };

  const addField = (name: string) => {
    update({ fields: { ...draft.fields, [name]: { schema: { type: "string" }, description: "" } } });
    setOpen((current) => [...current, name]);
  };

  const removeField = (name: string) => {
    const fields = { ...draft.fields };
    delete fields[name];
    update({ fields });
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
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <CardTitle>Contexto del contenido</CardTitle>
                  <InfoHint label="Qué es el contexto">
                    Pares clave/valor que acompañan a cada prompt: asignatura, idioma, lenguaje de
                    programación… Lo que no cambia entre ítems.
                  </InfoHint>
                  <Badge variant="outline" className="ml-auto">
                    {Object.keys(draft.content_context).length}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
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
                  validate={(key) =>
                    key in draft.content_context ? "Esa clave ya existe" : null
                  }
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <CardTitle>Reglas generales de generación</CardTitle>
                  <InfoHint label="Qué son las reglas">
                    Se añaden a todos los prompts de generación, sea cual sea el campo. Para lo
                    específico de un campo usa su guía de generación.
                  </InfoHint>
                  <Badge variant="outline" className="ml-auto">
                    {draft.general_generation_rules.length}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {draft.general_generation_rules.map((rule, index) => (
                  <div key={index} className="flex items-start gap-2">
                    <span className="mt-2 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] tabular-nums text-muted-foreground">
                      {index + 1}
                    </span>
                    <Textarea
                      value={rule}
                      className="min-h-16 text-sm"
                      placeholder="Una regla por bloque"
                      onChange={(event) => {
                        const rules = [...draft.general_generation_rules];
                        rules[index] = event.target.value;
                        update({ general_generation_rules: rules });
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      title="Quitar regla"
                      className="mt-1 shrink-0 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
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

                {draft.general_generation_rules.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Sin reglas: el modelo solo seguirá las guías de cada campo.
                  </p>
                ) : null}

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
          </div>

          <div className="flex flex-wrap items-center gap-2 pt-2">
            <h2 className="text-sm font-semibold tracking-tight">Campos del ítem</h2>
            <Badge variant="outline">{names.length}</Badge>
            <InfoHint label="Qué son los campos">
              Definen qué es un ítem: el esquema contra el que se validan tanto los extraídos del
              banco como los generados. El campo marcado con <Star className="inline size-3" /> es el
              primario: el texto que se etiqueta y se embebe.
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

          {baseType(draft.fields[draft.primary_field]?.schema ?? {}) !== "string" ? (
            <Alert tone="warning" title="El campo primario no es de texto">
              <p>
                <code className="font-mono">{draft.primary_field}</code> es el texto que se embebe y
                se etiqueta contra el grafo; con otro tipo el emparejamiento con conceptos pierde
                sentido.
              </p>
            </Alert>
          ) : null}

          <div className="space-y-2">
            {Object.entries(draft.fields).map(([name, spec], index) => (
              <FieldEditor
                key={name}
                name={name}
                spec={spec}
                isPrimary={name === draft.primary_field}
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
                onChange={(next) => update({ fields: { ...draft.fields, [name]: next } })}
                onRename={(next) => renameField(name, next)}
                onRemove={() => removeField(name)}
                onMakePrimary={() => update({ primary_field: name })}
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

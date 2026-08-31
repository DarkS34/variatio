import { useMutation } from "@tanstack/react-query";
import {
  ChevronsDownUp,
  ChevronsUpDown,
  Plus,
  Save,
  Star,
  TriangleAlert,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { LOCKED_HINT, StageGate, useStageLocked } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Textarea } from "@/components/ui/input";
import { Alert, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import type { ExemplarsProfile, FieldSpec, ItemTypeSpec, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { embedFields } from "@/lib/profile";
import { useInvalidateChain, useProfile } from "@/state/queries";

import { FieldEditor, baseType, fieldNameError, nameError } from "./FieldEditor";
import { useConfirm } from "@/components/ui/confirm";
import { useT } from "@/lib/i18n";

function AddInline({
  placeholder,
  cta,
  onAdd,
  validate,
  mono = true,
  disabled = false,
}: {
  placeholder: string;
  cta: string;
  onAdd: (value: string) => void;
  validate?: (value: string) => string | null;
  mono?: boolean;
  disabled?: boolean;
}) {
  const { t } = useT();
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
          aria-label={placeholder}
          disabled={disabled}
          title={disabled ? t(LOCKED_HINT) : undefined}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={placeholder}
          className={mono ? "font-mono" : undefined}
        />
        {error ? <p className="mt-1 text-small text-destructive">{error}</p> : null}
      </div>
      <Button
        variant="outline"
        onClick={submit}
        disabled={disabled || !text.trim() || Boolean(error)}
        title={disabled ? t(LOCKED_HINT) : undefined}
      >
        <Plus />
        {cta}
      </Button>
    </div>
  );
}

function TypeStrip({
  keys,
  active,
  labels,
  onSelect,
  onAdd,
  onRemove,
  disabled = false,
}: {
  keys: string[];
  active: string;
  labels: Record<string, string>;
  onSelect: (key: string) => void;
  onAdd: (key: string) => void;
  onRemove: (key: string) => void;
  disabled?: boolean;
}) {
  const tr = useT();
  const confirm = useConfirm();
  const { t } = tr;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-body font-semibold tracking-tight">{t("modality.title")}</h2>
        <InfoHint label={t("modality.whatAre")}>{t("modality.whatAre.body")}</InfoHint>
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
            <span className="text-body font-medium">{labels[key] || key}</span>
            {keys.length > 1 && !disabled ? (
              <span
                role="button"
                tabIndex={-1}
                title={t("modality.remove", { key })}
                className="rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                onClick={async (event) => {
                  event.stopPropagation();
                  if (await confirm({ title: t("modality.removeConfirm", { key }), tone: "danger" }))
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
        placeholder={t("modality.newPlaceholder")}
        cta={t("modality.add")}
        onAdd={onAdd}
        validate={(key) => nameError(key, keys, tr)}
        disabled={disabled}
      />
    </div>
  );
}

export function ProfileEditor() {
  const tr = useT();
  const { t } = tr;
  const query = useProfile();
  const invalidate = useInvalidateChain();
  const stageLocked = useStageLocked();

  const [draft, setDraft] = useState<ExemplarsProfile | null>(null);
  const [activeType, setActiveType] = useState<string | null>(null);
  const [open, setOpen] = useState<string[]>([]);
  const [validation, setValidation] = useState<{ valid: boolean; error: string | null } | null>(null);

  useEffect(() => {
    if (query.data?.profile && draft === null) {
      setDraft(query.data.profile);
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

  // «No hay perfil todavía» and «no se pudo leer» look the same from here and are not the
  // same thing: the first is the state a new workspace starts in and its screen is the build
  // button above; the second used to render nothing at all.
  if (query.isError)
    return <LoadError title={t("profile.unreadable")} error={query.error} onRetry={query.refetch} />;

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

  const allOpen = open.length === names.length && names.length > 0;

  return (
    <div className="space-y-4">
      <div className="sticky top-14 z-20 -mx-4 flex flex-wrap items-center gap-3 border-b border-border bg-background/90 px-4 py-3 backdrop-blur">
        {/* NO RAW-JSON TAB, and therefore no «Formulario» tab either (2026-08-31, explicit
            user request): with one view left there is nothing to switch between. What it
            offered — pasting a whole profile in and applying it — is the one edit that can
            put a shape on screen the form cannot express, and the validator's own sentence
            is what this bar carries instead. */}
        {/* SÓLO SE HABLA CUANDO ALGO VA MAL (2026-09-01, explicit user request). El
            «carga correctamente» era una confirmación permanente de que nada pasa, en la
            barra que sólo debería llevar el guardado; lo que sí tiene que estar es la
            frase del validador cuando el perfil NO carga, porque es la razón por la que
            el botón de guardar se niega. */}
        {validation && !validation.valid ? (
          <span className="flex min-w-0 items-center gap-1.5 text-small text-destructive">
            <TriangleAlert className="size-3.5 shrink-0" />
            <span className="truncate" title={validation.error ?? undefined}>
              {validation.error}
            </span>
          </span>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          {dirty ? <Badge variant="attention">{t("profileEditor.unsaved")}</Badge> : null}
          <Button
            onClick={() => save.mutate(draft)}
            disabled={stageLocked || !dirty || save.isPending || validation?.valid === false}
            title={stageLocked ? t(LOCKED_HINT) : undefined}
          >
            {save.isPending ? <Spinner /> : <Save />}
            {t("common.save")}
          </Button>
        </div>
      </div>

      {save.isError ? (
        <Alert tone="danger" title={t("profileEditor.saveFailed")}>
          <p>{(save.error as Error).message}</p>
        </Alert>
      ) : null}

      <div className="space-y-4">
        <TypeStrip
          keys={typeKeys}
          active={activeKey}
          labels={Object.fromEntries(
            typeKeys.map((key) => [key, draft.item_types[key].label || key]),
          )}
          onSelect={(key) => {
            setActiveType(key);
            setOpen([]);
          }}
          onAdd={addType}
          onRemove={removeType}
          disabled={stageLocked}
        />

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle>{t("modality.identity")}</CardTitle>
                <InfoHint label={t("modality.identity.hintLabel")}>
                  {t("modality.identity.hint")}
                </InfoHint>
                <code className="ml-auto font-mono text-small text-muted-foreground">
                  {activeKey}
                </code>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <Field label={t("modality.readableName")}>
                <Input
                  value={spec.label ?? ""}
                  placeholder={t("modality.readableName.placeholder")}
                  readOnly={stageLocked}
                  onChange={(event) => updateType({ label: event.target.value })}
                />
              </Field>
              <Field label={t("modality.description")}>
                <Textarea
                  autoGrow
                  value={spec.description ?? ""}
                  placeholder={t("modality.description.placeholder")}
                  className="min-h-20"
                  readOnly={stageLocked}
                  onChange={(event) => updateType({ description: event.target.value })}
                />
              </Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle>{t("modality.rules")}</CardTitle>
              {/* Visible, not behind an (i): this is the one thing on the screen that
                  decides how a generated item reads, and it is the only instrument the
                  profile carries for it — the per-field generation guidance is a manual
                  exception now, not the other half of a pair. */}
              <p className="text-small text-muted-foreground">{t("modality.rules.body")}</p>
            </CardHeader>
            <CardContent className="space-y-2">
              {rules.map((rule, index) => (
                <div key={index} className="flex items-start gap-2">
                  <span className="mt-2 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-micro nums text-muted-foreground">
                    {index + 1}
                  </span>
                  <Textarea
                    autoGrow
                    aria-label={t("modality.rule.n", { n: index + 1 })}
                    value={rule}
                    className="min-h-16"
                    readOnly={stageLocked}
                    placeholder={t("modality.rule.placeholder")}
                    onChange={(event) => {
                      const next = [...rules];
                      next[index] = event.target.value;
                      updateType({ general_generation_rules: next });
                    }}
                  />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    disabled={stageLocked}
                    title={stageLocked ? t(LOCKED_HINT) : t("modality.rule.remove")}
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
                <p className="text-small text-attention">{t("modality.rules.none")}</p>
              ) : null}

              <Button
                size="sm"
                variant="ghost"
                disabled={stageLocked}
                title={stageLocked ? t(LOCKED_HINT) : undefined}
                onClick={() => updateType({ general_generation_rules: [...rules, ""] })}
              >
                <Plus />
                {t("modality.rule.add")}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-2">
          <h2 className="text-body font-semibold tracking-tight">
            {t("modality.fieldsOf", { name: spec.label || activeKey })}
          </h2>
          <InfoHint label={t("modality.fields.hintLabel")}>
            {t("modality.fields.hintA")}{" "}
            <Star className="inline size-3" /> {t("modality.fields.hintB")}
          </InfoHint>
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto"
            onClick={() => setOpen(allOpen ? [] : names)}
          >
            {allOpen ? <ChevronsDownUp /> : <ChevronsUpDown />}
            {allOpen ? t("modality.collapseAll") : t("modality.expandAll")}
          </Button>
        </div>

        {/* LA TARJETA «CAMPOS QUE SE INDEXAN» YA NO ESTÁ (2026-09-01, explicit user
            request). Qué campos entran en el índice es una decisión sobre la recuperación,
            no sobre la asignatura, y quien prepara una instancia no tiene con qué
            decidirla: se queda lo que el perfil traiga, que es lo que el constructor
            dedujo. `embed_fields` sigue en el artefacto y `toggleIndexed` sigue existiendo
            para cuando haya que volver a ofrecerlo. */}
        {baseType(spec.fields[spec.primary_field]?.schema ?? {}) !== "string" ? (
          <Alert tone="attention" title={t("modality.primaryNotText")}>
            <p>
              <code className="font-mono">{spec.primary_field}</code>{" "}
              {t("modality.primaryNotTextBody")}
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
          placeholder={t("modality.newFieldPlaceholder")}
          cta={t("modality.addField")}
          onAdd={addField}
          validate={(name) => fieldNameError(name, names, tr)}
          disabled={stageLocked}
        />
      </div>
    </div>
  );
}

export function ProfileScreen({ stage }: { stage: StageState | undefined }) {
  return (
    <StageGate stage={stage}>
      <ProfileEditor />
    </StageGate>
  );
}

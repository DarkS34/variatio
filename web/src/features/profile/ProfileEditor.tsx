import { useMutation } from "@tanstack/react-query";
import {
  ChevronsDownUp,
  ChevronsUpDown,
  Plus,
  Star,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  StageGate,
  useRegisterPendingEdit,
  useStageLocked,
} from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Textarea } from "@/components/ui/input";
import { Alert, LoadError, Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import type { ExemplarsProfile, FieldSpec, ItemTypeSpec, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { splitCriterion } from "@/lib/difficulty";
import { difficultyFieldOf, difficultyLevelsOf } from "@/lib/profile";
import { embedFields } from "@/lib/profile";
import { useInvalidateChain, useProfile } from "@/state/queries";

import { FieldEditor, baseType, fieldNameError, nameError } from "./FieldEditor";
import { useConfirm } from "@/components/ui/confirm";
import { useT } from "@/lib/i18n";

/**
 * A box that adds one thing, and it is drawn only while the stage is being corrected.
 *
 * It takes no `disabled`: an empty box and a button carry no information at all, so in the
 * static view there is nothing to keep visible and greying them out would claim something
 * is wrong when the only thing true is that this is not the moment's task.
 */
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
          aria-label={placeholder}
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
      <Button variant="outline" onClick={submit} disabled={!text.trim() || Boolean(error)}>
        <Plus />
        {cta}
      </Button>
    </div>
  );
}

/**
 * The types, as the tabs that choose which one is being read.
 *
 * Choosing one is not correcting anything, so the strip is drawn in both states; what
 * lives only in the correcting one is what ADDS and REMOVES a type. «Añadir un tipo» sat
 * against the tabs of a screen somebody had opened to read it, where it reads as a
 * question about the tab beside it rather than as an offer.
 */
function TypeStrip({
  keys,
  active,
  labels,
  onSelect,
  onAdd,
  onRemove,
  editing,
}: {
  keys: string[];
  active: string;
  labels: Record<string, string>;
  onSelect: (key: string) => void;
  onAdd: (key: string) => void;
  onRemove: (key: string) => void;
  editing: boolean;
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
            {keys.length > 1 && editing ? (
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

      {editing ? (
        <AddInline
          placeholder={t("modality.newPlaceholder")}
          cta={t("modality.add")}
          onAdd={onAdd}
          validate={(key) => nameError(key, keys, tr)}
        />
      ) : null}
    </div>
  );
}

/**
 * A value somebody wrote, drawn as what it is.
 *
 * A disabled `Textarea` is not text: it is a control that will not work, and it reads as
 * one. So the static view renders prose — keeping the line breaks, because the criteria
 * and the rules are written with them.
 */
function Written({ text, className }: { text: string; className?: string }) {
  const { t } = useT();
  const value = text.trim();
  return (
    <p
      className={cn(
        "whitespace-pre-line text-body",
        value ? null : "text-muted-foreground",
        className,
      )}
    >
      {value || t("modality.empty")}
    </p>
  );
}

/** The label over a block that has no control under it, in the type of `Field`'s own. */
function Caption({ children }: { children: string }) {
  return <p className="text-micro font-condensed uppercase text-muted-foreground">{children}</p>;
}

/** The rule's number, shared by the two states so they cannot drift apart. */
function RuleNumber({ n, className }: { n: number; className?: string }) {
  return (
    <span
      className={cn(
        "flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-micro nums text-muted-foreground",
        className,
      )}
    >
      {n}
    </span>
  );
}

/**
 * The ladder, and what puts an exercise on each rung.
 *
 * The criterion is ONE string in the artifact and `splitCriterion` is what takes it apart;
 * a text it cannot take apart comes back whole and is drawn whole, over the bare ladder.
 * When it does come apart, every DECLARED rung gets a row — including one the criterion
 * says nothing about, or a ladder of three would be drawn as a ladder of two.
 */
function DifficultyRead({
  levels,
  description,
}: {
  levels: string[];
  description?: string | null;
}) {
  const { t } = useT();
  const { lead, rungs } = splitCriterion(description, levels);
  const clause = new Map(rungs.map((rung) => [rung.level, rung.text]));

  if (rungs.length)
    return (
      <div className="space-y-2">
        {lead ? <p className="whitespace-pre-line text-body">{lead}</p> : null}
        <dl className="space-y-1.5">
          {levels.map((level) => (
            <div key={level} className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <dt>
                <Badge variant="outline">{level}</Badge>
              </dt>
              <dd className="min-w-0 flex-1 text-body text-muted-foreground">
                {clause.get(level) ?? t("modality.difficulty.rungSilent")}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {levels.map((level) => (
          <Badge key={level} variant="outline">
            {level}
          </Badge>
        ))}
      </div>
      {lead ? (
        <p className="whitespace-pre-line text-body">{lead}</p>
      ) : (
        <p className="text-body text-muted-foreground">{t("modality.difficulty.noCriterion")}</p>
      )}
    </div>
  );
}

export function ProfileEditor() {
  const tr = useT();
  const { t } = tr;
  const query = useProfile();
  const invalidate = useInvalidateChain();
  // VIEWING AND CORRECTING ARE TWO MOMENTS. Locked — for either reason — this is a static
  // view: what somebody wrote is rendered as text, and a control that only serves to change
  // it is not drawn at all. Hidden and not greyed, because nothing is wrong here.
  const editing = !useStageLocked();

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

  // THIS SCREEN HAS NO «Guardar» OF ITS OWN: what writes the file is `StageGate`'s
  // correction bar — «Guardar los cambios», pinned to the foot of the window — and
  // «Continuar», which saves first and closes the stage after. What is offered upwards is
  // the draft, so those buttons know there is something pending and why it may not be
  // written — the sentence is the pipeline validator's own, because refusing without saying
  // why is what this screen exists to avoid. `discard` is what «Dejar de corregir» does once
  // it has asked. `draft` is null only before the first read, where `dirty` is false and
  // `save` unreachable.
  useRegisterPendingEdit({
    dirty,
    blocked: validation?.valid === false ? (validation.error ?? t("profileEditor.invalid")) : null,
    save: async () => {
      if (draft) await save.mutateAsync(draft);
    },
    discard: () => setDraft(query.data?.profile ?? null),
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

  // THE DIFFICULTY IS NOT ONE MORE FIELD. Every modality carries one, its ladder is shared
  // by all of them and only its criterion is its own — so what a person edits is that
  // criterion, once, up in «Qué tipo es», and not a row in the list with a name, a type and
  // an obligatoriedad it does not get to choose. Editing it in two places is what the
  // «(i) and visible text never say the same thing» rule is about.
  const difficultyField = difficultyFieldOf(spec) ?? query.data?.difficulty?.field ?? null;
  const difficultyLevels = difficultyLevelsOf(spec).length
    ? difficultyLevelsOf(spec)
    : (query.data?.difficulty?.levels ?? []);
  const difficulty = difficultyField ? spec.fields[difficultyField] : undefined;
  const names = Object.keys(spec.fields).filter((name) => name !== difficultyField);
  const rules = spec.general_generation_rules ?? [];
  const indexed = embedFields(spec);

  // Absent means a profile written before difficulty was guaranteed, so the first edit
  // materialises it exactly as a build would — the canonical name and ladder come from the
  // server, which is the only side that knows the workspace's prompt language.
  const setDifficultyCriterion = (description: string) => {
    if (!difficultyField) return;
    const previous = spec.fields[difficultyField];
    updateType({
      fields: {
        ...spec.fields,
        [difficultyField]: {
          ...previous,
          schema: previous?.schema ?? { enum: difficultyLevels },
          description,
          decided_by: "user",
        },
      },
    });
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
            // Born with the difficulty, like every type a build writes: it is not
            // something a person adds, so there is no control that would add it.
            ...(query.data?.difficulty
              ? {
                  [query.data.difficulty.field]: {
                    schema: { enum: query.data.difficulty.levels },
                    description: "",
                    decided_by: "user" as const,
                  },
                }
              : {}),
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
    const order = [...names];
    const index = order.indexOf(name);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target], order[index]];
    if (difficultyField && difficultyField in spec.fields) order.push(difficultyField);
    updateType({
      fields: Object.fromEntries(order.map((key) => [key, spec.fields[key]])),
    });
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
      {/* THE STICKY BAR AT THE TOP IS GONE (2026-09-02): what it carried — the unsaved
          badge, the validator's sentence, the saving spinner — is what `StageGate`'s
          correction bar says at the foot of the window, beside the save button that acts on
          it. Two bars saying one thing a screen apart is the rule about the (i) and the
          visible text. */}
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
          editing={editing}
        />

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            {/* No `pb-2` here or on the card beside it: the header's own `p-4` leaves 16 px
                under the title, which is the gap between two fields — so every element of
                the block is the same distance from the next one. Both cards of the row
                change together or their contents stop starting at the same height. */}
            <CardHeader>
              <div className="flex items-center gap-2">
                <CardTitle>{t("modality.identity")}</CardTitle>
                <InfoHint label={t("modality.identity.hintLabel")}>
                  {t("modality.identity.hint")}
                </InfoHint>
              </div>
            </CardHeader>
            {/* `space-y-4` and not the `space-y-2` this had: `Field` separates its own
                label from its own control by 6 px, so at 8 px the gap BETWEEN two fields
                was barely wider than the gap INSIDE one and the three read as a single
                undifferentiated block. 16 px is 2.7× the internal gap, which is what makes
                the grouping legible; the difficulty's own 8 px between its rungs and its
                box stays below it, so the hierarchy holds. */}
            <CardContent className="space-y-4">
              {/* The readable name is on the tab that selected this type, so reading it
                  here would be reading it twice; it comes back as a field the moment it
                  can be changed. */}
              {editing ? (
                <Field label={t("modality.readableName")}>
                  <Input
                    value={spec.label ?? ""}
                    placeholder={t("modality.readableName.placeholder")}
                    onChange={(event) => updateType({ label: event.target.value })}
                  />
                </Field>
              ) : null}

              {editing ? (
                <Field label={t("modality.description")}>
                  <Textarea
                    autoGrow
                    value={spec.description ?? ""}
                    placeholder={t("modality.description.placeholder")}
                    className="min-h-20"
                    onChange={(event) => updateType({ description: event.target.value })}
                  />
                </Field>
              ) : (
                <div className="space-y-1.5">
                  <Caption>{t("modality.description")}</Caption>
                  <Written text={spec.description ?? ""} />
                </div>
              )}

              {/* THE LADDER IS SHARED AND THE CRITERION IS THE TYPE'S OWN. The sentence
                  that used to say so between the two halves went on 2026-09-02 (explicit
                  user request): the rungs are drawn above and the criterion below, and a
                  paragraph explaining that arrangement is one a person preparing a subject
                  reads once and then steps over for ever.

                  The rungs are shown and not offered — that is what lets one level mean one
                  thing across the whole list and lets the list be ordered by it. The
                  render-prop form is not decoration: the label has to reach the textarea,
                  and `Field` only injects into a single element child. */}
              {editing ? (
                <Field label={t("modality.difficulty")}>
                  {(props) => (
                    <div>
                      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                        {difficultyLevels.map((level) => (
                          <Badge key={level} variant="outline">
                            {level}
                          </Badge>
                        ))}
                      </div>
                      <Textarea
                        {...props}
                        autoGrow
                        value={difficulty?.description ?? ""}
                        placeholder={t("modality.difficulty.placeholder")}
                        className="min-h-20"
                        onChange={(event) => setDifficultyCriterion(event.target.value)}
                      />
                    </div>
                  )}
                </Field>
              ) : (
                <div className="space-y-1.5">
                  <Caption>{t("modality.difficulty")}</Caption>
                  <DifficultyRead
                    levels={difficultyLevels}
                    description={difficulty?.description}
                  />
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              {/* BEHIND THE (i) since 2026-09-01, by explicit user request, reversing the
                  «visible, not hidden» this card carried. What it explains is what a rule
                  HAS TO BE — checkable against an item already written, naming its field,
                  useless if it would fit any subject — which is read once, when writing
                  the first one, and then sits over the list for ever. The rule it bends is
                  the app's own «visible beats hidden»; what keeps it honest is that
                  nothing else on the screen says it, so the (i) is the only carrier and
                  not a second copy. */}
              <CardTitle className="flex items-center gap-1.5">
                {t("modality.rules")}
                <InfoHint label={t("modality.rules.hintLabel")}>{t("modality.rules.body")}</InfoHint>
              </CardTitle>
            </CardHeader>
            {/* A numbered list either way, because that is what the rules ARE: the
                correcting state writes into the numbers, the static one reads them. */}
            <CardContent className="space-y-2">
              {editing ? (
                <>
                  {rules.map((rule, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <RuleNumber n={index + 1} className="mt-2" />
                      <Textarea
                        autoGrow
                        aria-label={t("modality.rule.n", { n: index + 1 })}
                        value={rule}
                        className="min-h-16"
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
                        title={t("modality.rule.remove")}
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
                    onClick={() => updateType({ general_generation_rules: [...rules, ""] })}
                  >
                    <Plus />
                    {t("modality.rule.add")}
                  </Button>
                </>
              ) : rules.length ? (
                <ol className="space-y-2">
                  {rules.map((rule, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <RuleNumber n={index + 1} className="mt-0.5" />
                      <Written text={rule} className="min-w-0 flex-1" />
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-small text-attention">{t("modality.rules.none")}</p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* «Campos de …» IS DRAWN ONLY WHILE CORRECTING (explicit user request). An editor
            per field — its identifier, its type, whether it is obligatory — is the most
            technical question the whole path asks, and it was greeting somebody who had
            opened the screen to read it. What was worth learning from them is asked where
            it belongs: «¿Las partes de cada tipo son las correctas?» is in the
            questionnaire beside this, so nothing is lost by not offering the editor. */}
        {editing ? (
          <>
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
            {names.map((name, index) => (
              <FieldEditor
                key={name}
                name={name}
                spec={spec.fields[name]}
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
          />
          </>
        ) : null}
      </div>
    </div>
  );
}

// How many types the opening sentence names before it stops naming them. Every profile in
// the reference workspaces declares between two and six, so nothing real is elided; past
// that the sentence becomes a wall, and the count at its head stays true either way
// because what is left over is said out loud rather than dropped.
const MAX_NAMED_TYPES = 6;

/**
 * WHAT CAME OUT OF THE BUILD, COUNTED AND NAMED (explicit user request).
 *
 * The sentence under the title was the same paragraph whatever the profile turned out to
 * hold, so it could not say the one thing somebody opening this screen has to know: how
 * many shapes of exercise were found and what they are called. Only this screen holds
 * those, which is why it hands the sentence up rather than the header reaching down.
 *
 * `undefined` while there is no profile yet, because that is what `StageGate` falls back
 * on: «se han detectado 0 tipos» for half a second is worse than the generic sentence.
 * With ONE type the tabs are not a way of filtering anything, so nothing invites a press.
 *
 * What it counts is the file, twice over. Not the editor's draft — «se han detectado» is
 * about what the build produced, not about a name somebody is halfway through typing, and
 * the two can only differ while the bar below is saying «sin guardar». And not the file at
 * all during a REBUILD: the builder writes at the end, so the query still serves the
 * profile about to be replaced, and the header would spend the build naming types on their
 * way out — under a screen that hides that very artifact for exactly that reason.
 */
function useProfileIntro(stage: StageState | undefined): ReactNode {
  const { t, plural, language } = useT();
  const query = useProfile();
  const stale = !stage || stage.status === "building";
  const profile = !stale && query.data?.exists ? query.data.profile : null;
  const names = profile
    ? Object.entries(profile.item_types).map(([key, spec]) => spec.label || key)
    : [];
  if (!names.length) return undefined;

  const shown = names.slice(0, MAX_NAMED_TYPES);
  const rest = names.length - shown.length;
  // The list joiner is the language's own: Spanish puts «y» before the last name and
  // English an Oxford comma, and neither belongs in a catalogue string.
  const listed = new Intl.ListFormat(language, { type: "conjunction" }).format(
    rest ? [...shown, plural("stage.what.profile.more", rest)] : shown,
  );

  return (
    <p className="max-w-[74ch] text-body text-muted-foreground">
      {[
        plural("stage.what.profile.found", names.length, { names: listed }),
        t("stage.what.profile.why"),
      ].join(" ")}
    </p>
  );
}

export function ProfileScreen({ stage }: { stage: StageState | undefined }) {
  const intro = useProfileIntro(stage);
  return (
    <StageGate stage={stage} intro={intro}>
      <ProfileEditor />
    </StageGate>
  );
}

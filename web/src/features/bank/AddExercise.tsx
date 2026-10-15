import { useMutation } from "@tanstack/react-query";
import { Check, Eye, Pencil, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ConceptPicker } from "@/components/ConceptPicker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CARD_CHOICE, CARD_CHOSEN, ChoiceMark, ChoicePill } from "@/components/ui/choice";
import { ConceptChip } from "@/components/ui/concept-chip";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Label, Select, Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import { ItemFields } from "@/apps/generation/ResultCard";
import { api } from "@/lib/api";
import { splitCriterion } from "@/lib/difficulty";
import { fieldText } from "@/lib/fields";
import { truncate } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";
import { fieldLabel } from "@/lib/profile";
import { readableValue } from "@/lib/text";
import type {
  BankItem,
  BankItemType,
  ExemplarsProfile,
  FieldSpec,
  ItemTypeSpec,
  Job,
  KgConcept,
  NewBankItem,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { useStream } from "@/state/queries";

import { inputsOf, isList, isRequired, orderedFields, valueOf } from "./exercise";
import { HIDDEN, VisibilityPicker, choiceBody, choiceComplete, type VisibilityChoice } from "./Visibility";

/** Who decides an exercise's concepts: the tagger, as for the exercises of the documents, or
 *  the teacher who wrote it. */
type Tagging = "auto" | "manual";

/** What the dialog opens on: an empty exercise, or one already written (a generated one). */
export interface ExerciseStart {
  itemType: string | null;
  fields: Record<string, unknown>;
  /** The concepts «Los elijo yo» opens with. */
  concepts?: string[];
  primary?: string | null;
  /** A sentence over the form, such as which fields a generated exercise was made without. */
  note?: string | null;
  /** Open on the exercise as it is read, with a way to correct it: one already written. */
  reading?: boolean;
  /** Keep its type: a generated exercise was written in one. */
  lockType?: boolean;
}

/** An exercise as it was saved, and the tagging queued on it if the system tags it. */
interface Saved {
  item: BankItem;
  job: Job | null;
  tagging: Tagging;
}

/**
 * «Nuevo ejercicio»: a teacher writes an exercise for the bank, in two steps, and sees it saved.
 *
 * The two steps are the two decisions there are (the user's request, 2026-10-14: «un flow
 * intuitivo, diseña bien»): what the exercise says, and who decides its concepts. The second
 * opens on the system tagging it, which is how every other exercise of the bank got its
 * concepts. Going back keeps everything.
 *
 * SAVING DOES NOT CLOSE IT. It turns into what was saved, and the concepts arrive in place —
 * queued, being tagged, chosen —, so a teacher sees the exercise get its concepts without
 * looking for it in the table. «Añadir otro» keeps the type and the level, because a teacher
 * writes several of a kind in a row. Closing before the tagging ends cuts nothing: the job
 * goes on, and the table's row says «Etiquetando» until its concepts land.
 *
 * The same dialog passes a generated exercise into the bank (`start`), opening on what the
 * model wrote; `save` is what each door posts.
 */
export function AddExerciseDialog({
  itemTypes,
  profile,
  concepts,
  start,
  title,
  description,
  saveLabel,
  another = true,
  canShow = false,
  save,
  onClose,
}: {
  itemTypes: BankItemType[];
  profile: ExemplarsProfile | null;
  concepts: KgConcept[];
  start?: ExerciseStart;
  title: string;
  description: string;
  saveLabel: string;
  /** Whether «Añadir otro» is offered once it is saved. */
  another?: boolean;
  /** Whether the API lets the class see it from the start: «¿Qué ve la clase?». */
  canShow?: boolean;
  save: (body: NewBankItem) => Promise<{ item: BankItem; job: Job | null }>;
  /** Called with the ids saved during this opening, in the order they were saved. */
  onClose: (saved: string[]) => void;
}) {
  const { t } = useT();
  const confirm = useConfirm();
  const firstType = start?.itemType ?? itemTypes[0]?.key ?? null;
  const [typeKey, setTypeKey] = useState<string | null>(firstType);
  const [values, setValues] = useState<Record<string, string>>(() => inputsOf(start?.fields));
  const [step, setStep] = useState<1 | 2>(1);
  const [tagging, setTagging] = useState<Tagging>("auto");
  const [chosen, setChosen] = useState<string[]>(start?.concepts ?? []);
  const [primary, setPrimary] = useState<string | null>(start?.primary ?? null);
  const [problem, setProblem] = useState<{ field: string | null; message: string } | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);
  const [shown, setShown] = useState<VisibilityChoice>(HIDDEN);
  const ids = useRef<string[]>([]);

  const summary = itemTypes.find((type) => type.key === typeKey) ?? itemTypes[0];
  const spec = typeKey ? (profile?.item_types?.[typeKey] ?? null) : null;
  const fields = useMemo(() => orderedFields(summary, spec), [summary, spec]);

  const write = useMutation({
    mutationFn: (body: NewBankItem) => save(body),
    onSuccess: ({ item, job }) => {
      ids.current = [...ids.current, item.id];
      setSaved({ item, job, tagging });
    },
    onError: (error) => setProblem({ field: null, message: (error as Error).message }),
  });

  const written = Object.values(values).some((value) => value.trim() !== "");
  const close = async () => {
    if (!saved && written && !(await confirm({ title: t("bank.add.discard"), tone: "danger" })))
      return;
    onClose(ids.current);
  };

  // What step 1 has written, as the bank stores it; a field it cannot read is the problem.
  const build = (): Record<string, unknown> | null => {
    const out: Record<string, unknown> = {};
    for (const field of fields) {
      const raw = values[field] ?? "";
      const schema = spec?.fields?.[field]?.schema ?? {};
      if (raw.trim() === "") {
        if (isRequired(schema)) {
          // The level is asked as «Nivel», whatever the field is called.
          const name = field === summary?.difficulty_field ? t("bank.add.level") : fieldLabel(field, spec);
          setProblem({ field, message: t("bank.add.missing", { field: name }) });
          return null;
        }
        // Left empty: a field that may be null is written null — the bank's schema wants the
        // key —, one with a default is left for the default.
        if (!("default" in schema)) out[field] = null;
        continue;
      }
      const value = valueOf(raw, schema);
      if (value === undefined) {
        setProblem({ field, message: t("bank.add.notJson", { field: fieldLabel(field, spec) }) });
        return null;
      }
      out[field] = value;
    }
    setProblem(null);
    return out;
  };

  const next = () => {
    if (build() !== null) setStep(2);
  };

  const submit = () => {
    const built = build();
    if (built === null) {
      setStep(1);
      return;
    }
    if (tagging === "manual" && chosen.length === 0) {
      setProblem({ field: null, message: t("bank.add.pickOne") });
      return;
    }
    if (canShow && !choiceComplete(shown)) {
      setProblem({ field: null, message: t("bank.visibility.pickGroup") });
      return;
    }
    write.mutate({
      item_type: typeKey,
      fields: built,
      tag: tagging,
      ...(tagging === "manual" ? { concepts: chosen, primary_concept: primary ?? chosen[0] } : {}),
      ...(canShow && shown.level !== "hidden" ? { visibility: choiceBody(shown) } : {}),
    });
  };

  const again = () => {
    // The type and the level stay: a teacher writes several of a kind in a row.
    const level = summary?.difficulty_field ? values[summary.difficulty_field] : undefined;
    setValues(level && summary?.difficulty_field ? { [summary.difficulty_field]: level } : {});
    setChosen([]);
    setPrimary(null);
    setSaved(null);
    setProblem(null);
    setStep(1);
  };

  const footer = saved ? (
    <>
      {another ? (
        <Button variant="outline" onClick={again}>
          {t("bank.add.another")}
        </Button>
      ) : null}
      <Button onClick={() => onClose(ids.current)}>{t("common.close")}</Button>
    </>
  ) : step === 1 ? (
    <>
      <Button variant="ghost" onClick={close}>
        {t("common.cancel")}
      </Button>
      <Button onClick={next}>{t("bank.add.next")}</Button>
    </>
  ) : (
    <>
      <Button variant="ghost" onClick={() => setStep(1)} disabled={write.isPending}>
        {t("bank.add.back")}
      </Button>
      <Button onClick={submit} disabled={write.isPending}>
        {write.isPending ? <Spinner /> : null}
        {saveLabel}
      </Button>
    </>
  );

  return (
    <Dialog open onClose={close} title={title} description={description} className="sm:max-w-4xl" footer={footer}>
      {saved ? (
        <SavedExercise saved={saved} summary={summary} concepts={concepts} />
      ) : (
        <div className="space-y-5">
          <Steps step={step} />
          {start?.note && step === 1 ? (
            <p className="text-small text-muted-foreground">{start.note}</p>
          ) : null}
          {step === 1 ? (
            <ExerciseStep
              itemTypes={start?.lockType ? itemTypes.filter((type) => type.key === typeKey) : itemTypes}
              reading={start?.reading ? (start.fields ?? null) : null}
              typeKey={typeKey}
              onType={(key) => {
                setTypeKey(key);
                setProblem(null);
              }}
              summary={summary}
              spec={spec}
              fields={fields}
              values={values}
              onValue={(field, value) => setValues((current) => ({ ...current, [field]: value }))}
              problem={problem}
              build={build}
            />
          ) : (
            <>
              <ConceptsStep
                tagging={tagging}
                onTagging={setTagging}
                concepts={concepts}
                chosen={chosen}
                onChosen={setChosen}
                primary={primary}
                onPrimary={setPrimary}
              />
              {/* Hidden, like every exercise, unless its author shows it now. */}
              {canShow && summary ? (
                <div className="space-y-2 border-t border-border pt-4">
                  <Label>{t("bank.visibility.question")}</Label>
                  <VisibilityPicker value={shown} onChange={setShown} types={[summary]} profile={profile} />
                </div>
              ) : null}
            </>
          )}
          {problem && problem.field === null ? (
            <p role="alert" className="text-small text-destructive">
              {problem.message}
            </p>
          ) : null}
        </div>
      )}
    </Dialog>
  );
}

/** The two steps, numbered: the one being answered in ink, a finished one ticked. */
function Steps({ step }: { step: 1 | 2 }) {
  const { t } = useT();
  const names: Key[] = ["bank.add.step.exercise", "bank.add.step.concepts"];
  return (
    <ol aria-label={t("bank.add.steps")} className="flex flex-wrap items-center gap-x-5 gap-y-1">
      {names.map((name, index) => {
        const n = index + 1;
        const current = n === step;
        return (
          <li
            key={name}
            aria-current={current ? "step" : undefined}
            className={cn(
              "flex items-center gap-2 text-body",
              current ? "font-medium text-foreground" : "text-muted-foreground",
            )}
          >
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-small nums",
                current ? "border-primary bg-sunk" : "border-input",
              )}
            >
              {n < step ? <Check className="size-3.5" aria-hidden /> : n}
            </span>
            {t(name)}
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Step 1: the type, the level and the fields, the statement first and largest.
 *
 * Every field is labelled with its name and helped with the profile's own description of it,
 * so a teacher reads what the exercises of the bank are expected to say. «Vista previa» draws
 * the exercise as it is read everywhere else — formulas and diagrams included —, because a
 * teacher who writes a formula has to see it before saving it.
 */
function ExerciseStep({
  itemTypes,
  reading,
  typeKey,
  onType,
  summary,
  spec,
  fields,
  values,
  onValue,
  problem,
  build,
}: {
  itemTypes: BankItemType[];
  /** The exercise to open on as it is read, when it is already written. */
  reading: Record<string, unknown> | null;
  typeKey: string | null;
  onType: (key: string) => void;
  summary: BankItemType | undefined;
  spec: ItemTypeSpec | null;
  fields: string[];
  values: Record<string, string>;
  onValue: (field: string, value: string) => void;
  problem: { field: string | null; message: string } | null;
  build: () => Record<string, unknown> | null;
}) {
  const { t } = useT();
  const [preview, setPreview] = useState<Record<string, unknown> | null>(reading);
  const types = useRadioGroup(
    itemTypes.map((type) => type.key),
    typeKey,
    onType,
  );
  const levelField = summary?.difficulty_field ?? null;
  const levels = summary?.difficulty_levels ?? [];
  const level = levelField ? (values[levelField] ?? "") : "";
  const rungs = useRadioGroup(levels, level || null, (value) => levelField && onValue(levelField, value));
  const criterion = splitCriterion(levelField ? spec?.fields?.[levelField]?.description : null, levels);
  const clause = criterion.rungs.find((rung) => rung.level === level)?.text;

  // The field a refusal names takes the focus, so the teacher lands where to write.
  useEffect(() => {
    if (!problem?.field) return;
    const node = document.getElementById(fieldId(problem.field));
    (node?.querySelector<HTMLElement>("[tabindex='0']") ?? node)?.focus();
  }, [problem]);

  return (
    <div className="space-y-5">
      {itemTypes.length > 1 ? (
        <div className="space-y-1.5">
          <Label>{t("bank.add.type")}</Label>
          {itemTypes.length <= 4 ? (
            <div role="radiogroup" aria-label={t("bank.add.type")} className="flex flex-wrap gap-2" {...types.group}>
              {itemTypes.map((type) => (
                <ChoicePill
                  key={type.key}
                  {...types.radio(type.key)}
                  chosen={type.key === typeKey}
                  onClick={() => onType(type.key)}
                >
                  {type.label || type.key}
                </ChoicePill>
              ))}
            </div>
          ) : (
            <Select
              aria-label={t("bank.add.type")}
              value={typeKey ?? ""}
              onChange={(event) => onType(event.target.value)}
              className="max-w-80"
            >
              {itemTypes.map((type) => (
                <option key={type.key} value={type.key}>
                  {type.label || type.key}
                </option>
              ))}
            </Select>
          )}
        </div>
      ) : null}

      {levelField && levels.length > 0 ? (
        <div className="space-y-1.5">
          <Label>{t("bank.add.level")}</Label>
          <div
            id={fieldId(levelField)}
            role="radiogroup"
            aria-label={t("bank.add.level")}
            className="flex flex-wrap gap-2"
            {...rungs.group}
          >
            {levels.map((rung) => (
              <ChoicePill
                key={rung}
                {...rungs.radio(rung)}
                chosen={rung === level}
                onClick={() => onValue(levelField, rung)}
              >
                {readableValue(rung)}
              </ChoicePill>
            ))}
          </div>
          {/* What the chosen rung means, in the words of the type's own criterion: the
              teacher places the exercise on the scale the generator reads. */}
          {clause ? <p className="text-small text-muted-foreground">{clause}</p> : null}
          {problem?.field === levelField ? (
            <p role="alert" className="text-small text-destructive">
              {problem.message}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          className="h-7"
          onClick={() => {
            if (preview) setPreview(null);
            else {
              const built = build();
              if (built !== null) setPreview(built);
            }
          }}
        >
          {preview ? <Pencil /> : <Eye />}
          {preview ? t(reading ? "bank.promote.correct" : "bank.add.write") : t("bank.add.preview")}
        </Button>
      </div>

      {preview ? (
        <div className="well space-y-3 p-4">
          <ItemFields item={preview} spec={spec} />
        </div>
      ) : (
        <div className="space-y-4">
          {fields
            .filter((name) => name !== levelField)
            .map((name) => (
              <FieldInput
                key={name}
                name={name}
                spec={spec?.fields?.[name]}
                typeSpec={spec}
                primary={name === summary?.primary_field}
                value={values[name] ?? ""}
                onChange={(value) => onValue(name, value)}
                error={problem?.field === name ? problem.message : null}
              />
            ))}
        </div>
      )}
    </div>
  );
}

/** One field of the exercise: a closed list as a select, a list one entry per line, the rest
 *  as text. Its label is the field's name and its help the profile's description of it. */
function FieldInput({
  name,
  spec,
  typeSpec,
  primary,
  value,
  onChange,
  error,
}: {
  name: string;
  spec: FieldSpec | undefined;
  typeSpec: ItemTypeSpec | null;
  primary: boolean;
  value: string;
  onChange: (value: string) => void;
  error: string | null;
}) {
  const { t } = useT();
  const schema = spec?.schema ?? {};
  const id = fieldId(name);
  const options = Array.isArray(schema.enum) ? schema.enum.map(String) : null;
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>
        {fieldLabel(name, typeSpec)}
        {isRequired(schema) ? "" : ` · ${t("bank.add.optional")}`}
        {isList(schema) ? ` · ${t("bank.listField")}` : ""}
      </Label>
      {spec?.description ? (
        <p className="text-small text-muted-foreground">{spec.description}</p>
      ) : null}
      {options ? (
        <Select
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="max-w-80"
          aria-invalid={error ? true : undefined}
        >
          <option value="" />
          {options.map((option) => (
            <option key={option} value={option}>
              {readableValue(option)}
            </option>
          ))}
        </Select>
      ) : (
        <Textarea
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={cn("text-body", primary ? "min-h-36" : "min-h-20")}
          aria-invalid={error ? true : undefined}
        />
      )}
      {error ? (
        <p role="alert" className="text-small text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Step 2: the system tags it, or the teacher chooses its concepts and the main one. */
function ConceptsStep({
  tagging,
  onTagging,
  concepts,
  chosen,
  onChosen,
  primary,
  onPrimary,
}: {
  tagging: Tagging;
  onTagging: (next: Tagging) => void;
  concepts: KgConcept[];
  chosen: string[];
  onChosen: (next: string[]) => void;
  primary: string | null;
  onPrimary: (next: string | null) => void;
}) {
  const { t } = useT();
  const options: { value: Tagging; title: Key; body: Key }[] = [
    { value: "auto", title: "bank.add.auto.title", body: "bank.add.auto.body" },
    { value: "manual", title: "bank.add.manual.title", body: "bank.add.manual.body" },
  ];
  const radios = useRadioGroup(
    options.map((option) => option.value),
    tagging,
    onTagging,
  );
  return (
    <div className="space-y-4">
      <div
        role="radiogroup"
        aria-label={t("bank.add.step.concepts")}
        className="grid gap-3 sm:grid-cols-2"
        {...radios.group}
      >
        {options.map((option) => {
          const on = option.value === tagging;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={on}
              {...radios.radio(option.value)}
              onClick={() => onTagging(option.value)}
              className={cn(CARD_CHOICE, "flex items-start gap-3 rounded-inner p-3", on && CARD_CHOSEN)}
            >
              <ChoiceMark chosen={on} className="mt-1.5" />
              <span className="space-y-1">
                <span className="block text-body font-medium">{t(option.title)}</span>
                <span className="block text-small text-muted-foreground">{t(option.body)}</span>
              </span>
            </button>
          );
        })}
      </div>
      {tagging === "manual" ? (
        <div>
          <ConceptPicker
            concepts={concepts.filter((concept) => concept.taggable)}
            selected={chosen}
            onChange={onChosen}
            primary={primary}
            onPrimaryChange={onPrimary}
            maxHeight="16rem"
          />
        </div>
      ) : null}
    </div>
  );
}

/**
 * The exercise as it was saved, and its concepts as they arrive.
 *
 * With the system tagging it the concepts are read off the tagging's own run — queued, being
 * tagged, done — and, should the stream have missed its end, off the bank once the job is
 * over. A tagging that found nothing, or failed, offers to choose them by hand; one that found
 * some offers to change them.
 */
function SavedExercise({
  saved,
  summary,
  concepts,
}: {
  saved: Saved;
  summary: BankItemType | undefined;
  concepts: KgConcept[];
}) {
  const { t } = useT();
  const { item, job } = saved;
  const run = useStream().runs[job?.id ?? ""];
  const status = run?.job?.status ?? job?.status ?? null;
  const tagged = run?.tagged.find((entry) => entry.id === item.id);
  const [read, setRead] = useState<BankItem | null>(null);
  const [own, setOwn] = useState<{ concepts: string[]; primary: string | null } | null>(
    saved.tagging === "manual"
      ? { concepts: item.concepts ?? [], primary: item.primary_concept ?? null }
      : null,
  );
  const [editing, setEditing] = useState(false);
  const over = status === "succeeded" || status === "failed" || status === "cancelled";

  // The stream says what the tagger decided; a run it missed is read back off the bank.
  useEffect(() => {
    if (!over || tagged || read || own) return;
    let live = true;
    api
      .bank({ q: item.id, page_size: 5 })
      .then((listing) => live && setRead(listing.items.find((row) => row.id === item.id) ?? null))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [over, tagged, read, own, item.id]);

  const found = own
    ? own
    : tagged
      ? { concepts: tagged.concepts, primary: tagged.primary_concept }
      : read
        ? { concepts: read.concepts ?? [], primary: read.primary_concept ?? null }
        : null;

  const statement = summary ? fieldText(item[summary.primary_field]) : "";
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">
          <Check />
          {t("bank.add.saved", { id: item.id })}
        </Badge>
      </div>
      <p className="line-clamp-3 whitespace-pre-wrap text-body">{truncate(statement, 400)}</p>
      <div className="space-y-2 border-t border-border pt-4">
        <Label>{t("bank.concepts")}</Label>
        {editing ? (
          <ChooseConcepts
            itemId={item.id}
            concepts={concepts}
            start={found}
            onSaved={(next) => {
              setOwn(next);
              setEditing(false);
            }}
          />
        ) : found && found.concepts.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2">
            {orderedFirst(found.concepts, found.primary).map((concept) => (
              <ConceptChip
                key={concept}
                tone={concept === found.primary ? "primary" : "default"}
                title={concept === found.primary ? t("concept.isPrimary") : undefined}
              >
                {concept}
              </ConceptChip>
            ))}
            <Button variant="ghost" size="sm" className="h-7" onClick={() => setEditing(true)}>
              <Pencil />
              {t("bank.add.change")}
            </Button>
          </div>
        ) : over || (found && found.concepts.length === 0 && saved.tagging === "auto") ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="attention">
              <TriangleAlert />
              {status === "failed" || status === "cancelled" ? t("bank.add.failed") : t("bank.add.none")}
            </Badge>
            <Button variant="outline" size="sm" className="h-7" onClick={() => setEditing(true)}>
              {t("bank.add.chooseThem")}
            </Button>
          </div>
        ) : (
          <p className="flex items-center gap-2 text-small text-muted-foreground" aria-live="polite">
            {status === "running" ? <Spinner /> : null}
            {status === "running" ? t("bank.add.tagging") : t("bank.add.queued")}
          </p>
        )}
      </div>
    </div>
  );
}

/** The concepts of a saved exercise chosen by hand, the main one marked. */
function ChooseConcepts({
  itemId,
  concepts,
  start,
  onSaved,
}: {
  itemId: string;
  concepts: KgConcept[];
  start: { concepts: string[]; primary: string | null } | null;
  onSaved: (next: { concepts: string[]; primary: string | null }) => void;
}) {
  const { t } = useT();
  const [chosen, setChosen] = useState<string[]>(start?.concepts ?? []);
  const [primary, setPrimary] = useState<string | null>(start?.primary ?? null);
  const write = useMutation({
    mutationFn: () => api.setConcepts(itemId, chosen, primary ?? chosen[0] ?? null),
    onSuccess: () => onSaved({ concepts: chosen, primary: primary ?? chosen[0] ?? null }),
  });
  return (
    <div className="space-y-3">
      <div>
        <ConceptPicker
          concepts={concepts.filter((concept) => concept.taggable)}
          selected={chosen}
          onChange={setChosen}
          primary={primary}
          onPrimaryChange={setPrimary}
          maxHeight="14rem"
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" className="h-7" disabled={chosen.length === 0 || write.isPending} onClick={() => write.mutate()}>
          {write.isPending ? <Spinner /> : null}
          {t("bank.add.saveConcepts")}
        </Button>
        {write.isError ? (
          <span className="text-small text-destructive">{(write.error as Error).message}</span>
        ) : null}
      </div>
    </div>
  );
}

/** The element of a field of the form, by the field's name. */
function fieldId(name: string): string {
  return `exercise-field-${name}`;
}

/** A list with the primary concept first. */
function orderedFirst(concepts: string[], primary: string | null): string[] {
  return concepts.slice().sort((a, b) => Number(b === primary) - Number(a === primary));
}

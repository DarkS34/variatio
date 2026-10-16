import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ChevronRight,
  Eye,
  Plus,
  Star,
  RefreshCw,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Diagram } from "@/components/Diagram";
import { ConceptPicker } from "@/components/ConceptPicker";
import {
  StageGate,
  useStageLocked,
  useStageLockReason,
  useStageLockedHint,
  type StageControl,
} from "@/components/StageGate";
import { AddExerciseDialog } from "./AddExercise";
import { GeneratedList } from "./GeneratedList";
import { VisibilityBadge, VisibilityDialog } from "./Visibility";
import { Pager } from "./Pager";
import { SetAside } from "./SetAside";
import { TagLive } from "./TagLive";
import { Badge } from "@/components/ui/badge";
import { ConceptBadge, ConceptChip } from "@/components/ui/concept-chip";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Label, SearchInput, Select, Textarea } from "@/components/ui/input";
import { Checkbox, LoadError, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { TabCount, Tabs } from "@/components/ui/tabs";
import { useExerciseTotal } from "@/consumers/generation/GenerationsPanel";
import { diagramSource } from "@/lib/diagram";
import { api } from "@/lib/api";
import { fieldText, fieldToInput, hasBrokenText, inputToField, isCodeField, isEmptyField } from "@/lib/fields";
import { dayMonth, truncate } from "@/lib/format";
import { isLive } from "@/lib/queue";
import { fieldLabel } from "@/lib/profile";
import { readableValue } from "@/lib/text";
import type {
  BankItem,
  BankItemType,
  BankListing,
  ClassGroup,
  KgConcept,
  StageState,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useActiveWorkspace,
  useClassGroups,
  useEngineOffline,
  useInvalidateChain,
  useJobRun,
  useKg,
  useProfile,
  useStream,
  useSubmitJob,
} from "@/state/queries";
import { useSession } from "@/state/auth";
import { useConfirm } from "@/components/ui/confirm";
import { useT } from "@/lib/i18n";

/**
 * A control that exists only to CORRECT the bank.
 *
 * Hidden and never greyed while the stage is being looked at: nothing on screen is wrong,
 * and a dimmed button says otherwise.
 */
function Correction({ children }: { children: ReactNode }) {
  return useStageLockReason() === "reviewing" ? null : <>{children}</>;
}

/** What is drawn only while the stage is being looked at: `Correction`'s other half. */
function Reviewing({ children }: { children: ReactNode }) {
  return useStageLockReason() === "reviewing" ? <>{children}</> : null;
}

/** An item's temas with the primary one first. It is the tagging's own answer, and the row
 *  draws at most three, so leaving it in the raw order lets it be the badge that is cut. */
function orderedConcepts(item: BankItem): string[] {
  return (item.concepts ?? [])
    .slice()
    .sort((a, b) => Number(b === item.primary_concept) - Number(a === item.primary_concept));
}

interface ItemDialogProps {
  item: BankItem;
  fields: string[];
  primaryField: string;
  concepts: KgConcept[];
  /** Whether the API can tag one exercise again (`POST /api/bank/tag`); not the demo's. */
  canRetag: boolean;
  onClose: () => void;
  onSaved: () => void;
}

/** One field as it is READ: its name through `fieldLabel`, code in a block, prose as prose.
 *  The dialog and the expanded row both draw fields with it, so opening an exercise one way
 *  or the other cannot show the same field two ways — and `fieldLabel` is what extends that
 *  to the third reading, the card on "Generar ejercicios". */
function FieldBlock({ field, value, primary = false }: { field: string; value: unknown; primary?: boolean }) {
  const { t } = useT();
  return (
    <div className="space-y-1">
      <Label>
        {fieldLabel(field)}
        {primary ? t("bank.primaryField") : ""}
      </Label>
      {diagramSource(fieldText(value)) !== null ? (
        <Diagram code={fieldText(value)} />
      ) : isCodeField(field) ? (
        <CodeBlock code={fieldText(value)} maxHeight="16rem" />
      ) : (
        <p className="whitespace-pre-wrap text-body">{fieldText(value)}</p>
      )}
    </div>
  );
}

function ItemDialog(props: ItemDialogProps) {
  return useStageLocked() ? <ItemReading {...props} /> : <ItemEditor {...props} />;
}

function ItemReading({ item, fields, primaryField, onClose }: ItemDialogProps) {
  const { t } = useT();
  const concepts = orderedConcepts(item);

  return (
    <Dialog
      open
      onClose={onClose}
      title={t("bank.item", { id: item.id })}
      description={item.source ? t("bank.source", { source: item.source }) : undefined}
      className="max-w-4xl"
      footer={
        <Button variant="ghost" onClick={onClose}>
          {t("common.close")}
        </Button>
      }
    >
      {/* One column, the concepts FIRST: they are the answer of this step, and the fields
          take the width rather than being read through half a dialog. */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 border-b border-border pb-4">
          <Label>{t("bank.concepts")}</Label>
          <InfoHint label={t("bank.howTagged")}>{t("bank.howTaggedBody")}</InfoHint>
          {concepts.length === 0 ? (
            <Badge variant="attention">
              <TriangleAlert />
              {t("bank.noConcept")}
            </Badge>
          ) : (
            /* A `ConceptChip` and not a `Badge`, unlike the table's row: this is the same
               dialog the EDITOR draws, and there the concepts are `ConceptPicker`'s chips —
               so reading an exercise and correcting it showed one list two ways. The row
               keeps its badges because its two-line box is 50 px and a chip is 26. */
            concepts.map((concept) => (
              <ConceptChip
                key={concept}
                tone={concept === item.primary_concept ? "primary" : "default"}
                title={concept === item.primary_concept ? t("concept.isPrimary") : undefined}
              >
                {concept}
              </ConceptChip>
            ))
          )}
        </div>
        {/* An empty field is skipped rather than drawn empty: here it is nothing to read,
            where in the form it is a gap somebody may want to fill. */}
        {fields.map((field) =>
          isEmptyField(item[field]) ? null : (
            <FieldBlock key={field} field={field} value={item[field]} primary={field === primaryField} />
          ),
        )}
      </div>
    </Dialog>
  );
}

function ItemEditor({
  item,
  fields,
  primaryField,
  concepts,
  canRetag,
  onClose,
  onSaved,
}: ItemDialogProps) {
  const { t } = useT();
  const listFields = useMemo(
    () => new Set(fields.filter((field) => Array.isArray(item[field]))),
    [fields, item],
  );
  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const field of fields) {
      initial[field] = fieldToInput(item[field]);
    }
    return initial;
  });
  const [selected, setSelected] = useState<string[]>(item.concepts ?? []);
  const [primary, setPrimary] = useState<string | null>(item.primary_concept ?? null);
  const [error, setError] = useState<string | null>(null);

  const saveFields = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {};
      for (const field of fields) {
        payload[field] = inputToField(values[field] ?? "", listFields.has(field));
      }
      return api.patchItem(item.id, payload);
    },
  });

  const saveConcepts = useMutation({
    mutationFn: () => api.setConcepts(item.id, selected, primary),
  });
  const retag = useMutation({ mutationFn: () => api.tagItems([item.id]) });

  // The statement of a tagged exercise rewritten: its concepts were decided on the old one,
  // so the save may hand it back to the tagger instead of keeping the concepts below.
  const restated =
    canRetag &&
    (item.concepts ?? []).length > 0 &&
    (values[primaryField] ?? "") !== fieldToInput(item[primaryField]);

  const submit = async (again = false) => {
    setError(null);
    try {
      await saveFields.mutateAsync();
      if (again) await retag.mutateAsync();
      else await saveConcepts.mutateAsync();
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const pending = saveFields.isPending || saveConcepts.isPending || retag.isPending;

  return (
    <Dialog
      open
      onClose={onClose}
      title={t("bank.item", { id: item.id })}
      description={item.source ? t("bank.source", { source: item.source }) : undefined}
      className="max-w-4xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          {restated ? (
            <Button
              variant="outline"
              onClick={() => submit(true)}
              disabled={pending}
              title={t("bank.saveAndRetagHint")}
            >
              <RefreshCw />
              {t("bank.saveAndRetag")}
            </Button>
          ) : null}
          <Button onClick={() => submit()} disabled={pending}>
            {pending ? <Spinner /> : null}
            {t("common.save")}
          </Button>
        </>
      }
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="space-y-3">
          {fields.map((field) => (
            <div key={field} className="space-y-1">
              <Label htmlFor={`bank-item-${field}`}>
                {field}
                {field === primaryField ? t("bank.primaryField") : ""}
                {listFields.has(field) ? ` · ${t("bank.listField")}` : ""}
              </Label>
              <Textarea
                id={`bank-item-${field}`}
                value={values[field] ?? ""}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [field]: event.target.value }))
                }
                className={cn("text-body", field === primaryField ? "min-h-28" : "min-h-20")}
              />
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <div>
            <div className="mb-2 flex items-center gap-1.5">
              <Label>{t("bank.concepts")}</Label>
              <InfoHint label={t("bank.howTagged")}>{t("bank.howTaggedBody")}</InfoHint>
            </div>
            <ConceptPicker
              concepts={concepts}
              selected={selected}
              onChange={setSelected}
              primary={primary}
              onPrimaryChange={setPrimary}
              maxHeight="14rem"
            />
          </div>

        </div>
      </div>

      {error ? <p className="mt-3 text-small text-destructive">{error}</p> : null}
    </Dialog>
  );
}

/**
 * «Manual» or «Generado» before an exercise a person put in the bank, with who did and when.
 *
 * Nothing for one collected from the documents, which is the ordinary case, nor on an API
 * that sends no origin (the demo's).
 */
function OriginBadge({ item }: { item: BankItem }) {
  const { t } = useT();
  if (item.origin !== "manual" && item.origin !== "generated") return null;
  const date = item.added_at ? dayMonth(item.added_at) : null;
  const title = !date
    ? undefined
    : item.added_by
      ? t("bank.origin.addedBy", { name: item.added_by.name, date })
      : t("bank.origin.addedOn", { date });
  return (
    <Badge variant="outline" className="py-0" title={title}>
      {t(item.origin === "manual" ? "bank.origin.manual" : "bank.origin.generated")}
    </Badge>
  );
}

function ItemRow({
  item,
  primaryField,
  secondaryFields,
  typeLabel,
  groups,
  difficulty,
  showDifficulty,
  selected,
  tagging,
  selectable,
  onToggle,
  onEdit,
  onDelete,
  onVisibility,
  onStar,
}: {
  item: BankItem;
  primaryField: string;
  secondaryFields: string[];
  typeLabel: string | null;
  /** The class's groups, to name the ones an exercise is shown to. */
  groups: ClassGroup[];
  difficulty: string | null;
  showDifficulty: boolean;
  selected: boolean;
  /** The tagger is on it now: a job of this teacher's names it (`tag_item`). */
  tagging: boolean;
  /** Whether rows may be ticked outside correcting: what the class sees is chosen for several. */
  selectable: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  /** Opens what the class sees of it; absent on an API with no marks (the demo's). */
  onVisibility?: () => void;
  onStar?: () => void;
}) {
  const { t } = useT();
  const locked = useStageLocked();
  const lockedHint = useStageLockedHint();
  // A selection made while correcting outlives the boxes that made it, and a tinted row
  // whose cause is off screen reads as the table having decided something.
  const reviewing = useStageLockReason() === "reviewing";
  const [open, setOpen] = useState(false);
  const untagged = !tagging && (!item.concepts || item.concepts.length === 0);
  const text = fieldText(item[primaryField]);
  // Extracted before the grammar was dropped from remote bank extraction, so the statement
  // holds control characters where its accents were. Only a re-extraction repairs it; this
  // is what keeps the row from looking sound.
  const broken = hasBrokenText(item);
  // A chevron that opens onto nothing is not drawn: the fold holds the fields the modality
  // declares beside the statement, and an item may carry none of them. The whole item is
  // still one click away — the statement itself opens it.
  const ordered = orderedConcepts(item);
  const shownConcepts = ordered.slice(0, MAX_ROW_CONCEPTS);
  const restConcepts = ordered.slice(MAX_ROW_CONCEPTS);
  const hasDetail = secondaryFields.some((field) => !isEmptyField(item[field]));

  return (
    <>
      {/* `group` is what lets the row's BIN appear on hover: it is one icon repeated on
          every one of forty rows, so at rest it is forty pieces of furniture saying the
          same thing, and on the row you are pointing at it is the thing there is to do
          with it. `focus-within` is the other half and is not optional: a control that
          only exists under a mouse pointer does not exist for a keyboard. The chevron is
          NOT in that group — see the cell at the end of the row. */}
      <TR
        selected={selected && (selectable || !reviewing)}
        className={cn(
          // The chevron may not move when it is pressed, and a row GROWS on opening. `TR`'s
          // own `align-top` reaches no cell — `vertical-align` is not inherited and `TD`
          // sets `align-middle` itself — so it takes `[&>td]`, whose `.row > td` outranks
          // `.align-middle` wherever the two meet.
          "group align-top [&>td]:align-top",
          // Every collapsed row is the same height, or the table cannot be scanned down a
          // column. `height` on a table row is a MINIMUM and does half the work: the other
          // half is the clamping below, without which a long statement still pushes past.
          // 5.5rem is the measured ceiling of a full row — the id's line box at the table's
          // own 21 px, two clamped lines at 23.25, `py-2` either side and the border.
          !open && "h-[5.5rem]",
          untagged && "bg-[color-mix(in_oklch,var(--attention)_8%,transparent)]",
          // A teacher's star marks its row twice: the filled star at its end and an ink edge
          // down its start. Not a ground: a ground is what a ticked row already has.
          item.favourite && "[&>td:first-child]:shadow-[inset_3px_0_0_var(--primary)]",
        )}
      >
        {/* The box goes with what it is a handle for: re-tagging while correcting, and what
            the class sees, which is no correction and is chosen in either moment. Without
            a consumer the column would be a control down every row that does nothing. */}
        {selectable ? (
          <TD className="py-2 pl-3">
            <Checkbox
              checked={selected}
              onCheckedChange={onToggle}
              label={t("bank.selectItem", { id: item.id })}
              className="mt-1"
            />
          </TD>
        ) : (
          <Correction>
            <TD className="py-2 pl-3">
              <Checkbox
                checked={selected}
                onCheckedChange={onToggle}
                label={t("bank.selectItem", { id: item.id })}
                className="mt-1"
              />
            </TD>
          </Correction>
        )}
        <TD className="min-w-0 py-2 pl-2 pr-3">
          {/* The id rides above the statement instead of holding a column of its own: it is
              how you name an item when talking about it, not something anybody scans down.
              Beside it, where the exercise came from when a person put it there; collected
              from the documents is the ordinary case and says nothing. The line keeps the
              id's own 21 px, so the row keeps its measured height. */}
          <span className="flex h-[1.3125rem] items-center gap-1.5">
            <span className="font-mono text-micro tracking-normal text-muted-foreground">
              {item.id}
            </span>
            <OriginBadge item={item} />
            <VisibilityBadge visibility={item.visibility} groups={groups} />
          </span>
          <button
            onClick={onEdit}
            // Never `block` beside `line-clamp-2`: the clamp works by setting `display:
            // -webkit-box`, so a `block` wins the cascade and switches it off in silence.
            // An open row drops the clamp and the 200-character cut both — the fold is
            // where the exercise is read.
            className={cn(
              "text-left text-body whitespace-pre-wrap hover:underline",
              // `block` only when the clamp is off: clamped, `-webkit-box` is already
              // block-level; open, an inline button lands on the id's own line.
              open ? "block" : "line-clamp-2",
            )}
          >
            {open ? text : truncate(text, 200)}
          </button>
          {open && hasDetail ? (
            <div className="mt-3 space-y-3">
              {secondaryFields.map((field) =>
                isEmptyField(item[field]) ? null : (
                  <FieldBlock key={field} field={field} value={item[field]} />
                ),
              )}
            </div>
          ) : null}
        </TD>
        {typeLabel ? (
          <TD className="py-2 pl-2">
            {/* A badge is never broken over several lines. The column is fixed and a
                teacher writes the type's name, so a long one grows to two and three lines —
                and with `--radius: 0` the only shapes there are are the pill and the square
                rectangle, so a three-line pill is a lozenge whose round corners eat the
                text. It is cut with an ellipsis and the whole name goes in the `title`,
                which is the rule the `+N` beside it already follows: what is trimmed is
                named, never hidden. The `truncate` goes on a CHILD and not on the badge,
                because `text-overflow` does not act on the items of a flex container. */}
            <Badge variant="outline" className="max-w-full" title={typeLabel}>
              <span className="truncate">{typeLabel}</span>
            </Badge>
          </TD>
        ) : null}
        <TD className="py-2 pr-3">
          {/* Two rows of badges and no more, so the row keeps its height. What is cut is
              named rather than hidden: `+N` carries the rest in its title, and the primary
              concept is drawn FIRST so the one the tagger settled on is never the one that
              falls off the end. Two rows measure 48 px with micro at 12 (a badge is 22.2
              plus the 4 of `gap-1`), and at 2.875rem the second row lost its last 2 px. */}
          <div className="flex max-h-[3.125rem] max-w-64 flex-wrap gap-1 overflow-hidden">
            {broken ? (
              <Badge variant="danger" title={t("bank.brokenTextHint")}>
                <TriangleAlert />
                {t("bank.brokenText")}
              </Badge>
            ) : null}
            {tagging ? (
              <Badge variant="outline">
                <Spinner />
                {t("bank.tagging")}
              </Badge>
            ) : untagged ? (
              <Badge variant="attention">
                <TriangleAlert />
                {t("bank.noConcept")}
              </Badge>
            ) : (
              <>
                {/* THE PRIMARY CONCEPT IS THE FILLED BADGE. It used to be `default` against
                    `secondary`, which is a tone — measured on these very rows, 1.03:1 of
                    ground and 1.10:1 of text, so the two were the same badge and the `title`
                    was carrying the whole distinction alone. Filled it is 15.88:1, at no
                    extra width, which is what a row with a two-line badge box can afford.
                    `ConceptBadge` owns the fill, the cut and the `title`; the three lists
                    that read this same tagging share it so they cannot drift again. */}
                {shownConcepts.map((concept) => (
                  <ConceptBadge key={concept} primary={concept === item.primary_concept}>
                    {concept}
                  </ConceptBadge>
                ))}
                {restConcepts.length > 0 ? (
                  <Badge variant="outline" title={restConcepts.join(", ")}>
                    +{restConcepts.length}
                  </Badge>
                ) : null}
              </>
            )}
          </div>
        </TD>
        {showDifficulty ? (
          <TD className="py-2 pr-3">
            {/* The rung as the profile spells it, never a word invented here: what the
                three mean is written per type in "Tipos de ejercicio", and a label of our
                own would be a second copy of it. An item nobody classified says so rather
                than passing for the entry level. */}
            {difficulty ? (
              <Badge variant="secondary">{difficulty}</Badge>
            ) : (
              <span className="text-small text-muted-foreground">{t("bank.noDifficulty")}</span>
            )}
          </TD>
        ) : null}
        <TD className="whitespace-nowrap py-2 pr-3 text-right">
          <div className="inline-flex">
            {/* What the class sees and the star are no correction of the bank: they are in
                either moment of the stage. The eye on hover; the star always once it is on,
                since a favourite says so down the column. */}
            {onVisibility ? (
              <Button
                variant="ghost"
                size="icon-sm"
                className="opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
                onClick={onVisibility}
                title={t("bank.visibility.change", { id: item.id })}
                aria-label={t("bank.visibility.change", { id: item.id })}
              >
                <Eye />
              </Button>
            ) : null}
            {onStar ? (
              <Button
                variant="ghost"
                size="icon-sm"
                className={cn(
                  item.favourite
                    ? "text-primary"
                    : "opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100",
                )}
                onClick={onStar}
                aria-pressed={Boolean(item.favourite)}
                title={t(item.favourite ? "bank.unstar" : "bank.star", { id: item.id })}
                aria-label={t(item.favourite ? "bank.unstar" : "bank.star", { id: item.id })}
              >
                <Star fill={item.favourite ? "currentColor" : "none"} />
              </Button>
            ) : null}
            {/* The chevron is always drawn and the delete is not. Per-row chrome repeated
                forty times is furniture — true of the bin, false of this: opening a row is
                how the rest of an exercise is read, which is the task of the whole step, and
                a control that exists only under a pointer cannot be found at all on a touch
                screen. `--muted-foreground` at rest and full ink on hover, so a column of
                forty still reads as chrome. */}
            {hasDetail ? (
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground hover:text-foreground"
                onClick={() => setOpen((value) => !value)}
                aria-expanded={open}
                aria-label={t("bank.detail")}
              >
                <ChevronRight className={cn("transition-transform", open && "rotate-90")} />
              </Button>
            ) : null}
            <Correction>
              <Button
                variant="ghost"
                size="icon-sm"
                className="opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
                onClick={onDelete}
                disabled={locked}
                title={locked ? t(lockedHint) : t("bank.delete")}
                aria-label={t("bank.delete")}
              >
                <Trash2 />
              </Button>
            </Correction>
          </div>
        </TD>
      </TR>
    </>
  );
}

/** How many exemplars are drawn at once: what fits beside the questionnaire, which is
 *  where they are read. */
const PAGE_SIZE = 7;

/** How the origin filter tells an origin a person adds from the name of a document. */
const ORIGIN_FILTER = "origin:";

/** How many concepts a row draws before the rest become "+N". Three of ~10 characters is
 *  what fits in two rows of the column, measured over the two reference banks (219 items,
 *  median name 10 characters, 90th percentile 19). */
const MAX_ROW_CONCEPTS = 3;

function BankMeters({
  listing,
  onShowUntagged,
}: {
  listing: BankListing | undefined;
  onShowUntagged: () => void;
}) {
  const { t, plural } = useT();

  if (!listing) return <Skeleton className="h-24" />;

  const { items, tagged, untagged } = listing.totals;

  // Drawn only while some item is still missing a concept: a meter at 120/120 reports that
  // there is nothing to do. With an EMPTY bank it is drawn, because there "0 of 0" is not
  // "finished" but "there is no bank". It carries no control: the re-tag verbs are all at
  // the foot of the table (`TableActions`), so correcting the stage adds nothing above the
  // table and the rows never move when it opens.
  if (untagged === 0 && items > 0) return null;

  return (
    <Card className="space-y-2 p-5">
      <div className="flex items-baseline justify-between gap-2 text-body">
        <span className="text-muted-foreground">{t("bank.taggedItems")}</span>
        <span className="nums font-medium">
          {tagged}/{items}
        </span>
      </div>
      <Progress value={tagged} max={items} tone={untagged === 0 ? "settled" : "attention"} />
      {untagged > 0 ? (
        <button
          onClick={onShowUntagged}
          className="text-small text-attention transition-opacity hover:opacity-80"
        >
          {plural("bank.seeUntagged", untagged)}
        </button>
      ) : (
        <p className="text-small text-muted-foreground">{t("bank.emptyBank")}</p>
      )}
    </Card>
  );
}

/**
 * The re-tag verbs, at the foot of the table they act on.
 *
 * One place for every scope: with rows picked by hand, the count and what to do with those
 * rows; with none, the bank's own scopes — the exercises without a concept, then all of
 * them. The two sets take turns on the same spot, as a selection's gestures do in a
 * table's head. Every control is 28 px, the pager's height, so the strip keeps one height
 * whatever it holds.
 */
function TableActions({
  totals,
  selected,
  offline,
  submitting,
  onRetag,
  onClear,
  onShow,
}: {
  totals: BankListing["totals"];
  selected: Set<string>;
  offline: string | null;
  submitting: boolean;
  onRetag: (params: Record<string, unknown>) => void;
  onClear: () => void;
  /** Opens what the class sees of the ticked rows; absent on an API with no marks. */
  onShow?: () => void;
}) {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const locked = useStageLocked();
  const lockedHint = useStageLockedHint();

  const busy = locked || submitting || Boolean(offline);
  const why = locked ? t(lockedHint) : offline;
  const icon = submitting ? <Spinner /> : <RefreshCw />;

  if (selected.size > 0)
    return (
      <>
        <span className="text-small font-medium">{plural("bank.selectedCount", selected.size)}</span>
        {onShow ? <ShowButton count={selected.size} onClick={onShow} /> : null}
        <Button
          size="sm"
          className="h-7"
          variant="outline"
          disabled={busy}
          title={why ?? plural("bank.retagSelectedHint", selected.size)}
          onClick={() => onRetag({ ids: [...selected] })}
        >
          {icon}
          {t("bank.retagSelected")}
        </Button>
        <Button size="sm" variant="ghost" className="h-7" onClick={onClear}>
          {t("bank.deselect")}
        </Button>
      </>
    );

  const { items, untagged } = totals;
  return (
    <>
      {untagged > 0 ? (
        <Button
          size="sm"
          className="h-7"
          variant="outline"
          disabled={busy}
          title={why ?? plural("bank.retagUntaggedHint", untagged)}
          onClick={() => onRetag({})}
        >
          {icon}
          {plural("bank.retagUntagged", untagged)}
        </Button>
      ) : null}
      {items > 0 ? (
        <Button
          size="sm"
          className="h-7"
          // Outline when it is the strip's one verb; beside the narrower retry it steps back.
          variant={untagged > 0 ? "ghost" : "outline"}
          disabled={busy}
          title={why ?? plural("bank.retagAllHint", items)}
          onClick={async () => {
            if (await confirm({ title: plural("bank.confirmRetagAll", items), tone: "danger" }))
              onRetag({ all: true });
          }}
        >
          {untagged > 0 ? null : icon}
          {t("bank.retagAll")}
        </Button>
      ) : null}
    </>
  );
}

/** «Qué ve la clase (n)»: what the class sees of the rows ticked. */
function ShowButton({ count, onClick }: { count: number; onClick: () => void }) {
  const { plural } = useT();
  return (
    <Button size="sm" className="h-7" variant="outline" onClick={onClick}>
      <Eye />
      {plural("bank.visibility.bulk", count)}
    </Button>
  );
}

/**
 * The ticked rows while the stage is being looked at: what the class sees of them is chosen
 * in either moment, and re-tagging is a correction's (`TableActions`).
 */
function Selection({ count, onShow, onClear }: { count: number; onShow: () => void; onClear: () => void }) {
  const { t, plural } = useT();
  if (count === 0) return null;
  return (
    <>
      <span className="text-small font-medium">{plural("bank.selectedCount", count)}</span>
      <ShowButton count={count} onClick={onShow} />
      <Button size="sm" variant="ghost" className="h-7" onClick={onClear}>
        {t("bank.deselect")}
      </Button>
    </>
  );
}

/**
 * The bank as the second part of its step (`BankStep`): the stage without a header of its
 * own, its state handed in by the step that draws both parts. Its stale notice carries no
 * rebuild: collecting the bank again is the step's own way out, beside its title.
 */
export function BankPart({
  stage,
  control,
}: {
  stage: StageState | undefined;
  control: StageControl;
}) {
  const { t } = useT();
  const confirm = useConfirm();
  const kg = useKg();
  const submit = useSubmitJob();
  const invalidate = useInvalidateChain();
  const offline = useEngineOffline();

  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [itemType, setItemType] = useState("");
  const [source, setSource] = useState("");
  const [untagged, setUntagged] = useState<boolean | undefined>(undefined);
  const [difficulty, setDifficulty] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<BankItem | null>(null);
  const [adding, setAdding] = useState(false);
  const [tab, setTab] = useState<"bank" | "generated">("bank");
  const [markFilter, setMarkFilter] = useState<"all" | "visible" | "favourite">("all");
  const [showing, setShowing] = useState<BankItem[] | null>(null);
  // Every exercise read so far, so the rows ticked on other pages can be shown too.
  const known = useRef(new Map<string, BankItem>());
  const generatedTotal = useExerciseTotal(useActiveWorkspace());
  // After adding, the table opens on «Manuales» at the page of the last one added: set when
  // the dialog closes, spent when the listing filtered so arrives.
  const jump = useRef(false);
  const profile = useProfile();

  const workspace = useActiveWorkspace();
  useEffect(() => {
    setItemType("");
    // Same rule as the modality: a rung is a value THIS profile declares and the endpoint
    // answers 422 for one it does not, so carrying it across instances greets the screen
    // with an error about a filter nobody set.
    setDifficulty("");
    setPage(1);
  }, [workspace]);

  // Re-tagging puts the bank into "building", so only the live preview survives. What
  // belongs there is the order the tagger works in, which only the event stream knows:
  // it rewrites labels on the same items, so the file's own order never moves.
  const tagRun = useJobRun("tag");
  const tagStatus = tagRun?.job?.status;
  const tagging = tagStatus === "running" || tagStatus === "queued";

  // The origin filter holds a document's name, or one of the two origins a person adds.
  const origin = source.startsWith(ORIGIN_FILTER) ? source.slice(ORIGIN_FILTER.length) : undefined;
  const params = {
    q: query,
    item_type: itemType,
    source: origin ? undefined : source,
    origin,
    untagged,
    difficulty,
    visible: markFilter === "visible" ? true : undefined,
    favourite: markFilter === "favourite" ? true : undefined,
    page,
    page_size: PAGE_SIZE,
  };
  const bank = useQuery({
    queryKey: ["bank", workspace, params],
    queryFn: () => api.bank(params as never),
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === workspace ? previous : undefined,
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteItem(id),
    onSuccess: () => {
      invalidate();
      bank.refetch();
    },
  });

  const concepts = kg.data?.concepts ?? [];
  const listing = bank.data;
  // What this API answers about where exercises come from; none on an older one (the demo),
  // and with it go the origin badges, the two origins of the filter and «Añadir ejercicio».
  const origins = listing?.origins;
  // And who sees what, and the stars: the same, read off `marks`.
  const marks = listing?.marks;
  // The class's groups, to name the ones an exercise is shown to; asked only where marks are.
  const classGroups = useClassGroups(Boolean(marks)).data ?? [];
  for (const item of listing?.items ?? []) known.current.set(item.id, item);
  const star = useMutation({
    mutationFn: (item: BankItem) => api.star(item.id, !item.favourite),
    onSuccess: () => bank.refetch(),
  });
  const showTicked = () =>
    setShowing([...selected].map((id) => known.current.get(id) ?? ({ id } as BankItem)));

  // The exercises the tagger is on for this teacher (`tag_item`, its own jobs), and the
  // table read again each time one of those jobs ends, since its concepts land in the file.
  const me = useSession().data?.user.id;
  const stream = useStream();
  const taggingIds = useMemo(() => {
    const ids = new Set<string>();
    for (const run of Object.values(stream.runs)) {
      if (run.job?.kind !== "tag_item" || !isLive(run.job) || run.job.user_id !== me) continue;
      for (const id of (run.job.params?.items as string[] | undefined) ?? []) ids.add(id);
    }
    return ids;
  }, [stream, me]);
  const taggingKey = [...taggingIds].sort().join(",");
  const lastTagging = useRef(taggingKey);
  useEffect(() => {
    if (lastTagging.current !== taggingKey && lastTagging.current !== "") bank.refetch();
    lastTagging.current = taggingKey;
  }, [taggingKey, bank]);

  const pages = useMemo(
    () => (listing ? Math.max(1, Math.ceil(listing.total / listing.page_size)) : 1),
    [listing],
  );
  useEffect(() => {
    if (!jump.current || !listing || bank.isPlaceholderData || origin !== "manual") return;
    jump.current = false;
    if (page !== pages) setPage(pages);
  }, [listing, bank.isPlaceholderData, origin, page, pages]);

  // Which field carries an item's text is a property of its modality, not of the bank:
  // two modalities can name their primary differently, so every row resolves its own.
  const itemTypes: BankItemType[] = listing?.item_types ?? [];
  // Whether the modality column carries information: with one declared, or with the filter
  // pinning one, it is the same badge down every row saying what the filter already says.
  const manyTypes = itemTypes.length > 1 && !itemType;
  const severalDeclared = itemTypes.length > 1;
  const typeOf = (item: BankItem | null): BankItemType | undefined => {
    if (!item) return undefined;
    if (item.item_type) return itemTypes.find((t) => t.key === item.item_type);
    return itemTypes.length === 1 ? itemTypes[0] : undefined;
  };
  // WHICH KEY CARRIES THE DIFFICULTY comes from the server, not from a table here: the name
  // is the workspace's prompt language's (`nivel_dificultad` / `difficulty_level`) and a
  // table drawing a column has no business looking that up. Every modality declares the
  // same three rungs, which is what makes one column over a mixed list mean anything.
  const difficultyField = itemTypes.find((t) => t.difficulty_field)?.difficulty_field ?? null;
  // The rungs the profile declares, counted over the WHOLE bank rather than over the
  // page: the filter is about what is in there, and a count that moved with the other
  // filters would be describing the question instead of the answer. Read defensively —
  // an API older than this bundle sends no `difficulties` and the control just goes.
  const rungs = listing?.difficulties ?? [];
  const difficultyFor = (item: BankItem | null) => {
    const name = typeOf(item)?.difficulty_field;
    const value = name ? item?.[name] : undefined;
    return typeof value === "string" && value ? value : null;
  };
  const primaryFieldFor = (item: BankItem | null) => typeOf(item)?.primary_field ?? "";
  const fieldsFor = (item: BankItem | null) => typeOf(item)?.fields ?? [];
  // Out of the expanded detail, because it is the column at the end of the same row. It
  // stays in the item editor, where it is a value somebody corrects.
  const detailFieldsFor = (item: BankItem | null) =>
    fieldsFor(item).filter((f) => f !== primaryFieldFor(item) && f !== typeOf(item)?.difficulty_field);
  const labelFor = (item: BankItem | null) => typeOf(item)?.label ?? item?.item_type ?? "—";
  const primaryHeader = severalDeclared
    ? [...new Set(itemTypes.map((t) => t.primary_field))].join(" / ")
    : (itemTypes[0]?.primary_field ?? "contenido");

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  // Select-all acts on the page, not on the whole bank: the ids of the other pages are
  // not loaded, and re-tagging 3 000 items because a header box said "todos" is not what
  // anyone means by it.
  const pageIds = listing?.items.map((item) => item.id) ?? [];
  const selectedOnPage = pageIds.filter((id) => selected.has(id)).length;
  const pageSelected = pageIds.length > 0 && selectedOnPage === pageIds.length;
  const someSelected = selectedOnPage > 0 && !pageSelected;
  const togglePage = () =>
    setSelected((current) => {
      const next = new Set(current);
      if (pageSelected) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });
  const pageBox = (
    <Checkbox
      checked={pageSelected}
      indeterminate={someSelected}
      onCheckedChange={togglePage}
      label={pageSelected ? t("bank.deselectPage") : t("bank.selectPage")}
    />
  );

  // Whether the bank may be written to is NOT read here and cannot be: `reviewing` is
  // `StageGate`'s own state and this component is the one that renders it, so the hooks that
  // answer only work below. Every control that writes therefore reads it for itself.

  // Nothing is shown while the bank is being EXTRACTED: what is left in that state is the
  // phase bar and the notice beside it. The sliding window lives on in `TagLive`, which is a
  // different job — tagging patches items that are ALREADY in the bank, so its feed says
  // what is being decided rather than what is appearing.
  const livePreview = tagging ? <TagLive run={tagRun} /> : null;

  return (
    <StageGate
      stage={stage}
      control={control}
      headless
      staleAction={null}
      livePreview={livePreview}
    >
      {/* «Banco» is what the generator learns from; «Generados» is where candidates come from:
          this teacher's own exercises, to pass in the ones worth it. Two tabs and not three
          by origin, because an exercise passed in is both, and the bank is read whole. */}
      {origins ? (
        <Tabs
          className="mb-4"
          items={[
            { value: "bank", label: t("bank.tab.bank"), badge: <TabCount n={listing?.totals.items} /> },
            { value: "generated", label: t("bank.tab.generated"), badge: <TabCount n={generatedTotal} /> },
          ]}
          value={tab}
          onChange={(next) => setTab(next as "bank" | "generated")}
        />
      ) : null}
      {tab === "generated" && origins ? (
        <GeneratedList
          itemTypes={itemTypes}
          onToBank={(id) => {
            setTab("bank");
            setQuery(id);
            setSource("");
            setItemType("");
            setDifficulty("");
            setUntagged(undefined);
            setPage(1);
          }}
        />
      ) : (
        <div className="space-y-4">
          {origins ? (
            <SetAside
              itemTypes={itemTypes}
              profile={profile.data?.profile ?? null}
              concepts={concepts}
              onBack={() => {
                invalidate();
                bank.refetch();
              }}
            />
          ) : null}
          <BankMeters
            listing={listing}
            onShowUntagged={() => {
              setUntagged(true);
              setPage(1);
            }}
          />


          <div className="flex flex-wrap items-center gap-2">
            {marks ? (
              <Tabs
                items={[
                  { value: "all", label: t("bank.marks.all") },
                  { value: "visible", label: t("bank.marks.visible"), badge: <TabCount n={marks.visible} /> },
                  { value: "favourite", label: t("bank.marks.favourites"), badge: <TabCount n={marks.favourites} /> },
                ]}
                value={markFilter}
                onChange={(next) => {
                  setMarkFilter(next as "all" | "visible" | "favourite");
                  setPage(1);
                }}
              />
            ) : null}
            <SearchInput
              className="min-w-56 flex-1"
              aria-label={t("bank.search")}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
              placeholder={t("bank.search")}
            />
            {severalDeclared ? (
              <Select
                aria-label={t("bank.filterByModality")}
                value={itemType}
                onChange={(event) => {
                  setItemType(event.target.value);
                  setPage(1);
                }}
                className="max-w-56"
              >
                <option value="">{t("bank.allModalities")}</option>
                {itemTypes.map((type) => (
                  <option key={type.key} value={type.key}>
                    {type.label || type.key} ({type.count})
                  </option>
                ))}
              </Select>
            ) : null}
            <Select
              aria-label={t("bank.filterBySource")}
              value={source}
              onChange={(event) => {
                setSource(event.target.value);
                setPage(1);
              }}
              className="max-w-48"
            >
              <option value="">{t("bank.allSources")}</option>
              {origins ? (
                <>
                  <option value={`${ORIGIN_FILTER}manual`}>
                    {t("bank.origins.manual")} ({origins.manual})
                  </option>
                  <option value={`${ORIGIN_FILTER}generated`}>
                    {t("bank.origins.generated")} ({origins.generated})
                  </option>
                  {(listing?.sources ?? []).length > 0 ? (
                    <optgroup label={t("bank.origins.documents")}>
                      {(listing?.sources ?? []).map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </optgroup>
                  ) : null}
                </>
              ) : (
                (listing?.sources ?? []).map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))
              )}
            </Select>
            {/* The difficulty is a FILTER and not an order: the rungs are three, so ordering
                by them only groups the list, where "enséñame los avanzados" is the question
                somebody actually asks. The list is by id, which is extraction order.

                Offered only where a modality declares rungs: a filter with one option filters
                nothing. */}
            {rungs.length > 0 ? (
              <Select
                aria-label={t("bank.filterByDifficulty")}
                value={difficulty}
                onChange={(event) => {
                  setDifficulty(event.target.value);
                  setPage(1);
                }}
                className="max-w-48"
              >
                <option value="">{t("bank.allDifficulties")}</option>
                {rungs.map((rung) => (
                  <option key={rung.value} value={rung.value}>
                    {readableValue(rung.value)} ({rung.count})
                  </option>
                ))}
              </Select>
            ) : null}
            {/* Last of the row: the only one of the four that is not a property of an item
                but a state of the WORK, and a toggle among selects, so it reads as the end of
                the row rather than as a dropdown that lost its label. */}
            <Button
              variant={untagged === true ? "default" : "outline"}
              onClick={() => {
                setUntagged(untagged === true ? undefined : true);
                setPage(1);
              }}
            >
              <TriangleAlert />
              {t("bank.untagged")}
            </Button>
            {/* Writing an exercise by hand is a move of its own and not a correction of what
                the bank holds, so it is here in either moment of the stage. An outline: the
                step's coral is its way out. */}
            {origins ? (
              <Button variant="outline" onClick={() => setAdding(true)}>
                <Plus />
                {t("bank.add")}
              </Button>
            ) : null}
          </div>

          {bank.isError ? (
            <LoadError title={t("bank.unreadable")} error={bank.error} onRetry={bank.refetch} />
          ) : null}

          {listing ? (
            <div className="surface p-5">
              {/* FIXED LAYOUT, or an open row widens the table. Under the auto algorithm a
                  cell is never narrower than its longest unbreakable line, and a code block
                  with one such line in it — measured: 376 characters — pushed the table to
                  3 419 px inside a 1 406 px wrapper, with the chevron that closes the row
                  two screens to the right. Fixed, the columns are the header's widths, the
                  statement takes what is left, and the `<pre>` scrolls inside its own cell
                  as it was always meant to. */}
              <Table minWidth="48rem" className="table-fixed">
                <THead>
                  <TR>
                    {marks ? (
                      <TH className="w-8">{pageBox}</TH>
                    ) : (
                      <Correction>
                        <TH className="w-8">{pageBox}</TH>
                      </Correction>
                    )}
                    <TH>{primaryHeader}</TH>
                    {/* 15rem and not 10, and the number is measured: the nine type names of
                        the two reference subjects run from 142 to 262 px drawn as a badge, so
                        at 10rem every one of them was cut. At 15 eight of the nine fit whole
                        and the ellipsis goes back to being the exception, which is what
                        justifies solving it with a `title`. The statement pays for it — it is
                        clamped to two lines and had 766 px — and `minWidth` rises with it, or
                        in a narrow window the statement column is left with nothing. */}
                    {manyTypes ? <TH className="w-60">{t("bank.column.modality")}</TH> : null}
                    <TH className="w-72">{t("bank.column.concepts")}</TH>
                    {difficultyField ? (
                      <TH className="w-28">{t("bank.column.difficulty")}</TH>
                    ) : null}
                    {/* The eye and the star join the chevron and the bin where the marks exist. */}
                    <TH className={marks ? "w-32" : "w-20"} />
                  </TR>
                </THead>
                <TBody>
                  {listing.items.map((item) => (
                    <ItemRow
                      key={item.id}
                      item={item}
                      primaryField={primaryFieldFor(item)}
                      secondaryFields={detailFieldsFor(item)}
                      typeLabel={manyTypes ? labelFor(item) : null}
                      groups={classGroups}
                      difficulty={difficultyField ? difficultyFor(item) : null}
                      showDifficulty={Boolean(difficultyField)}
                      selected={selected.has(item.id)}
                      tagging={taggingIds.has(item.id)}
                      selectable={Boolean(marks)}
                      onVisibility={marks ? () => setShowing([item]) : undefined}
                      onStar={marks ? () => star.mutate(item) : undefined}
                      onToggle={() => toggle(item.id)}
                      onEdit={() => setEditing(item)}
                      onDelete={async () => {
                        if (await confirm({ title: t("bank.confirmDelete", { id: item.id }), tone: "danger" }))
                          remove.mutate(item.id);
                      }}
                    />
                  ))}
                </TBody>
              </Table>
              {listing.items.length === 0 ? (
                <p className="p-8 text-center text-body text-muted-foreground">
                  {t("bank.noneWithFilters")}
                </p>
              ) : null}

              {/* The foot of the table, and both things it says are about the table: where
                  you are in the bank and what you have picked out of it belong on one line,
                  inside the card they describe. There is no second pager at the top — for a
                  page of seven rows the whole list is in view.

                  There is deliberately no whole-bank "Etiquetar pendientes": extracting and
                  tagging are one job, the extractor tagging each document as it comes out. The
                  scoped retries are all here, beside the rows they reach (`TableActions`).
                  `min-h-7` is the controls' height, so the strip is one height whether they
                  are drawn (correcting) or not (reviewing). */}
              {listing.items.length > 0 ? (
                <div className="mt-3 flex min-h-7 flex-wrap items-center gap-x-3 gap-y-2 border-t border-border pt-3 text-body">
                  <Pager
                    page={listing.page}
                    pages={pages}
                    total={listing.total}
                    onPage={setPage}
                  />

                  <span className="flex-1" />

                  <Correction>
                    <TableActions
                      totals={listing.totals}
                      selected={selected}
                      offline={offline}
                      submitting={submit.isPending}
                      onRetag={(params) => submit.mutate({ kind: "tag", params })}
                      onClear={() => setSelected(new Set())}
                      onShow={marks ? showTicked : undefined}
                    />
                  </Correction>
                  {marks ? (
                    <Reviewing>
                      <Selection
                        count={selected.size}
                        onShow={showTicked}
                        onClear={() => setSelected(new Set())}
                      />
                    </Reviewing>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : (
            <Skeleton className="h-96" />
          )}
        </div>
      )}

      {showing && listing ? (
        <VisibilityDialog
          items={showing}
          itemTypes={itemTypes}
          profile={profile.data?.profile ?? null}
          onClose={(saved) => {
            setShowing(null);
            if (saved) bank.refetch();
          }}
        />
      ) : null}

      {adding && listing ? (
        <AddExerciseDialog
          itemTypes={itemTypes}
          profile={profile.data?.profile ?? null}
          concepts={concepts}
          title={t("bank.add.title")}
          description={t("bank.add.description")}
          saveLabel={t("bank.add.save")}
          canShow={Boolean(marks)}
          save={(body) => api.addItem(body)}
          onClose={(added) => {
            setAdding(false);
            if (added.length === 0) return;
            invalidate();
            jump.current = true;
            setSource(`${ORIGIN_FILTER}manual`);
            setQuery("");
            setItemType("");
            setDifficulty("");
            setUntagged(undefined);
            bank.refetch();
          }}
        />
      ) : null}

      {editing && listing ? (
        <ItemDialog
          item={editing}
          fields={fieldsFor(editing)}
          primaryField={primaryFieldFor(editing)}
          concepts={concepts}
          canRetag={Boolean(origins)}
          onClose={() => setEditing(null)}
          onSaved={() => {
            invalidate();
            bank.refetch();
          }}
        />
      ) : null}
    </StageGate>
  );
}

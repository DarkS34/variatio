import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Search,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { ConceptPicker } from "@/components/ConceptPicker";
import {
  StageGate,
  useStageLocked,
  useStageLockReason,
  useStageLockedHint,
} from "@/components/StageGate";
import { TagLive } from "./TagLive";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Checkbox, LoadError, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { api } from "@/lib/api";
import { fieldText, hasBrokenText, fieldToInput, inputToField, isEmptyField } from "@/lib/fields";
import { truncate } from "@/lib/format";
import { readableValue } from "@/lib/text";
import type {
  BankItem,
  BankItemType,
  BankListing,
  Coverage,
  KgConcept,
  StageState,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useActiveWorkspace,
  useCoverage,
  useEngineOffline,
  useInvalidateChain,
  useJobRun,
  useKg,
  useSubmitJob,
} from "@/state/queries";
import { useConfirm } from "@/components/ui/confirm";
import { useT } from "@/lib/i18n";

/**
 * A control that exists only to CORRECT the bank.
 *
 * Hidden — never greyed — while the stage is being looked at: nothing on screen is wrong,
 * and a dimmed button says otherwise. It comes back with «Quiero corregir algo» at the foot
 * of the page, closed stage or not (2026-09-02): the first write reopens it on the server.
 */
function Correction({ children }: { children: ReactNode }) {
  return useStageLockReason() === "reviewing" ? null : <>{children}</>;
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
  onClose: () => void;
  onSaved: () => void;
}

/**
 * ONE EXERCISE, WHOLE: the form, or the reading of it.
 *
 * Two components rather than one with every field refused. A dialog of greyed textareas
 * over an item nobody has objected to is the «atenuar en vez de ocultar» failure at full
 * size — it reports damage where there is none.
 *
 * The reading is not a control taken away either, and that is why it survives the hiding
 * pass: the row clamps the statement to two lines and draws three of its temas, so this is
 * the only place an exercise can be read entire with everything it was tagged with. Reading
 * one is precisely what this step asks of the person.
 */
/** One field as it is READ: the key as its label, code in a block, prose as prose. The
 *  dialog and the expanded row both draw fields with it, so opening an exercise one way or
 *  the other cannot show the same field two ways. */
function FieldBlock({ field, value, primary = false }: { field: string; value: unknown; primary?: boolean }) {
  const { t } = useT();
  return (
    <div className="space-y-1">
      <Label>
        {field}
        {primary ? t("bank.primaryField") : ""}
      </Label>
      {isCodeField(field) ? (
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
      {/* ONE COLUMN, THE CONCEPTS FIRST (2026-09-04, explicit user request to fix how an
          exercise looks when opened). The right column used to hold the tagger's trace
          beside the concepts; with the trace gone it held three badges and a hand's width
          of nothing, while the exercise was read through half the dialog. The concepts
          are the answer of this step, so they lead, and the fields take the width. */}
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
            concepts.map((concept) => (
              <Badge
                key={concept}
                variant={concept === item.primary_concept ? "default" : "secondary"}
                title={concept === item.primary_concept ? t("concept.isPrimary") : undefined}
              >
                {concept}
              </Badge>
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

  const submit = async () => {
    setError(null);
    try {
      await saveFields.mutateAsync();
      await saveConcepts.mutateAsync();
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const pending = saveFields.isPending || saveConcepts.isPending;

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
          <Button onClick={submit} disabled={pending}>
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
              <Label>
                {field}
                {field === primaryField ? t("bank.primaryField") : ""}
                {listFields.has(field) ? ` · ${t("bank.listField")}` : ""}
              </Label>
              <Textarea
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

// Field names come from the profile and are subject-specific, so "is this code?" can only
// ever be a guess; it decides presentation only, and guessing wrong costs a plain <p>.
export function isCodeField(field: string): boolean {
  const name = field.toLowerCase();
  return ["soluc", "codigo", "code", "solution", "material"].some((hint) =>
    name.includes(hint),
  );
}

function ItemRow({
  item,
  primaryField,
  secondaryFields,
  typeLabel,
  difficulty,
  showDifficulty,
  selected,
  onToggle,
  onEdit,
  onDelete,
}: {
  item: BankItem;
  primaryField: string;
  secondaryFields: string[];
  typeLabel: string | null;
  difficulty: string | null;
  showDifficulty: boolean;
  selected: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { t } = useT();
  const locked = useStageLocked();
  const lockedHint = useStageLockedHint();
  // A selection made while correcting survives going back to the view, where the box that
  // made it is no longer drawn — and a tinted row whose cause is off screen reads as the
  // table having decided something. Nothing is lost: the picks come back with the boxes.
  const reviewing = useStageLockReason() === "reviewing";
  const [open, setOpen] = useState(false);
  const untagged = !item.concepts || item.concepts.length === 0;
  const text = fieldText(item[primaryField]);
  // Extracted before the grammar was dropped from remote bank extraction: the statement
  // holds control characters where its accents used to be. Nothing here can repair it —
  // only a re-extraction can — but until this the row looked exactly like a sound one.
  const broken = hasBrokenText(item);
  // A CHEVRON THAT OPENS ONTO NOTHING IS NOT DRAWN. What the fold holds is the fields the
  // modality declares beside the statement, and an item may carry none of them — on the
  // reference bank `solucion` and `explicacion` came back null for every exercise, so with
  // the tagger's trace gone (2026-09-04, explicit user request) the control would have been
  // a button down forty rows that answers with an empty box. The whole item is still one
  // click away: the statement itself opens it.
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
        selected={selected && !reviewing}
        className={cn(
          // THE CHEVRON MAY NOT MOVE WHEN IT IS PRESSED (2026-09-04, explicit user request:
          // «se abre y luego no se puede cerrar o abrir otro»). `TR`'s own `align-top` never
          // reached a cell — `vertical-align` is not inherited, and `TD` sets `align-middle`
          // itself — so every cell was centred in a row that GROWS on opening: measured, the
          // chevron slid 48 px down on a 176 px row, out from under the pointer that had
          // just clicked it, and a second click landed on the empty top of the same cell and
          // did nothing. With a code field in the detail the row is several hundred pixels
          // tall and the control ends up in the middle of nowhere. `[&>td]` is what actually
          // reaches the cells: `.row > td` outranks `.align-middle` on specificity, so it
          // wins wherever the two meet.
          "group align-top [&>td]:align-top",
          // EVERY COLLAPSED ROW IS THE SAME HEIGHT (2026-09-01, explicit user request).
          // A table whose rows breathe with the length of a statement cannot be scanned
          // down a column, and the two cells that made them breathe are bounded rather
          // than shortened: the statement is clamped to two lines and the concepts to two
          // rows of badges. `height` on a table row is a MINIMUM, so it only does half the
          // work — the clamping is the other half, and without it a long statement would
          // still push past. An open row drops it: the detail it reveals is the point.
          // 5.5rem is the MEASURED ceiling of a full one since the scale moved on
          // 2026-09-04 (5rem before it): the id's line box is the table's own 21px and
          // not micro's 16.2 (an inline in a block sits on the parent's strut), plus two
          // clamped lines at 23.25, `py-2` either side and the border — 84.5 measured,
          // and at 5rem a one-line statement sat at 80 beside them.
          !open && "h-[5.5rem]",
          untagged && "bg-[color-mix(in_oklch,var(--attention)_8%,transparent)]",
        )}
      >
        {/* The box goes with what it is a handle for. Selecting rows has exactly one
            consumer, «Re-etiquetar selección», so with that hidden the column would be a
            control down every row that does nothing at all. */}
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
        <TD className="min-w-0 py-2 pl-2 pr-3">
          {/* The id rides above the statement instead of holding a column of its own: it is
              how you name an item when talking about it, not something anybody scans down. */}
          <span className="font-mono text-micro tracking-normal text-muted-foreground">
            {item.id}
          </span>
          <button
            onClick={onEdit}
            // NOT `block`: `line-clamp-2` works by setting `display: -webkit-box`, and a
            // `block` beside it wins in the cascade and switches the clamp off in silence
            // — measured, `display` computed `block` and a long statement ran to a third
            // line. `-webkit-box` is block-level anyway, so nothing else needed it. An
            // OPEN row drops both the clamp and the 200-character cut: the fold is where
            // the exercise is read, and a statement cut at «…» over its own solution was
            // the row saying less in the state that exists to say more.
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
            {/* UNA INSIGNIA NO SE PARTE EN VARIAS LÍNEAS. La columna es fija y hay nombres
                de tipo largos («Problema de construcción formal»), así que la insignia
                crecía a dos y tres líneas: con `--radius: 0` las únicas formas posibles son
                la píldora y el rectángulo a escuadra, y una píldora de tres líneas es un
                lozenge con las esquinas comiéndose el texto. Se corta con puntos
                suspensivos y el nombre entero va en el `title`, que es la misma regla que
                el `+N` de la celda de al lado: lo que se recorta se nombra, no se esconde.
                El `truncate` va en un hijo y no en la insignia, porque `text-overflow` no
                actúa sobre los ítems de un contenedor flex. */}
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
            {untagged ? (
              <Badge variant="attention">
                <TriangleAlert />
                {t("bank.noConcept")}
              </Badge>
            ) : (
              <>
                {/* EL PRINCIPAL SE DICE AL PASAR EL RATÓN, Y SÓLO ÉL. La diferencia entre
                    `default` y `secondary` es un tono, y un tono no se nota en una fila de
                    insignias: el `title` es lo que dice qué significa. Los demás no llevan
                    ninguno — un rótulo en cada uno sería ruido, y es el mismo criterio que
                    `ConceptPicker` ya aplica. */}
                {shownConcepts.map((concept) => (
                  <Badge
                    key={concept}
                    variant={concept === item.primary_concept ? "default" : "secondary"}
                    title={concept === item.primary_concept ? t("concept.isPrimary") : undefined}
                  >
                    {concept}
                  </Badge>
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
                three mean is written per type in «Tipos de ejercicio», and a label of our
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
            {/* THE CHEVRON IS ALWAYS DRAWN, AND THE DELETE IS NOT (2026-09-04, explicit user
                request: «se abre y luego no se puede cerrar o abrir cualquier otro»). The
                row's two controls were one `group-hover` block together, on the rule that
                per-row chrome repeated forty times is furniture — true of the bin, and
                false of this one. Opening a row is how the rest of an exercise is read,
                which is the task of the whole step, and a control that only exists under a
                pointer is a control nobody can find: measured in the lab, with no hover
                every one of the seven chevrons computes `opacity: 0`, so after opening one
                row there is visibly nothing to press on any other — and on a touch screen
                there is no hover to recover them with. It is `--muted-foreground` at rest
                and full ink on hover, so a column of forty still reads as chrome. */}
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

/**
 * WHAT THE BANK IS WORTH, AS ONE STRIP.
 *
 * It was three cards across a full row — tagging, coverage, thresholds — each with its own
 * heading, border and (i), sitting above a forty-row table. Three boxes is what you build
 * when three numbers arrive from three places, and it reads as three subjects; there is
 * only one, «is this bank good enough to generate from», and the three answer it in
 * descending order of how much you can do about it.
 *
 * So: the two that are progress get the width and the meters, and the thresholds — which
 * are read here and changed in «Configuración» — become the small print they always were.
 *
 * THE TWO GLOBAL RE-TAG ACTIONS MOVE HERE, next to the number they act on. They were in
 * different places at different weights: «Re-etiquetar los N» inside the tagging card,
 * «Re-etiquetar todo» beside it, and «Re-etiquetar selección» in a bar that appears at the
 * bottom of the page — three affordances for one verb, and the only way to know which
 * scope you were about to hit was to notice where you had clicked. The selection one stays
 * where it is on purpose: it is contextual, it appears only when there is a selection, and
 * it belongs to the rows it acts on rather than to the totals.
 */
/** Cuántos ejemplares se dibujan de una vez. */
const PAGE_SIZE = 7;

/** How many concepts a row draws before the rest become «+N». Three of ~10 characters is
 *  what fits in two rows of the column, measured over the two reference banks (219 items,
 *  median name 10 characters, 90th percentile 19). */
const MAX_ROW_CONCEPTS = 3;

/** What the listing may be ordered by. `recent` is the live view's and is never offered
 *  here; `difficulty` only appears when the profile declares one. */

/**
 * WHICH PAGE OF THE BANK, AND THE TWO STEPS EITHER SIDE OF IT.
 *
 * Drawn TWICE — over the table and under it (2026-09-01, explicit user request) — because
 * a page here is forty rows tall and the only way to reach the next one was to scroll to
 * the bottom of the one you had just read. That is not a duplicated control in the sense
 * the house rule forbids: it is one control at both ends of a long list, which is what a
 * pager is for, and both ends read the same `page`.
 */
function Pager({
  page,
  pages,
  total,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (next: number) => void;
}) {
  const { t, plural } = useT();
  return (
    <>
      <span className="text-small nums text-muted-foreground">
        {plural("bank.pageOf", total, { page, pages })}
      </span>
      {pages > 1 ? (
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={t("common.previous")}
            title={t("common.previous")}
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={t("common.next")}
            title={t("common.next")}
            disabled={page >= pages}
            onClick={() => onPage(page + 1)}
          >
            <ChevronRight />
          </Button>
        </div>
      ) : null}
    </>
  );
}

function BankMeters({
  listing,
  coverage,
  offline,
  submitting,
  onRetag,
  onShowUntagged,
}: {
  listing: BankListing | undefined;
  coverage: Coverage | undefined;
  offline: string | null;
  submitting: boolean;
  onRetag: (params: Record<string, unknown>) => void;
  onShowUntagged: () => void;
}) {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const locked = useStageLocked();
  const lockedHint = useStageLockedHint();

  if (!listing) return <Skeleton className="h-24" />;

  const { items, tagged, untagged } = listing.totals;
  const busy = locked || submitting || Boolean(offline);
  const why = locked ? t(lockedHint) : offline;

  return (
    <Card className="flex flex-col divide-y divide-border lg:flex-row lg:divide-x lg:divide-y-0">
      {/* SÓLO MIENTRAS FALTE ALGUNO (2026-09-01, explicit user request). Un medidor a
          120/120 informa de que no hay nada que hacer, que es la definición de ruido; lo
          que hay que ver es el resto, y para eso está. Con el banco vacío sí se dibuja,
          porque ahí «0 de 0» no es «terminado» sino «no hay banco». */}
      {untagged > 0 || items === 0 ? (
        <div className="flex-[1.2] space-y-2 p-4">
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
        </div>
      ) : null}

      <div className="flex-[1.2] space-y-2 p-4">
        <div className="flex items-baseline justify-between gap-2 text-body">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            {t("bank.conceptsWithExample")}
            <InfoHint label={t("bank.coverageHint")}>{t("bank.coverageBody")}</InfoHint>
          </span>
          <span className="nums font-medium">
            {coverage ? `${coverage.covered}/${coverage.total}` : "—"}
          </span>
        </div>
        {/* El rótulo ERA la línea de debajo: «Cobertura del currículo» arriba y «Conceptos
            con ejemplo» debajo decían lo mismo dos veces, y la de abajo lo decía mejor. */}
        <Progress value={coverage?.covered ?? 0} max={coverage?.total ?? null} tone="settled" />
      </div>

      {/* LOS DOS RE-ETIQUETADOS GLOBALES SON CORRECCIÓN, y desaparecen enteros mientras la
          etapa se mira: son las dos únicas cosas de esta franja que ESCRIBEN. Lo que dicen
          no se pierde al ocultarlos, y por eso pueden ocultarse — cuántos ejercicios están
          sin tema lo dice el medidor de al lado, y «Ver los N sin concepto», que es un
          filtro, sigue ahí. La columna entera se va con ellos: vacía sería un cuarto de
          tarjeta con su borde y su relleno anunciando que aquí había algo. */}
      <Correction>
        <div className="flex flex-[0.9] flex-col items-start gap-2 p-4">
          <div className="flex flex-wrap gap-2">
            {untagged > 0 ? (
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                title={why ?? plural("bank.retagUntaggedHint", untagged)}
                onClick={() => onRetag({})}
              >
                {submitting ? <Spinner /> : <RefreshCw />}
                {plural("bank.retagUntagged", untagged)}
              </Button>
            ) : null}
            {items > 0 ? (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                title={why ?? plural("bank.retagAllHint", items)}
                onClick={async () => {
                  if (await confirm({ title: plural("bank.confirmRetagAll", items), tone: "danger" }))
                    onRetag({ all: true });
                }}
              >
                {t("bank.retagAll")}
              </Button>
            ) : null}
          </div>
          {/* «Umbral 0.4 · 10 candidatos» ya no se dibuja (2026-09-01, explicit user
              request). Son dos ajustes de recuperación que se leían aquí y se cambian en
              «Configuración»: quien prepara una asignatura no decide nada con ellos, y en la
              franja que responde «¿sirve ya este banco?» eran la única línea que no lo
              respondía. Siguen en el payload del listado. */}
        </div>
      </Correction>
    </Card>
  );
}

/**
 * WHAT TO DO WITH THE ROWS PICKED BY HAND, at the foot of the table they were picked from.
 *
 * The third scope of one verb and the only contextual one, so it stays down here rather
 * than joining the two global re-tags in the strip above. It is correction all the same and
 * goes with the boxes that feed it while the stage is only being looked at.
 */
function SelectionActions({
  selected,
  offline,
  submitting,
  onRetag,
  onClear,
}: {
  selected: Set<string>;
  offline: string | null;
  submitting: boolean;
  onRetag: () => void;
  onClear: () => void;
}) {
  const { t, plural } = useT();
  const locked = useStageLocked();
  const lockedHint = useStageLockedHint();

  if (selected.size === 0) return null;

  return (
    <>
      <span className="text-small font-medium">{plural("bank.selectedCount", selected.size)}</span>
      <Button
        size="sm"
        variant="outline"
        disabled={locked || submitting || Boolean(offline)}
        title={
          locked ? t(lockedHint) : (offline ?? plural("bank.retagSelectedHint", selected.size))
        }
        onClick={onRetag}
      >
        {submitting ? <Spinner /> : <RefreshCw />}
        {t("bank.retagSelected")}
      </Button>
      <Button size="sm" variant="ghost" onClick={onClear}>
        {t("bank.deselect")}
      </Button>
    </>
  );
}

export function BankScreen({ stage }: { stage: StageState | undefined }) {
  const { t } = useT();
  const confirm = useConfirm();
  const kg = useKg();
  const coverage = useCoverage();
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

  const workspace = useActiveWorkspace();
  useEffect(() => {
    setItemType("");
    // Same rule as the modality: a rung is a value THIS profile declares, and the endpoint
    // answers 422 for one it does not — so carrying it into another instance would greet
    // the screen with an error about a filter nobody set here.
    setDifficulty("");
    setPage(1);
  }, [workspace]);

  // Re-tagging puts the bank into «building» like a rebuild does, so StageGate hides the
  // whole screen and only the live preview survives. What belongs there is NOT the file
  // — re-tagging rewrites labels on the same items, so `order=recent` returns the
  // same ten rows from beginning to end — but the order the tagger works in, which
  // only the event stream knows.
  const tagRun = useJobRun("tag");
  const tagStatus = tagRun?.job?.status;
  const tagging = tagStatus === "running" || tagStatus === "queued";

  // SIETE POR PÁGINA (2026-09-01, explicit user request). Cuarenta filas era un listado
  // que se recorría con la rueda del ratón y en el que la paginación no pintaba nada;
  // siete caben de una vez en la mitad izquierda de la pantalla, junto al cuestionario,
  // que es donde se leen.
  const params = { q: query, item_type: itemType, source, untagged, difficulty, page, page_size: PAGE_SIZE };
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

  const pages = useMemo(
    () => (listing ? Math.max(1, Math.ceil(listing.total / listing.page_size)) : 1),
    [listing],
  );

  // Which field carries an item's text is a property of its modality, not of the bank:
  // two modalities can name their primary differently, so every row resolves its own.
  const itemTypes: BankItemType[] = listing?.item_types ?? [];
  // WHETHER THE MODALITY COLUMN CARRIES INFORMATION. With one modality declared it never
  // did; with several it stops doing so the moment the filter above pins one, and then it
  // is the same two-line badge repeated down all forty rows — 135 px of width saying what
  // the filter already says. The column is about variation, so it is drawn only where
  // there is any.
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

  // Whether the bank may be written to is NOT read here and cannot be: `reviewing` is
  // `StageGate`'s own state and this component is the one that renders it, so the hooks that
  // answer only work below. Every control that writes therefore reads it for itself.

  // NOTHING IS SHOWN WHILE THE BANK IS BEING EXTRACTED (2026-09-01, explicit user request).
  // `BankLive` — «Ejercicios que van saliendo» — polled the file every three seconds and let
  // the items in one at a time under the progress bar; it is deleted, and what is left in
  // that state is the phase bar and the notice beside it. The sliding window itself lives on
  // in `TagLive`, which is a different job: tagging patches items that are ALREADY in the
  // bank, so its feed says what is being decided rather than what is appearing.
  const livePreview = tagging ? <TagLive run={tagRun} /> : null;

  return (
    <StageGate stage={stage} livePreview={livePreview}>
      <div className="space-y-4">
        <BankMeters
          listing={listing}
          coverage={coverage.data}
          offline={offline}
          submitting={submit.isPending}
          onRetag={(params) => submit.mutate({ kind: "tag", params })}
          onShowUntagged={() => {
            setUntagged(true);
            setPage(1);
          }}
        />


        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              aria-label={t("bank.search")}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
              placeholder={t("bank.search")}
              className="pl-8"
            />
          </div>
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
            {(listing?.sources ?? []).map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
          {/* THE DIFFICULTY IS A FILTER AND NOT AN ORDER (2026-09-01, explicit user
              request, reversing the sort asked for two days earlier). «Ordenar por
              dificultad» answered a question nobody has — the rungs are three, so ordering
              by them only groups the list — where «enséñame los avanzados» is the question
              somebody actually asks. It stands where the order select stood, and the order
              control went with it: the list is by id, which is extraction order.

              Offered only where a modality declares rungs, like the column and the sort
              before it: a filter with one option filters nothing. */}
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
          {/* LAST OF THE ROW (2026-09-01, explicit user request). It is the only one of the
              four that is not a property of an item but a state of the WORK — what still has
              to be tagged — and it is a toggle among selects, so it reads as the end of the
              row rather than as one more dropdown that lost its label. */}
          <Button
            variant={untagged === true ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setUntagged(untagged === true ? undefined : true);
              setPage(1);
            }}
          >
            <TriangleAlert />
            {t("bank.untagged")}
          </Button>
        </div>

        {bank.isError ? (
          <LoadError title={t("bank.unreadable")} error={bank.error} onRetry={bank.refetch} />
        ) : null}

        {listing ? (
          <div className="overflow-hidden rounded-lg border border-border">
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
                  <Correction>
                    <TH className="w-8">
                      <Checkbox
                        checked={pageSelected}
                        indeterminate={someSelected}
                        onCheckedChange={togglePage}
                        label={
                          pageSelected
                            ? t("bank.deselectPage")
                            : t("bank.selectPage")
                        }
                      />
                    </TH>
                  </Correction>
                  <TH>{primaryHeader}</TH>
                  {/* 15rem y no 10, y el número está medido: los nueve nombres de tipo de
                      las dos asignaturas de referencia miden entre 142 y 262 px dibujados
                      como insignia, y a 10rem se recortaban TODOS. A 15 caben ocho de los
                      nueve enteros y el recorte vuelve a ser la excepción — que es lo que
                      justifica resolverlo con puntos suspensivos y un `title`. Lo paga el
                      enunciado, que va recortado a dos líneas y tenía 766 px; `minWidth`
                      sube con ello, o en una ventana estrecha la columna del enunciado se
                      quedaría sin nada. */}
                  {manyTypes ? <TH className="w-60">{t("bank.column.modality")}</TH> : null}
                  <TH className="w-72">{t("bank.column.concepts")}</TH>
                  {difficultyField ? (
                    <TH className="w-28">{t("bank.column.difficulty")}</TH>
                  ) : null}
                  <TH className="w-20" />
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
                    difficulty={difficultyField ? difficultyFor(item) : null}
                    showDifficulty={Boolean(difficultyField)}
                    selected={selected.has(item.id)}
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

            {/* THE FOOT OF THE TABLE, and both things it says are about the table.
                The selection used to be a bar of its own BELOW the pagination, so a page
                could carry the filters at the top, a floating bar at the bottom and the
                page controls between them — three strips around one list. Where you are in
                the bank and what you have picked out of it belong on the same line, and
                the line belongs inside the card they describe.

                THE ONE AT THE TOP IS GONE (2026-09-01, explicit user request). Two pagers
                for a page of seven rows is one control drawn twice a screen apart: the
                whole list is in view, so the one at the end of it is the one under your
                eyes when you run out of rows. What went with it is the second copy of
                «N ejercicios · página M de P», which is the same reading in both places.

                What has NOT come back is a whole-bank «Etiquetar pendientes»: extracting
                and tagging are one job since the extractor tags each document as it comes
                out. The scoped retries are the strip above (what the verifier rejected, and
                the whole bank with a confirmation) and this one, which re-runs the tagger
                over items chosen by hand, whatever their state. */}
            {listing.items.length > 0 ? (
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border px-3 py-2.5 text-body">
                <Pager
                  page={listing.page}
                  pages={pages}
                  total={listing.total}
                  onPage={setPage}
                />

                <span className="flex-1" />

                <Correction>
                  <SelectionActions
                    selected={selected}
                    offline={offline}
                    submitting={submit.isPending}
                    onRetag={() => submit.mutate({ kind: "tag", params: { ids: [...selected] } })}
                    onClear={() => setSelected(new Set())}
                  />
                </Correction>
              </div>
            ) : null}
          </div>
        ) : (
          <Skeleton className="h-96" />
        )}
      </div>

      {editing && listing ? (
        <ItemDialog
          item={editing}
          fields={fieldsFor(editing)}
          primaryField={primaryFieldFor(editing)}
          concepts={concepts}
          onClose={() => setEditing(null)}
          onSaved={() => {
            invalidate();
            bank.refetch();
            coverage.refetch();
          }}
        />
      ) : null}
    </StageGate>
  );
}

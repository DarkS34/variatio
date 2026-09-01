import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Search,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { ConceptPicker } from "@/components/ConceptPicker";
import { LOCKED_HINT, StageGate, useStageLocked } from "@/components/StageGate";
import { BankLive } from "./BankLive";
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
import { TAGGING_METHOD_KEYS, truncate } from "@/lib/format";
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

function ItemEditor({
  item,
  fields,
  primaryField,
  concepts,
  onClose,
  onSaved,
}: {
  item: BankItem;
  fields: string[];
  primaryField: string;
  concepts: KgConcept[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useT();
  const locked = useStageLocked();
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
        locked ? (
          <Button variant="ghost" onClick={onClose}>
            {t("common.close")}
          </Button>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button onClick={submit} disabled={pending}>
              {pending ? <Spinner /> : null}
              {t("common.save")}
            </Button>
          </>
        )
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
                readOnly={locked}
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
              disabled={locked}
              maxHeight="14rem"
            />
          </div>

          {item._tagging ? (
            <div className="rounded-lg border border-border p-3">
              <p className="mb-2 text-small font-medium text-muted-foreground">
                {t("bank.taggingMethod", {
                  method: TAGGING_METHOD_KEYS[item._tagging.method]
                    ? t(TAGGING_METHOD_KEYS[item._tagging.method])
                    : item._tagging.method,
                })}
              </p>
              {item._tagging.candidates.length === 0 ? (
                <p className="text-small text-[var(--attention)]">
                  {t("bank.noCandidates")}
                </p>
              ) : (
                <ul className="space-y-1">
                  {item._tagging.candidates.map(([name, score]) => (
                    <li key={name} className="flex items-center gap-2 text-small">
                      <span className="w-12 shrink-0 nums text-muted-foreground">
                        {score.toFixed(3)}
                      </span>
                      <div className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full bg-primary"
                          style={{ width: `${Math.min(100, score * 100)}%` }}
                        />
                      </div>
                      <span className="min-w-0 truncate">{name}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
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
  const [open, setOpen] = useState(false);
  const untagged = !item.concepts || item.concepts.length === 0;
  const text = fieldText(item[primaryField]);
  // Extracted before the grammar was dropped from remote bank extraction: the statement
  // holds control characters where its accents used to be. Nothing here can repair it —
  // only a re-extraction can — but until this the row looked exactly like a sound one.
  const broken = hasBrokenText(item);

  return (
    <>
      {/* `group` is what lets the row's own actions appear on hover. They are two icons
          repeated on every one of forty rows, so at rest they are forty pieces of furniture
          that say the same thing; on the row you are pointing at they are the two things
          there are to do with it. `focus-within` is the other half and is not optional: a
          control that only exists under a mouse pointer does not exist for a keyboard. */}
      <TR
        selected={selected}
        className={cn(
          "group align-top",
          untagged && "bg-[color-mix(in_oklch,var(--attention)_8%,transparent)]",
        )}
      >
        <TD className="py-2 pl-3">
          <Checkbox
            checked={selected}
            onCheckedChange={onToggle}
            label={t("bank.selectItem", { id: item.id })}
            className="mt-1"
          />
        </TD>
        <TD className="min-w-0 py-2 pl-2 pr-3">
          {/* The id rides above the statement instead of holding a column of its own: it is
              how you name an item when talking about it, not something anybody scans down. */}
          <span className="font-mono text-micro tracking-normal text-muted-foreground">
            {item.id}
          </span>
          <button onClick={onEdit} className="block text-left text-body hover:underline">
            {truncate(text, 200)}
          </button>
          {open ? (
            <div className="mt-2 space-y-2">
              {secondaryFields.map((field) => {
                const value = item[field];
                if (isEmptyField(value)) return null;
                return isCodeField(field) ? (
                  <CodeBlock key={field} code={fieldText(value)} maxHeight="16rem" />
                ) : (
                  <div key={field} className="space-y-0.5">
                    <Label>{field}</Label>
                    <p className="whitespace-pre-wrap text-small text-muted-foreground">
                      {fieldText(value)}
                    </p>
                  </div>
                );
              })}
              {item._tagging ? (
                <div className="rounded-md border border-border p-2">
                  <p className="mb-1 text-small text-muted-foreground">
                    {TAGGING_METHOD_KEYS[item._tagging.method]
                      ? t(TAGGING_METHOD_KEYS[item._tagging.method])
                      : item._tagging.method}
                    {item._tagging.model ? ` · ${item._tagging.model}` : ""}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {item._tagging.candidates.map(([name, score]) => (
                      <span key={name} className="text-small">
                        <span className="nums text-muted-foreground">
                          {score.toFixed(3)}
                        </span>{" "}
                        {name}
                      </span>
                    ))}
                    {item._tagging.candidates.length === 0 ? (
                      <span className="text-small text-[var(--attention)]">
                        {t("tagging.no_candidates")}
                      </span>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </TD>
        {typeLabel ? (
          <TD className="py-2 pl-2">
            <Badge variant="outline">{typeLabel}</Badge>
          </TD>
        ) : null}
        <TD className="py-2 pr-3">
          <div className="flex max-w-64 flex-wrap gap-1">
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
              item.concepts!.map((concept) => (
                <Badge key={concept} variant={concept === item.primary_concept ? "default" : "secondary"}>
                  {concept}
                </Badge>
              ))
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
          <div
            className={cn(
              "inline-flex transition-opacity group-hover:opacity-100 group-focus-within:opacity-100",
              // The expanded row keeps its chevron visible: the control that opened it is
              // the control that closes it, and hiding it would leave the detail with no
              // visible way back.
              open ? "opacity-100" : "opacity-0",
            )}
          >
            <Button variant="ghost" size="icon-sm" onClick={() => setOpen((value) => !value)} aria-label={t("bank.detail")}>
              <ChevronRight className={cn("transition-transform", open && "rotate-90")} />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onDelete}
              disabled={locked}
              title={locked ? t(LOCKED_HINT) : t("bank.delete")}
              aria-label={t("bank.delete")}
            >
              <Trash2 />
            </Button>
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

/** What the listing may be ordered by. `recent` is the live view's and is never offered
 *  here; `difficulty` only appears when the profile declares one. */
type BankOrder = "id" | "difficulty" | "suspicion";

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
  locked,
  offline,
  submitting,
  onRetag,
  onShowUntagged,
}: {
  listing: BankListing | undefined;
  coverage: Coverage | undefined;
  locked: boolean;
  offline: string | null;
  submitting: boolean;
  onRetag: (params: Record<string, unknown>) => void;
  onShowUntagged: () => void;
}) {
  const { t, plural } = useT();
  const confirm = useConfirm();

  if (!listing) return <Skeleton className="h-24" />;

  const { items, tagged, untagged } = listing.totals;
  const busy = locked || submitting || Boolean(offline);
  const why = locked ? t(LOCKED_HINT) : offline;

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
    </Card>
  );
}

export function BankScreen({ stage }: { stage: StageState | undefined }) {
  const { t, plural } = useT();
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
  const [order, setOrder] = useState<BankOrder>("id");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<BankItem | null>(null);

  const workspace = useActiveWorkspace();
  useEffect(() => {
    setItemType("");
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
  const params = { q: query, item_type: itemType, source, untagged, order, page, page_size: PAGE_SIZE };
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

  // Extracting and re-extracting are the same job with opposite consequences: with an empty
  // bank it is the missing step, and with items inside it deletes everything tagged and
  // corrected. The button says so and `BuildButton` asks for confirmation.
  const hasItems = (listing?.totals.items ?? 0) > 0;
  const locked = stage?.status === "approved";

  return (
    <StageGate
      stage={stage}
      livePreview={tagging ? <TagLive run={tagRun} /> : <BankLive />}
      buildLabels={{
        // «Extraer» the first time, because that is what the bank does and nothing else on
        // the chain does it. «Reconstruir» after, which is the DEFAULT and the same word the
        // other three steps use: it is the button you press again and again, so a name of
        // its own here only made the bank the odd one out.
        create: t("bank.extract"),
        redo: t("build.redoDefault"),
        confirmRedo: hasItems
          ? plural("bank.confirmReextract", listing?.totals.items ?? 0)
          : undefined,
      }}
    >
      <div className="space-y-4">
        <BankMeters
          listing={listing}
          coverage={coverage.data}
          locked={locked}
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
          <Select
            aria-label={t("bank.orderBy")}
            value={order}
            onChange={(event) => setOrder(event.target.value as BankOrder)}
            className="max-w-56"
          >
            <option value="id">{t("bank.orderById")}</option>
            {/* Offered only where it would order anything: with no difficulty declared the
                server falls back to the id order, and a control that silently does nothing
                is worse than one that is not there. */}
            {difficultyField ? (
              <option value="difficulty">{t("bank.orderByDifficulty")}</option>
            ) : null}
            <option value="suspicion">{t("bank.orderBySuspicion")}</option>
          </Select>

          {listing && listing.items.length > 0 ? (
            <div className="ml-auto flex items-center gap-3">
              <Pager
                page={listing.page}
                pages={pages}
                total={listing.total}
                onPage={setPage}
              />
            </div>
          ) : null}
        </div>

        {bank.isError ? (
          <LoadError title={t("bank.unreadable")} error={bank.error} onRetry={bank.refetch} />
        ) : null}

        {listing ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <Table minWidth="44rem">
              <THead>
                <TR>
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
                  <TH>{primaryHeader}</TH>
                  {manyTypes ? <TH className="w-40">{t("bank.column.modality")}</TH> : null}
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

                {selected.size > 0 ? (
                  <>
                    <span className="text-small font-medium">
                      {plural("bank.selectedCount", selected.size)}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={locked || submit.isPending || Boolean(offline)}
                      title={
                        locked
                          ? t(LOCKED_HINT)
                          : (offline ?? plural("bank.retagSelectedHint", selected.size))
                      }
                      onClick={() => submit.mutate({ kind: "tag", params: { ids: [...selected] } })}
                    >
                      {submit.isPending ? <Spinner /> : <RefreshCw />}
                      {t("bank.retagSelected")}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
                      {t("bank.deselect")}
                    </Button>
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : (
          <Skeleton className="h-96" />
        )}
      </div>

      {editing && listing ? (
        <ItemEditor
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

import { ArrowRight, ChevronRight, Library, MessageCircle, MessagesSquare, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { fromGeneration, stashDraft } from "@/consumers/generation/draft";
import { ItemFields } from "@/consumers/generation/ResultCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConceptBadge } from "@/components/ui/concept-chip";
import { SearchInput, Select } from "@/components/ui/input";
import { LoadError, Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { DOOR_TONE } from "@/components/ui/tone";
import { fieldText } from "@/lib/fields";
import { dayMonth, truncate } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { difficultyFieldOf, itemTypeOf } from "@/lib/profile";
import { useRouter } from "@/lib/router";
import { readableValue } from "@/lib/text";
import { stashChatDraft } from "@/lib/chatDraft";
import { stashTutorDraft } from "@/lib/tutorDraft";
import type { BankItemType, ExemplarsProfile, GenerationRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useFeatures } from "@/state/auth";
import { useActiveWorkspace, useGenerations, useProfile } from "@/state/queries";

import { typeSummaries } from "./exercise";

import { Pager } from "./Pager";
import { PromoteDialog } from "./Promote";

/** Which generated exercises: out of the bank (where the work is), in it, or all. */
type Scope = "out" | "in" | "all";

/** Rows a page, as the bank's table. */
const PAGE_SIZE = 7;

/** How many concepts a row draws before the rest are counted. */
const MAX_ROW_CONCEPTS = 3;

/**
 * «Generados», beside «Banco» on the bank's page: the exercises THIS teacher generated in the
 * subject, to pass into the bank the ones worth learning from (the user's request,
 * 2026-10-14). Nobody else's: a generated exercise is its author's alone.
 *
 * A table like the bank's, opening on the ones still out of it, since that is where the work
 * is. Each row carries its one gesture in sight, «Pasar al banco», or says it is in the bank
 * with a way to its row there.
 *
 * `reading` is a student's «Mis ejercicios generados» (2026-10-14): all of them, with no
 * question about the bank, and the gestures that take one elsewhere — «Generar más como
 * este» and «Trabajar con el tutor», each where its function is open — in place of passing
 * it in. The types come from the profile, since a student reads no bank listing.
 */
export function GeneratedList({
  itemTypes: given,
  onToBank,
  reading = false,
}: {
  itemTypes: BankItemType[];
  /** Shows a bank exercise in the «Banco» tab, by its id. */
  onToBank?: (id: string) => void;
  reading?: boolean;
}) {
  const { t } = useT();
  const workspace = useActiveWorkspace();
  const profile = useProfile().data?.profile ?? null;
  const itemTypes = useMemo(() => (reading ? typeSummaries(profile) : given), [reading, profile, given]);
  const features = useFeatures();
  const { navigate } = useRouter();
  const [scope, setScope] = useState<Scope>(reading ? "all" : "out");
  const [query, setQuery] = useState("");
  const [itemType, setItemType] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [page, setPage] = useState(1);
  const [promoting, setPromoting] = useState<GenerationRow | null>(null);

  useEffect(() => {
    setItemType("");
    setDifficulty("");
    setPage(1);
  }, [workspace]);

  const listing = useGenerations({
    q: query || undefined,
    item_type: itemType || undefined,
    difficulty: difficulty || undefined,
    bank: scope === "all" ? undefined : scope,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });
  const rows = listing.data?.generations ?? [];
  const total = listing.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const manyTypes = itemTypes.length > 1 && !itemType;
  // The statement's column is headed as the bank's is: by the field each type calls it.
  const primaryHeader = [...new Set(itemTypes.map((type) => type.primary_field))].join(" / ");
  const rungs = useMemo(
    () => [...new Set(itemTypes.flatMap((type) => type.difficulty_levels))],
    [itemTypes],
  );
  const restart = <T,>(set: (value: T) => void) => (value: T) => {
    set(value);
    setPage(1);
  };

  // A student's two gestures, each where its function is open to them.
  const again =
    reading && features.generate
      ? (row: GenerationRow) => {
          stashDraft(fromGeneration(row));
          navigate("/generate");
        }
      : null;
  const withChat =
    reading && features.chat
      ? (row: GenerationRow) => {
          const spec = profile ? itemTypeOf(profile, { item_type: row.item_type }) : null;
          const statement = spec ? fieldText(row.item[spec.primary_field]) : "";
          stashChatDraft({ message: t("chat.fromExercise.message", { statement }), generationId: row.id, bankId: null });
          navigate("/chat");
        }
      : null;
  const withTutor =
    reading && features.tutor
      ? (row: GenerationRow) => {
          const spec = profile ? itemTypeOf(profile, { item_type: row.item_type }) : null;
          const statement = spec ? fieldText(row.item[spec.primary_field]) : "";
          stashTutorDraft({ message: t("tutor.fromExercise.message", { statement }), generationId: row.id });
          navigate("/tutor");
        }
      : null;

  return (
    <div className="space-y-4">
      <p className="text-body text-muted-foreground">
        {t(reading ? "bank.reading.mine.lead" : "bank.generated.lead")}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {reading ? null : (
          <Tabs
            items={[
              { value: "out", label: t("bank.generated.out") },
              { value: "in", label: t("bank.generated.in") },
              { value: "all", label: t("bank.generated.all") },
            ]}
            value={scope}
            onChange={(next) => restart(setScope)(next as Scope)}
          />
        )}
        <SearchInput
          className="min-w-56 flex-1"
          aria-label={t("bank.search")}
          value={query}
          onChange={(event) => restart(setQuery)(event.target.value)}
          placeholder={t("bank.search")}
        />
        {itemTypes.length > 1 ? (
          <Select
            aria-label={t("bank.filterByModality")}
            value={itemType}
            onChange={(event) => restart(setItemType)(event.target.value)}
            className="max-w-56"
          >
            <option value="">{t("bank.allModalities")}</option>
            {itemTypes.map((type) => (
              <option key={type.key} value={type.key}>
                {type.label || type.key}
              </option>
            ))}
          </Select>
        ) : null}
        {rungs.length > 0 ? (
          <Select
            aria-label={t("bank.filterByDifficulty")}
            value={difficulty}
            onChange={(event) => restart(setDifficulty)(event.target.value)}
            className="max-w-48"
          >
            <option value="">{t("bank.allDifficulties")}</option>
            {rungs.map((rung) => (
              <option key={rung} value={rung}>
                {readableValue(rung)}
              </option>
            ))}
          </Select>
        ) : null}
      </div>

      {listing.isError ? (
        <LoadError title={t("bank.generated.unreadable")} error={listing.error} onRetry={() => listing.refetch()} />
      ) : listing.isLoading ? (
        <Skeleton className="h-96" />
      ) : (
        <div className="surface p-5">
          <Table minWidth="48rem" className="table-fixed">
            <THead>
              <TR>
                <TH>{primaryHeader}</TH>
                {manyTypes ? <TH className="w-60">{t("bank.column.modality")}</TH> : null}
                <TH className="w-72">{t("bank.column.concepts")}</TH>
                {rungs.length > 0 ? <TH className="w-28">{t("bank.column.difficulty")}</TH> : null}
                <TH className={reading ? "w-32" : "w-52"} />
              </TR>
            </THead>
            <TBody>
              {rows.map((row) => (
                <GeneratedRow
                  key={row.id}
                  row={row}
                  profile={profile}
                  manyTypes={manyTypes}
                  showDifficulty={rungs.length > 0}
                  onPromote={reading ? undefined : () => setPromoting(row)}
                  onToBank={onToBank}
                  onAgain={again ? () => again(row) : undefined}
                  onTutor={withTutor ? () => withTutor(row) : undefined}
                  onChat={withChat ? () => withChat(row) : undefined}
                />
              ))}
            </TBody>
          </Table>
          {rows.length === 0 ? (
            <p className="p-8 text-center text-body text-muted-foreground">
              {total === 0 && scope === "all" && !query && !itemType && !difficulty
                ? t("bank.generated.none")
                : t("bank.noneWithFilters")}
            </p>
          ) : (
            <div className="mt-3 flex min-h-7 flex-wrap items-center gap-x-3 gap-y-2 border-t border-border pt-3 text-body">
              <Pager page={page} pages={pages} total={total} onPage={setPage} />
            </div>
          )}
        </div>
      )}

      {promoting ? (
        <PromoteDialog
          generation={promoting}
          onClose={() => {
            setPromoting(null);
            listing.refetch();
          }}
        />
      ) : null}
    </div>
  );
}

/** One generated exercise: its statement, which unfolds whole, and its way into the bank —
 *  or, read by a student, its ways to a commission like it and to the tutor. */
function GeneratedRow({
  row,
  profile,
  manyTypes,
  showDifficulty,
  onPromote,
  onToBank,
  onAgain,
  onTutor,
  onChat,
}: {
  row: GenerationRow;
  profile: ExemplarsProfile | null;
  manyTypes: boolean;
  showDifficulty: boolean;
  onPromote?: () => void;
  onToBank?: (id: string) => void;
  onAgain?: () => void;
  onTutor?: () => void;
  onChat?: () => void;
}) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const spec = profile ? itemTypeOf(profile, { item_type: row.item_type }) : null;
  const statement = spec ? fieldText(row.item[spec.primary_field]) : "";
  const concepts = row.targets?.length ? row.targets : row.concepts;
  const levelField = difficultyFieldOf(spec);
  const level = levelField ? row.item[levelField] : undefined;
  const date = dayMonth(new Date(row.created_at * 1000).toISOString());

  return (
    <TR className={cn("group align-top [&>td]:align-top", !open && "h-[5.5rem]")}>
      <TD className="min-w-0 py-2 pl-2 pr-3">
        <span className="flex h-[1.3125rem] items-center text-small text-muted-foreground">{date}</span>
        <button
          onClick={() => setOpen((value) => !value)}
          className={cn("text-left text-body whitespace-pre-wrap hover:underline", open ? "block" : "line-clamp-2")}
          aria-expanded={open}
        >
          {open ? statement : truncate(statement, 200)}
        </button>
        {open ? (
          <div className="well mt-3 space-y-3 p-4">
            <ItemFields item={row.item} spec={spec} />
          </div>
        ) : null}
      </TD>
      {manyTypes ? (
        <TD className="py-2 pl-2">
          <Badge variant="outline" className="max-w-full" title={spec?.label || row.item_type}>
            <span className="truncate">{spec?.label || row.item_type}</span>
          </Badge>
        </TD>
      ) : null}
      <TD className="py-2 pr-3">
        <div className="flex max-h-[3.125rem] max-w-64 flex-wrap gap-1 overflow-hidden">
          {concepts.slice(0, MAX_ROW_CONCEPTS).map((concept, index) => (
            <ConceptBadge key={concept} primary={index === 0}>
              {concept}
            </ConceptBadge>
          ))}
          {concepts.length > MAX_ROW_CONCEPTS ? (
            <Badge variant="outline" title={concepts.slice(MAX_ROW_CONCEPTS).join(", ")}>
              +{concepts.length - MAX_ROW_CONCEPTS}
            </Badge>
          ) : null}
        </div>
      </TD>
      {showDifficulty ? (
        <TD className="py-2 pr-3">
          {typeof level === "string" && level ? (
            <Badge variant="secondary">{level}</Badge>
          ) : (
            <span className="text-small text-muted-foreground">{t("bank.noDifficulty")}</span>
          )}
        </TD>
      ) : null}
      <TD className="whitespace-nowrap py-2 pr-3 text-right">
        <div className="inline-flex items-center gap-1">
          {row.in_bank && onToBank ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-7"
              title={t("bank.generated.toBank", { id: row.in_bank })}
              onClick={() => onToBank(row.in_bank!)}
            >
              <Library />
              {t("bank.generated.inBank", { id: row.in_bank })}
            </Button>
          ) : row.promotable && onPromote ? (
            <Button variant="outline" size="sm" className="h-7" onClick={onPromote}>
              {t("bank.promote")}
              <ArrowRight />
            </Button>
          ) : null}
          {onAgain ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onAgain}
              title={t("generations.againHint")}
              aria-label={t("generations.moreLikeThis")}
            >
              <Sparkles />
            </Button>
          ) : null}
          {onTutor ? (
            <Button
              variant="ghost"
              size="icon-sm"
              className={cn(DOOR_TONE.tutor.face, DOOR_TONE.tutor.hover)}
              onClick={onTutor}
              title={t("tutor.fromExercise.hint")}
              aria-label={t("tutor.fromExercise")}
            >
              <MessagesSquare />
            </Button>
          ) : null}
          {onChat ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onChat}
              title={t("chat.fromExercise.hint")}
              aria-label={t("chat.fromExercise")}
            >
              <MessageCircle />
            </Button>
          ) : null}
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
        </div>
      </TD>
    </TR>
  );
}

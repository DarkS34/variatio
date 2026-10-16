import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronRight, MessageCircle, MessagesSquare, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { stashDraft } from "@/consumers/generation/draft";
import { useExerciseTotal } from "@/consumers/generation/GenerationsPanel";
import { ItemFields } from "@/consumers/generation/ResultCard";
import { ReadingScope } from "@/components/StageGate";
import { DOOR_TONE } from "@/components/ui/tone";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConceptBadge } from "@/components/ui/concept-chip";
import { SearchInput, Select } from "@/components/ui/input";
import { LoadError } from "@/components/ui/load-error";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { TabCount, Tabs } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { fieldText } from "@/lib/fields";
import { truncate } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { itemTypeOf } from "@/lib/profile";
import { useRouter } from "@/lib/router";
import { readableValue } from "@/lib/text";
import { stashChatDraft } from "@/lib/chatDraft";
import { stashTutorDraft } from "@/lib/tutorDraft";
import type { BankItemType, ExemplarsProfile, ReadableExercise } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useFeatures } from "@/state/auth";
import { useActiveWorkspace, useProfile } from "@/state/queries";

import { commissionLike } from "./exercise";
import { GeneratedList } from "./GeneratedList";
import { Pager } from "./Pager";

type Tab = "bank" | "mine";

/** Rows a page, as the teacher's table. */
const PAGE_SIZE = 7;

/** How many concepts a row draws before the rest are counted, as the teacher's table. */
const MAX_ROW_CONCEPTS = 3;

/**
 * STEP 3 AS A STUDENT READS IT: «Banco de ejercicios» (the user's decision, 2026-10-14).
 *
 * The page a teacher works on, with nothing that writes. Two tabs, as a teacher's: «Banco»,
 * the exercises the subject's teachers showed this student, cut to what they showed
 * (`GET /api/exercises`), and «Mis ejercicios generados», their own. It opens on the bank
 * when it holds something, else on their own exercises.
 *
 * A row takes its exercise elsewhere, each gesture only where that function is open to the
 * student: «Generar más como este» fills a commission with its type, its level and its
 * concepts; «Trabajar con el tutor» opens a conversation on it. What travels is what the
 * student reads — the statement, never a field the teacher hid.
 */
export function BankReader() {
  const { t } = useT();
  const workspace = useActiveWorkspace();
  const [tab, setTab] = useState<Tab | null>(null);
  // Another subject is another bank: the tab chosen in the last one does not carry over.
  useEffect(() => setTab(null), [workspace]);
  const summary = useQuery({
    queryKey: ["exercises", workspace, "summary"],
    queryFn: () => api.exercises({ page_size: 1 }),
  });
  const mine = useExerciseTotal(workspace);
  const shown = summary.data?.total;
  const opened: Tab = tab ?? (shown === 0 ? "mine" : "bank");

  return (
    <div className="space-y-7">
      <header className="min-w-0 space-y-1.5">
        <h1 className="font-display font-expanded text-title">{t("nav.step.bank")}</h1>
        <p className="max-w-[74ch] text-body text-muted-foreground">{t("bank.reading.lead")}</p>
      </header>
      <ReadingScope>
        {summary.isError ? (
          <LoadError title={t("bank.reading.unreadable")} error={summary.error} onRetry={() => summary.refetch()} />
        ) : summary.isLoading ? (
          <Skeleton className="h-96" />
        ) : (
          <div className="space-y-4">
            <Tabs
              items={[
                { value: "bank", label: t("bank.tab.bank"), badge: <TabCount n={shown} /> },
                { value: "mine", label: t("bank.reading.tab.mine"), badge: <TabCount n={mine} /> },
              ]}
              value={opened}
              onChange={(next) => setTab(next as Tab)}
            />
            {opened === "bank" ? <ExerciseTable /> : <GeneratedList itemTypes={[]} reading />}
          </div>
        )}
      </ReadingScope>
    </div>
  );
}

/** «Banco», read: the exercises shown, a page at a time, with the filters a reader asks. */
function ExerciseTable() {
  const { t } = useT();
  const workspace = useActiveWorkspace();
  const profile = useProfile().data?.profile ?? null;
  const take = useTakeElsewhere(profile);
  const [query, setQuery] = useState("");
  const [itemType, setItemType] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [concept, setConcept] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setItemType("");
    setDifficulty("");
    setConcept("");
    setPage(1);
  }, [workspace]);

  const params = {
    q: query || undefined,
    item_type: itemType || undefined,
    difficulty: difficulty || undefined,
    concept: concept || undefined,
    page,
    page_size: PAGE_SIZE,
  };
  const listing = useQuery({
    queryKey: ["exercises", workspace, params],
    queryFn: () => api.exercises(params),
    placeholderData: keepPreviousData,
  });
  const data = listing.data;
  const itemTypes = data?.item_types ?? [];
  const manyTypes = itemTypes.length > 1 && !itemType;
  const rungs = useMemo(
    () => (data?.difficulties ?? []).filter((rung) => rung.count > 0),
    [data?.difficulties],
  );
  // The concepts the exercises read carry, under their units, as the syllabus orders them.
  const units = useMemo(() => {
    const grouped = new Map<string, string[]>();
    for (const entry of data?.concepts ?? []) {
      const unit = entry.unit ?? "";
      grouped.set(unit, [...(grouped.get(unit) ?? []), entry.name]);
    }
    return [...grouped.entries()];
  }, [data?.concepts]);
  const filtered = Boolean(query || itemType || difficulty || concept);
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));
  const typeOf = (item: ReadableExercise) =>
    itemTypes.find((type) => type.key === item.item_type) ?? itemTypes[0] ?? null;
  // The statement's column is headed as the teacher's is: by the field each type calls it.
  const primaryHeader = [...new Set(itemTypes.map((type) => type.primary_field))].join(" / ");
  const restart = <T,>(set: (value: T) => void) => (value: T) => {
    set(value);
    setPage(1);
  };

  if (listing.isError) {
    return <LoadError title={t("bank.reading.unreadable")} error={listing.error} onRetry={() => listing.refetch()} />;
  }
  if (!data) return <Skeleton className="h-96" />;
  if (data.total === 0 && !filtered) {
    return (
      <p className="surface p-8 text-center text-body text-muted-foreground">{t("bank.reading.none")}</p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <SearchInput
          className="min-w-56 flex-1"
          aria-label={t("bank.reading.search")}
          value={query}
          onChange={(event) => restart(setQuery)(event.target.value)}
          placeholder={t("bank.reading.search")}
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
        {rungs.length > 1 ? (
          <Select
            aria-label={t("bank.filterByDifficulty")}
            value={difficulty}
            onChange={(event) => restart(setDifficulty)(event.target.value)}
            className="max-w-48"
          >
            <option value="">{t("bank.allDifficulties")}</option>
            {rungs.map((rung) => (
              <option key={rung.value} value={rung.value}>
                {readableValue(rung.value)}
              </option>
            ))}
          </Select>
        ) : null}
        {units.length > 0 ? (
          <Select
            aria-label={t("bank.reading.filterByConcept")}
            value={concept}
            onChange={(event) => restart(setConcept)(event.target.value)}
            className="max-w-64"
          >
            <option value="">{t("bank.reading.allConcepts")}</option>
            {units.map(([unit, names]) =>
              unit ? (
                <optgroup key={unit} label={unit}>
                  {names.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </optgroup>
              ) : (
                names.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))
              ),
            )}
          </Select>
        ) : null}
      </div>

      <div className="surface p-5">
        <Table minWidth="48rem" className="table-fixed">
          <THead>
            <TR>
              <TH>{primaryHeader}</TH>
              {manyTypes ? <TH className="w-60">{t("bank.column.modality")}</TH> : null}
              <TH className="w-72">{t("bank.column.concepts")}</TH>
              {rungs.length > 0 ? <TH className="w-28">{t("bank.column.difficulty")}</TH> : null}
              <TH className="w-32" />
            </TR>
          </THead>
          <TBody>
            {data.items.map((item) => (
              <ExerciseRow
                key={item.id}
                item={item}
                type={typeOf(item)}
                profile={profile}
                manyTypes={manyTypes}
                showDifficulty={rungs.length > 0}
                onAgain={take.again ? () => take.again!(item, typeOf(item)) : undefined}
                onTutor={take.tutor ? () => take.tutor!(item, typeOf(item)) : undefined}
                onChat={take.chat ? () => take.chat!(item, typeOf(item)) : undefined}
              />
            ))}
          </TBody>
        </Table>
        {data.items.length === 0 ? (
          <p className="p-8 text-center text-body text-muted-foreground">{t("bank.noneWithFilters")}</p>
        ) : (
          <div className="mt-3 flex min-h-7 flex-wrap items-center gap-x-3 gap-y-2 border-t border-border pt-3 text-body">
            <Pager page={data.page} pages={pages} total={data.total} onPage={setPage} />
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * The ways an exercise read leaves the page, each only where its function is open: a
 * commission like it, or a conversation with the tutor or the free chat on it.
 */
export function useTakeElsewhere(profile: ExemplarsProfile | null) {
  const { t } = useT();
  const { navigate } = useRouter();
  const features = useFeatures();
  const again = (item: ReadableExercise, type: BankItemType | null) => {
    stashDraft(commissionLike(item, type));
    navigate("/generate");
  };
  const statementOf = (item: ReadableExercise, type: BankItemType | null) => {
    const spec = profile ? itemTypeOf(profile, { item_type: item.item_type }) : null;
    return fieldText(item[spec?.primary_field ?? type?.primary_field ?? ""]);
  };
  const tutor = (item: ReadableExercise, type: BankItemType | null) => {
    stashTutorDraft({
      message: t("tutor.fromExercise.message", { statement: statementOf(item, type) }),
      generationId: null,
      bankId: item.id,
    });
    navigate("/tutor");
  };
  // Only what the student reads travels: the statement here, and on the server the fields
  // shown, never one hidden from them.
  const chat = (item: ReadableExercise, type: BankItemType | null) => {
    stashChatDraft({
      message: t("chat.fromExercise.message", { statement: statementOf(item, type) }),
      generationId: null,
      bankId: item.id,
    });
    navigate("/chat");
  };
  return {
    again: features.generate ? again : null,
    tutor: features.tutor ? tutor : null,
    chat: features.chat ? chat : null,
  };
}

/** One exercise read: its statement, which unfolds into what else was shown, and its gestures. */
function ExerciseRow({
  item,
  type,
  profile,
  manyTypes,
  showDifficulty,
  onAgain,
  onTutor,
  onChat,
}: {
  item: ReadableExercise;
  type: BankItemType | null;
  profile: ExemplarsProfile | null;
  manyTypes: boolean;
  showDifficulty: boolean;
  onAgain?: () => void;
  onTutor?: () => void;
  onChat?: () => void;
}) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const spec = profile ? itemTypeOf(profile, { item_type: item.item_type }) : null;
  const primaryField = spec?.primary_field ?? type?.primary_field ?? "";
  const statement = fieldText(item[primaryField]);
  const levelField = type?.difficulty_field ?? null;
  const level = levelField ? item[levelField] : undefined;
  // The level has a column of its own; what unfolds is the rest of what was shown.
  const fields = useMemo(() => {
    const kept: Record<string, unknown> = {};
    for (const name of item.shown) if (name !== levelField) kept[name] = item[name];
    return kept;
  }, [item, levelField]);
  const ordered = [...new Set([...(item.primary_concept ? [item.primary_concept] : []), ...item.concepts])];
  const shownConcepts = ordered.slice(0, MAX_ROW_CONCEPTS);
  const restConcepts = ordered.slice(MAX_ROW_CONCEPTS);

  return (
    <TR className={cn("group align-top [&>td]:align-top", !open && "h-[5.5rem]")}>
      <TD className="min-w-0 py-2 pl-2 pr-3">
        {/* Folded, the statement clamped; open, everything shown of it, formatted as the
            exercise is everywhere else (`ItemFields`), the statement first. */}
        {open ? (
          <div className="space-y-3">
            <ItemFields item={fields} spec={spec} />
          </div>
        ) : (
          <button
            onClick={() => setOpen(true)}
            className="line-clamp-3 text-left text-body whitespace-pre-wrap hover:underline"
            aria-expanded={false}
          >
            {truncate(statement, 260)}
          </button>
        )}
      </TD>
      {manyTypes ? (
        <TD className="py-2 pl-2">
          <Badge variant="outline" className="max-w-full" title={type?.label || item.item_type}>
            <span className="truncate">{type?.label || item.item_type}</span>
          </Badge>
        </TD>
      ) : null}
      <TD className="py-2 pr-3">
        <div className="flex max-h-[3.125rem] max-w-64 flex-wrap gap-1 overflow-hidden">
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
        {/* The row's gestures are the reason the list is read, so they stay in sight. */}
        <div className="inline-flex items-center gap-0.5">
          {onAgain ? (
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onAgain}
              title={t("bank.reading.againHint")}
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

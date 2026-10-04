import { Ban, BookOpen, ChevronRight, Eye, Mail, Pencil, Plus, RefreshCw, Sparkles, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConceptChip } from "@/components/ui/concept-chip";
import { useConfirm } from "@/components/ui/confirm";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Alert, EmptyState, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { SectionHeader, Sections, type SectionEntry } from "@/features/admin/Sections";
import { when } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { changes } from "./criteria";
import { useBuildCriteria, useSaveCriteria, useTutorCriteria } from "./queries";
import type { CriteriaDocument, Criterion, ForbiddenTerm, Strength } from "./types";

/**
 * THE SUBJECT'S CRITERIA: BUILT BY THE SYSTEM, CORRECTED BY A TEACHER, NEVER BY A STUDENT.
 *
 * The same two moments as every stage of the construction: a review that only reads, and a
 * correction opened on purpose («Quiero corregir algo») with a bar that saves. The review is
 * kept short on purpose — the first draft, drawn with every concept and every source under
 * every criterion, was a wall nobody read — so it shows the sentences alone, the units
 * folded, and leaves concepts and sources to the correction. The method's own rules are not
 * listed: they live in the reply prompt, and the header says in prose what the tutor does in
 * every subject. A rebuild replaces a correction, which is why it asks first; the correction
 * is not lost, it goes to the history.
 *
 * The correction is the administrator's panel's layout (`Sections`): the list of the parts
 * beside the part open. Stacked down one page — the subject's criteria, every unit's, the
 * terms, the administrative reply — the parts could not be told from one another, and the
 * terms sat under sixty boxes.
 */
export function CriteriaPanel({ ready }: { ready: boolean }) {
  const { t } = useT();
  const query = useTutorCriteria(true);
  const build = useBuildCriteria();
  const save = useSaveCriteria();
  const confirm = useConfirm();
  const toast = useToast();
  const [draft, setDraft] = useState<CriteriaDocument | null>(null);

  const data = query.data;

  if (query.isLoading) return <Skeleton className="h-96" />;
  if (!data) {
    return <LoadError title={t("tutor.criteria.unreadable")} error={query.error} onRetry={query.refetch} />;
  }

  const working = Boolean(data.job) || build.isPending;
  const rebuild = async () => {
    if (data.origin === "curated") {
      const ok = await confirm({
        title: t("tutor.criteria.rebuild"),
        body: t("tutor.criteria.rebuildConfirm"),
        confirmLabel: t("tutor.criteria.rebuild"),
      });
      if (!ok) return;
    }
    setDraft(null);
    build.mutate();
  };

  const header = (
    <Card>
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>{t("tutor.criteria.title")}</CardTitle>
          {data.origin !== "missing" ? (
            <Badge variant={data.origin === "curated" ? "settled" : "attention"}>
              {t(data.origin === "curated" ? "tutor.criteria.origin.curated" : "tutor.criteria.origin.draft")}
            </Badge>
          ) : null}
        </div>
        <CardDescription>{t("tutor.criteria.body")}</CardDescription>
        {data.criteria.built?.at ? (
          <p className="text-small text-muted-foreground">
            {t("tutor.criteria.builtBy", {
              date: when(data.criteria.built.at),
              model: String(data.criteria.built.model ?? "—"),
            })}
          </p>
        ) : null}
      </CardHeader>
    </Card>
  );

  if (working) {
    return (
      <div className="space-y-4">
        {header}
        <Alert
          tone="info"
          title={data.job?.status === "queued" ? t("tutor.criteria.queued") : t("tutor.criteria.building")}
          action={<Spinner className="size-4" />}
        />
      </div>
    );
  }

  if (data.origin === "missing") {
    return (
      <div className="space-y-4">
        {header}
        {build.error ? (
          <Alert tone="danger" title={t("tutor.criteria.buildFailed")}>
            <p>{build.error.message}</p>
          </Alert>
        ) : null}
        <EmptyState
          icon={<Sparkles />}
          title={t("tutor.criteria.missing")}
          action={
            <Button variant="attention" size="xl" disabled={!ready} onClick={() => void rebuild()}>
              <Sparkles />
              {t("tutor.criteria.build")}
            </Button>
          }
        >
          {t("tutor.criteria.missing.body")}
        </EmptyState>
      </div>
    );
  }

  const shown = data.criteria;
  const warnings =
    data.warnings.length > 0 ? (
      <Alert tone="attention" title={t("tutor.criteria.warnings")}>
        <ul className="list-disc pl-5">
          {data.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      </Alert>
    ) : null;

  if (draft) {
    return (
      <div className="space-y-7">
        {header}
        {warnings}
        <Correction
          saved={data.criteria}
          draft={draft}
          units={data.units}
          error={save.error?.message}
          saving={save.isPending}
          onChange={setDraft}
          onStop={() => setDraft(null)}
          onSave={() =>
            save.mutate(draft, {
              onSuccess: (saved) => {
                setDraft(null);
                toast({
                  title: t("tutor.criteria.saved"),
                  description: saved.warnings.length ? saved.warnings.join(" ") : undefined,
                  tone: "settled",
                });
              },
            })
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {header}

      {warnings}

      <div className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={() => setDraft(structuredClone(data.criteria))}>
          {t("tutor.criteria.correct")}
        </Button>
        <Button variant="ghost" disabled={!ready} onClick={() => void rebuild()}>
          <RefreshCw />
          {t("tutor.criteria.rebuild")}
        </Button>
      </div>

      <Review
        general={shown.general}
        units={data.units.map((unit) => ({ name: unit.name, criteria: shown.units[unit.name] ?? [] }))}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t("tutor.criteria.terms")}</CardTitle>
          <CardDescription>{t("tutor.criteria.terms.body")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {shown.forbidden_terms.length === 0 ? (
            <p className="text-small text-muted-foreground">{t("tutor.criteria.none")}</p>
          ) : null}
          {shown.forbidden_terms.map((term, index) => (
            <p key={index}>
              <code className="font-mono">{term.term}</code>
              {term.reason ? <span className="text-muted-foreground"> — {term.reason}</span> : null}
            </p>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("tutor.criteria.admin")}</CardTitle>
          <CardDescription>{t("tutor.criteria.admin.body")}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="whitespace-pre-wrap">{shown.administrative_reply}</p>
        </CardContent>
      </Card>
    </div>
  );
}

/** The criteria as a teacher reviews them: the sentences, the subject's open, each unit folded. */
function Review({
  general,
  units,
}: {
  general: Criterion[];
  units: { name: string; criteria: Criterion[] }[];
}) {
  const { t } = useT();
  return (
    <Card>
      <CardContent className="space-y-5 pt-5">
        <div className="space-y-2">
          <h3 className="font-medium">{t("tutor.criteria.general")}</h3>
          <Sentences criteria={general} />
        </div>
        <div className="space-y-1">
          <h3 className="font-medium">{t("tutor.criteria.byUnit")}</h3>
          {units.map((unit) => (
            <details key={unit.name} className="group border-t border-border py-2 first-of-type:border-t-0">
              <summary className="flex cursor-pointer list-none items-center gap-2">
                <ChevronRight className="size-4 shrink-0 transition-transform group-open:rotate-90" aria-hidden />
                <span className="min-w-0 flex-1">{unit.name}</span>
                <span className="text-small text-muted-foreground">{unit.criteria.length}</span>
              </summary>
              <div className="pb-1 pl-6 pt-2">
                <Sentences criteria={unit.criteria} />
              </div>
            </details>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/** A list of criteria as plain sentences; only what is required says so. */
function Sentences({ criteria }: { criteria: Criterion[] }) {
  const { t } = useT();
  if (criteria.length === 0) {
    return <p className="text-small text-muted-foreground">{t("tutor.criteria.none")}</p>;
  }
  return (
    <ul className="list-disc space-y-1.5 pl-5">
      {criteria.map((criterion, index) => (
        <li key={index}>
          {criterion.text}
          {criterion.strength === "must" ? (
            <span className="ml-2 text-micro font-condensed uppercase text-muted-foreground">
              {t("tutor.criteria.must")}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

const GENERAL = "general";
const TERMS = "terms";
const ADMIN = "admin";
const unitKey = (name: string) => `unit:${name}`;

/**
 * The criteria under correction: the list of the document's parts beside the part open.
 *
 * The three parts that concern the subject whole lead the list — its criteria, what the
 * tutor never suggests, the administrative reply — and the units follow under a caption,
 * numbered as the tutor numbers them everywhere. A row says how much its part holds and how
 * many of its rows are changed and not saved, so a correction left in another part is never
 * out of sight. The bar is the stage screens' own: the state of the changes, the way out
 * (which asks first when it would lose something) and the save.
 */
function Correction({
  saved,
  draft,
  units,
  error,
  saving,
  onChange,
  onStop,
  onSave,
}: {
  saved: CriteriaDocument;
  draft: CriteriaDocument;
  units: { name: string; concepts: string[] }[];
  error?: string;
  saving: boolean;
  onChange: (draft: CriteriaDocument) => void;
  onStop: () => void;
  onSave: () => void;
}) {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const [open, setOpen] = useState(GENERAL);
  const part = useRef<HTMLDivElement>(null);
  // A part chosen from the foot of a long one would open at its own foot, or wherever the
  // window stopped: its name comes back to the top, level with the list.
  const show = (key: string) => {
    setOpen(key);
    const node = part.current;
    if (node && node.getBoundingClientRect().top < parseFloat(getComputedStyle(node).scrollMarginTop)) {
      node.scrollIntoView({ block: "start" });
    }
  };

  const items: SectionEntry[] = [
    {
      key: GENERAL,
      label: t("tutor.criteria.general"),
      mark: <BookOpen className="size-4" />,
      detail: plural("tutor.criteria.count", draft.general.length),
      pending: changes(saved.general, draft.general),
    },
    {
      key: TERMS,
      label: t("tutor.criteria.terms"),
      mark: <Ban className="size-4" />,
      detail: plural("tutor.criteria.terms.count", draft.forbidden_terms.length),
      pending: changes(saved.forbidden_terms, draft.forbidden_terms),
    },
    {
      key: ADMIN,
      label: t("tutor.criteria.admin.short"),
      title: t("tutor.criteria.admin"),
      mark: <Mail className="size-4" />,
      detail: t("tutor.criteria.admin.detail"),
      pending: saved.administrative_reply === draft.administrative_reply ? 0 : 1,
    },
    ...units.map((unit, index) => ({
      key: unitKey(unit.name),
      label: unit.name,
      title: unit.name,
      group: index === 0 ? t("tutor.criteria.byUnit") : undefined,
      mark: (
        <span className="flex h-4 min-w-4 shrink-0 items-center justify-center rounded-sm border border-current px-0.5 text-micro leading-none">
          {index + 1}
        </span>
      ),
      detail: plural("tutor.criteria.count", (draft.units[unit.name] ?? []).length),
      pending: changes(saved.units[unit.name] ?? [], draft.units[unit.name] ?? []),
    })),
  ];
  const dirty = items.some((item) => item.pending);
  const unit = units.find((candidate) => unitKey(candidate.name) === open);

  const stop = async () => {
    if (
      dirty &&
      !(await confirm({
        title: t("stage.curate.stop"),
        body: t("stage.curate.discardConfirm"),
        confirmLabel: t("stage.curate.discard"),
        tone: "danger",
      }))
    )
      return;
    onStop();
  };

  return (
    <Sections label={t("tutor.criteria.sections")} items={items} value={open} onChange={show}>
      {/* Cleared of the sticky header, as the list beside it is. */}
      <div ref={part} className="scroll-mt-40 space-y-7 xl:scroll-mt-24">
        {open === TERMS ? (
          <TermsSection
            terms={draft.forbidden_terms}
            onChange={(forbidden_terms) => onChange({ ...draft, forbidden_terms })}
          />
        ) : open === ADMIN ? (
          <>
            <SectionHeader title={t("tutor.criteria.admin")} description={t("tutor.criteria.admin.body")} />
            <Card>
              <CardContent className="pt-5">
                <Textarea
                  aria-label={t("tutor.criteria.admin")}
                  autoGrow
                  value={draft.administrative_reply}
                  onChange={(event) => onChange({ ...draft, administrative_reply: event.target.value })}
                />
              </CardContent>
            </Card>
          </>
        ) : unit ? (
          <CriteriaSection
            key={unit.name}
            title={unit.name}
            description={t("tutor.criteria.unit.body")}
            concepts={unit.concepts}
            criteria={draft.units[unit.name] ?? []}
            onChange={(listed) => onChange({ ...draft, units: { ...draft.units, [unit.name]: listed } })}
          />
        ) : (
          <CriteriaSection
            key={GENERAL}
            title={t("tutor.criteria.general")}
            description={t("tutor.criteria.general.body")}
            concepts={units.flatMap((each) => each.concepts)}
            criteria={draft.general}
            onChange={(general) => onChange({ ...draft, general })}
          />
        )}
      </div>

      <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-inner bg-popover px-5 py-3 shadow-overlay">
        <Pencil aria-hidden className="size-4 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-body font-semibold">{t("stage.curate.bar")}</p>
          <p className={cn("text-small", error ? "text-destructive" : "text-muted-foreground")}>
            {error ?? t(dirty ? "stage.curate.unsaved" : "stage.curate.noChanges")}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button variant="outline" disabled={saving} onClick={() => void stop()}>
            <Eye className="hidden sm:block" />
            {t("stage.curate.stop")}
          </Button>
          <Button variant={dirty ? "attention" : "default"} disabled={!dirty || saving} onClick={onSave}>
            {saving ? <Spinner className="size-4" /> : null}
            {t("stage.curate.save")}
          </Button>
        </div>
      </div>
    </Sections>
  );
}

const EMPTY: Criterion = { text: "", strength: "should", concepts: [], sources: [] };

/** One part of criteria under correction: the subject's, or one unit's. */
function CriteriaSection({
  title,
  description,
  concepts,
  criteria,
  onChange,
}: {
  title: string;
  description: string;
  concepts: string[];
  criteria: Criterion[];
  onChange: (criteria: Criterion[]) => void;
}) {
  const { t } = useT();
  // The row just added takes the caret; a row drawn because the part was opened does not.
  const added = useRef(false);
  const put = (index: number, next: Criterion) =>
    onChange(criteria.map((criterion, i) => (i === index ? next : criterion)));

  return (
    <>
      <SectionHeader title={title} description={description} />
      <Card>
        <CardContent className="space-y-4 pt-5">
          {criteria.length === 0 ? (
            <p className="text-small text-muted-foreground">{t("tutor.criteria.none")}</p>
          ) : (
            <ol className="rows">
              {criteria.map((criterion, index) => (
                <EditableCriterion
                  key={index}
                  number={index + 1}
                  criterion={criterion}
                  concepts={concepts}
                  autoFocus={added.current && index === criteria.length - 1}
                  onChange={(next) => put(index, next)}
                  onRemove={() => onChange(criteria.filter((_, i) => i !== index))}
                />
              ))}
            </ol>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              added.current = true;
              onChange([...criteria, { ...EMPTY }]);
            }}
          >
            <Plus />
            {t("tutor.criteria.add")}
          </Button>
        </CardContent>
      </Card>
    </>
  );
}

function Sources({ sources }: { sources: Criterion["sources"] }) {
  const { t } = useT();
  if (sources.length === 0) return null;
  return (
    <p className="text-small text-muted-foreground">
      {t("tutor.criteria.sources")}: {sources.map((s) => s.location || s.document).join(" · ")}
    </p>
  );
}

/**
 * One criterion as a row of its part: the sentence, then how strongly it binds and the
 * concepts it is about on one line, then where it came from.
 *
 * No caption over each control: the part's name says these are criteria, and a select that
 * reads «Obligatorio» or «Añadir un concepto…» names itself. Three captions a row, six rows
 * a part, were most of the ink on the page.
 */
function EditableCriterion({
  number,
  criterion,
  concepts,
  autoFocus,
  onChange,
  onRemove,
}: {
  number: number;
  criterion: Criterion;
  concepts: string[];
  autoFocus: boolean;
  onChange: (criterion: Criterion) => void;
  onRemove: () => void;
}) {
  const { t } = useT();
  const offered = useMemo(
    () => concepts.filter((name) => !criterion.concepts.includes(name)),
    [concepts, criterion.concepts],
  );
  return (
    <li className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-start gap-x-3">
      <span aria-hidden className="pt-2 text-small tabular-nums text-muted-foreground">
        {number}
      </span>
      <div className="min-w-0 space-y-2.5">
        <Textarea
          aria-label={`${t("tutor.criteria.text")} ${number}`}
          autoGrow
          autoFocus={autoFocus}
          rows={1}
          className="min-h-0"
          value={criterion.text}
          onChange={(event) => onChange({ ...criterion, text: event.target.value })}
        />
        <div className="flex flex-wrap items-center gap-2">
          <Select
            aria-label={t("tutor.criteria.strength")}
            className="w-auto"
            value={criterion.strength}
            onChange={(event) => onChange({ ...criterion, strength: event.target.value as Strength })}
          >
            <option value="must">{t("tutor.criteria.must")}</option>
            <option value="should">{t("tutor.criteria.should")}</option>
          </Select>
          {criterion.concepts.map((name) => (
            <ConceptChip
              key={name}
              onRemove={() =>
                onChange({ ...criterion, concepts: criterion.concepts.filter((c) => c !== name) })
              }
              removeLabel={t("tutor.criteria.removeConcept", { name })}
            >
              {name}
            </ConceptChip>
          ))}
          {offered.length > 0 ? (
            <Select
              aria-label={t("tutor.criteria.concepts")}
              className="w-auto max-w-full"
              value=""
              onChange={(event) =>
                event.target.value &&
                onChange({ ...criterion, concepts: [...criterion.concepts, event.target.value] })
              }
            >
              <option value="">{t("tutor.criteria.addConcept")}</option>
              {offered.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </Select>
          ) : null}
        </div>
        <Sources sources={criterion.sources} />
      </div>
      <Button
        variant="ghost"
        size="icon-sm"
        className="mt-1"
        aria-label={t("tutor.criteria.remove")}
        title={t("tutor.criteria.remove")}
        onClick={onRemove}
      >
        <X />
      </Button>
    </li>
  );
}

/** The terms the tutor never suggests, under correction: a name and why, a row each. */
function TermsSection({
  terms,
  onChange,
}: {
  terms: ForbiddenTerm[];
  onChange: (terms: ForbiddenTerm[]) => void;
}) {
  const { t } = useT();
  const added = useRef(false);
  const put = (index: number, next: ForbiddenTerm) =>
    onChange(terms.map((term, i) => (i === index ? next : term)));
  const columns = "grid min-w-0 flex-1 gap-2 sm:grid-cols-[12rem_minmax(0,1fr)]";
  const caption = "text-micro font-condensed uppercase text-muted-foreground";

  return (
    <>
      <SectionHeader title={t("tutor.criteria.terms")} description={t("tutor.criteria.terms.body")} />
      <Card>
        <CardContent className="space-y-4 pt-5">
          {terms.length === 0 ? (
            <p className="text-small text-muted-foreground">{t("tutor.criteria.none")}</p>
          ) : (
            <div>
              {/* The two captions once, over the columns; stacked, each box names itself. */}
              <div aria-hidden className="hidden gap-3 pb-2 pr-10 sm:flex">
                <div className={columns}>
                  <span className={caption}>{t("tutor.criteria.term")}</span>
                  <span className={caption}>{t("tutor.criteria.reason")}</span>
                </div>
              </div>
              <ul className="rows">
                {terms.map((term, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <div className={columns}>
                      <Input
                        aria-label={t("tutor.criteria.term")}
                        placeholder={t("tutor.criteria.term")}
                        autoFocus={added.current && index === terms.length - 1}
                        className="font-mono"
                        value={term.term}
                        onChange={(event) => put(index, { ...term, term: event.target.value })}
                      />
                      <Textarea
                        aria-label={t("tutor.criteria.reason")}
                        placeholder={t("tutor.criteria.reason")}
                        autoGrow
                        rows={1}
                        className="min-h-0"
                        value={term.reason}
                        onChange={(event) => put(index, { ...term, reason: event.target.value })}
                      />
                    </div>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="mt-1"
                      aria-label={t("tutor.criteria.remove")}
                      title={t("tutor.criteria.remove")}
                      onClick={() => onChange(terms.filter((_, i) => i !== index))}
                    >
                      <X />
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              added.current = true;
              onChange([...terms, { term: "", reason: "", sources: [] }]);
            }}
          >
            <Plus />
            {t("tutor.criteria.addTerm")}
          </Button>
        </CardContent>
      </Card>
    </>
  );
}

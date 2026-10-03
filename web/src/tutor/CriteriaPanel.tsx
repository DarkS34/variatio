import { ChevronRight, Plus, RefreshCw, Sparkles, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConceptChip } from "@/components/ui/concept-chip";
import { useConfirm } from "@/components/ui/confirm";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Alert, EmptyState, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { when } from "@/lib/format";
import { useT } from "@/lib/i18n";

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

  const editing = draft !== null;
  const shown = draft ?? data.criteria;
  const commit = () => {
    if (!draft) return;
    save.mutate(draft, {
      onSuccess: (saved) => {
        setDraft(null);
        toast({
          title: t("tutor.criteria.saved"),
          description: saved.warnings.length ? saved.warnings.join(" ") : undefined,
          tone: "settled",
        });
      },
    });
  };

  return (
    <div className="space-y-4 pb-20">
      {header}

      {data.warnings.length > 0 ? (
        <Alert tone="attention" title={t("tutor.criteria.warnings")}>
          <ul className="list-disc pl-5">
            {data.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </Alert>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {editing ? null : (
          <Button variant="outline" onClick={() => setDraft(structuredClone(data.criteria))}>
            {t("tutor.criteria.correct")}
          </Button>
        )}
        <Button variant="ghost" disabled={!ready || editing} onClick={() => void rebuild()}>
          <RefreshCw />
          {t("tutor.criteria.rebuild")}
        </Button>
      </div>

      {editing ? (
        <>
          <Section
            title={t("tutor.criteria.general")}
            concepts={data.units.flatMap((unit) => unit.concepts)}
            criteria={shown.general}
            onChange={(general) => draft && setDraft({ ...draft, general })}
          />
          {data.units.map((unit) => (
            <Section
              key={unit.name}
              title={unit.name}
              concepts={unit.concepts}
              criteria={shown.units[unit.name] ?? []}
              onChange={(listed) =>
                draft && setDraft({ ...draft, units: { ...draft.units, [unit.name]: listed } })
              }
            />
          ))}
        </>
      ) : (
        <Review
          general={shown.general}
          units={data.units.map((unit) => ({ name: unit.name, criteria: shown.units[unit.name] ?? [] }))}
        />
      )}

      <Terms
        terms={shown.forbidden_terms}
        editing={editing}
        onChange={(forbidden_terms) => draft && setDraft({ ...draft, forbidden_terms })}
      />

      <Card>
        <CardHeader>
          <CardTitle>{t("tutor.criteria.admin")}</CardTitle>
          <CardDescription>{t("tutor.criteria.admin.body")}</CardDescription>
        </CardHeader>
        <CardContent>
          {editing ? (
            <Textarea
              aria-label={t("tutor.criteria.admin")}
              autoGrow
              value={shown.administrative_reply}
              onChange={(event) => draft && setDraft({ ...draft, administrative_reply: event.target.value })}
            />
          ) : (
            <p className="whitespace-pre-wrap">{shown.administrative_reply}</p>
          )}
        </CardContent>
      </Card>

      {editing ? (
        <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-2 border-t border-border bg-background/95 py-3 backdrop-blur">
          <span className="text-small text-muted-foreground">
            {save.error ? save.error.message : t("tutor.criteria.unsaved")}
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setDraft(null)} disabled={save.isPending}>
              {t("tutor.criteria.discard")}
            </Button>
            <Button variant="attention" onClick={commit} disabled={save.isPending}>
              {save.isPending ? <Spinner className="size-4" /> : null}
              {t("tutor.criteria.save")}
            </Button>
          </div>
        </div>
      ) : null}
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

const EMPTY: Criterion = { text: "", strength: "should", concepts: [], sources: [] };

/** One block of criteria under correction: the subject's, or one unit's. */
function Section({
  title,
  concepts,
  criteria,
  onChange,
}: {
  title: string;
  concepts: string[];
  criteria: Criterion[];
  onChange: (criteria: Criterion[]) => void;
}) {
  const { t } = useT();
  const put = (index: number, next: Criterion) =>
    onChange(criteria.map((criterion, i) => (i === index ? next : criterion)));

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {criteria.map((criterion, index) => (
          <EditableCriterion
            key={index}
            criterion={criterion}
            concepts={concepts}
            onChange={(next) => put(index, next)}
            onRemove={() => onChange(criteria.filter((_, i) => i !== index))}
          />
        ))}
        <Button variant="outline" size="sm" onClick={() => onChange([...criteria, { ...EMPTY }])}>
          <Plus />
          {t("tutor.criteria.add")}
        </Button>
      </CardContent>
    </Card>
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

function EditableCriterion({
  criterion,
  concepts,
  onChange,
  onRemove,
}: {
  criterion: Criterion;
  concepts: string[];
  onChange: (criterion: Criterion) => void;
  onRemove: () => void;
}) {
  const { t } = useT();
  const offered = useMemo(
    () => concepts.filter((name) => !criterion.concepts.includes(name)),
    [concepts, criterion.concepts],
  );
  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <Field label={t("tutor.criteria.text")}>
        <Textarea
          autoGrow
          value={criterion.text}
          onChange={(event) => onChange({ ...criterion, text: event.target.value })}
        />
      </Field>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("tutor.criteria.strength")}>
          <Select
            value={criterion.strength}
            onChange={(event) => onChange({ ...criterion, strength: event.target.value as Strength })}
          >
            <option value="must">{t("tutor.criteria.must")}</option>
            <option value="should">{t("tutor.criteria.should")}</option>
          </Select>
        </Field>
        {offered.length > 0 ? (
          <Field label={t("tutor.criteria.concepts")}>
            <Select
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
          </Field>
        ) : null}
        <Button variant="ghost" size="sm" className="ml-auto" onClick={onRemove}>
          <X />
          {t("tutor.criteria.remove")}
        </Button>
      </div>
      {criterion.concepts.length > 0 ? (
        <div className="flex flex-wrap gap-1">
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
        </div>
      ) : null}
      <Sources sources={criterion.sources} />
    </div>
  );
}

function Terms({
  terms,
  editing,
  onChange,
}: {
  terms: ForbiddenTerm[];
  editing: boolean;
  onChange: (terms: ForbiddenTerm[]) => void;
}) {
  const { t } = useT();
  const put = (index: number, next: ForbiddenTerm) =>
    onChange(terms.map((term, i) => (i === index ? next : term)));
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("tutor.criteria.terms")}</CardTitle>
        <CardDescription>{t("tutor.criteria.terms.body")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {terms.length === 0 && !editing ? (
          <p className="text-small text-muted-foreground">{t("tutor.criteria.none")}</p>
        ) : null}
        {terms.map((term, index) =>
          editing ? (
            <div key={index} className="flex flex-wrap items-end gap-2">
              <Field label={t("tutor.criteria.term")} className="w-40">
                <Input value={term.term} onChange={(event) => put(index, { ...term, term: event.target.value })} />
              </Field>
              <Field label={t("tutor.criteria.reason")} className="min-w-48 flex-1">
                <Input
                  value={term.reason}
                  onChange={(event) => put(index, { ...term, reason: event.target.value })}
                />
              </Field>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t("tutor.criteria.remove")}
                onClick={() => onChange(terms.filter((_, i) => i !== index))}
              >
                <X />
              </Button>
            </div>
          ) : (
            <p key={index}>
              <code className="font-mono">{term.term}</code>
              {term.reason ? <span className="text-muted-foreground"> — {term.reason}</span> : null}
            </p>
          ),
        )}
        {editing ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onChange([...terms, { term: "", reason: "", sources: [] }])}
          >
            <Plus />
            {t("tutor.criteria.addTerm")}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

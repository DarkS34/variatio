import { useMutation } from "@tanstack/react-query";
import { Check, FileText, Hourglass, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Textarea } from "@/components/ui/input";
import { Alert, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { hasExemplars } from "@/lib/concepts";
import { duration } from "@/lib/format";
import type { ConceptSource, KgSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useDescriptions,
  useElapsed,
  useEngineOffline,
  useJobRun,
  useSubmitJob,
} from "@/state/queries";
import { useT } from "@/lib/i18n";
import { jobName, stepName } from "@/lib/names";
import { CancelButton } from "@/components/CancelButton";

/**
 * What the chain writes on its own, put where it can be read and corrected.
 *
 * The descriptions are NOT a manual step: `initialize` — and therefore «Indexar conceptos»,
 * and any generation — builds the `Embedder`, and the first thing it does is write the
 * description of every taggable concept that lacks one. This screen is where they are
 * reviewed and where a rewrite can be forced, not where they originate.
 *
 * Each is composed against the paragraphs of the theory corpus the concept came from
 * (`sources`), which is what is shown under the text: without that evidence a description is
 * what the model knew about the topic, and not what the syllabus says.
 */

/** What is happening while they are being written, on the screen where it was asked for. */
function WritingProgress() {
  const { t } = useT();
  const run = useJobRun("describe_concepts");
  const status = run?.job?.status;
  const active = status === "running" || status === "queued";
  const elapsed = useElapsed(run?.job?.started_at ?? null, active);

  if (!run || !active) return null;

  const step = run.steps.filter((s) => s.status === "running").at(-1);

  return (
    <Card>
      <CardContent className="space-y-2 py-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Spinner />
          <p className="text-body font-medium">
            {(step ? stepName(step.id, t, step.label) : null) ??
              (run.job ? jobName(run.job.kind, t, run.job.label) : null)}
          </p>
          <span className="flex items-center gap-1 text-small nums text-muted-foreground">
            <Hourglass className="size-3" />
            {duration(elapsed)}
          </span>
          <CancelButton run={run} className="ml-auto" />
        </div>
        {/* No bar: the header's is already this job's while it runs. Two stacked bars counting the
            same thing read as two different things. */}
        {/* Saved after each concept, so cancelling keeps what was written. Saying so here is what
            makes the button above not scary. */}
        <p className="truncate text-small text-muted-foreground">
          {step?.detail ?? t("desc.preparing")}
          {t("desc.savedPerConcept")}
        </p>
      </CardContent>
    </Card>
  );
}

function SourcePassages({ sources, named }: { sources: ConceptSource[]; named: boolean }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);

  if (sources.length === 0) {
    return (
      <p className="mt-2 flex items-center gap-1.5 text-small text-attention">
        <TriangleAlert className="size-3.5" />
        {t("desc.noBacking")}
      </p>
    );
  }

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-1.5 text-small text-muted-foreground transition-colors hover:text-foreground"
      >
        <FileText className="size-3.5" />
        {open
          ? t("desc.hideMaterial", { n: sources.length })
          : t("desc.showMaterial", { n: sources.length })}
      </button>
      {open ? (
        <div className="mt-2 space-y-2">
          {sources.map((source, index) => (
            <blockquote
              key={index}
              className="border-l-2 border-border bg-muted/40 px-3 py-2 text-small leading-relaxed"
            >
              {named || source.location ? (
                <p className="mb-1 font-mono text-[11px] text-muted-foreground">
                  {[named ? source.document : "", source.location]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              ) : null}
              <p className="whitespace-pre-wrap">{source.text}</p>
            </blockquote>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function DescriptionReview({ kg }: { kg: KgSummary }) {
  const { plural, t } = useT();
  const query = useDescriptions();
  const submit = useSubmitJob();
  const offline = useEngineOffline();
  const run = useJobRun("describe_concepts");
  const writing = run?.job?.status === "running" || run?.job?.status === "queued";
  const [filter, setFilter] = useState("");
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<Record<string, boolean>>({});

  const save = useMutation({
    mutationFn: ({ concept, description }: { concept: string; description: string }) =>
      api.saveDescription(concept, description),
    onSuccess: (_data, variables) => {
      setSaved((current) => ({ ...current, [variables.concept]: true }));
      window.setTimeout(
        () => setSaved((current) => ({ ...current, [variables.concept]: false })),
        1500,
      );
      query.refetch();
    },
  });

  const rows = useMemo(() => {
    const descriptions = query.data?.descriptions ?? {};
    const needle = filter.trim().toLowerCase();
    return kg.concepts
      .filter((concept) => concept.taggable)
      .filter((concept) => !onlyMissing || !descriptions[concept.name])
      .filter(
        (concept) =>
          !needle ||
          concept.name.toLowerCase().includes(needle) ||
          concept.domain.toLowerCase().includes(needle),
      );
  }, [kg.concepts, query.data, filter, onlyMissing]);

  if (query.isLoading) return <Skeleton className="h-96" />;

  const descriptions = query.data?.descriptions ?? {};
  const missing = query.data?.missing ?? [];
  const sources = query.data?.sources ?? {};
  const unanchored = query.data?.unanchored ?? [];
  const namedDocuments = Boolean(query.data?.many_documents);
  const described = kg.totals.taggable - missing.length;

  /* One bar: while writing it counts the job, and the rest of the time the coverage. There
     were two, stacked and advancing together, which reads as two different measures when
     during a generation they are the same one. */
  const step = writing ? run?.steps.filter((s) => s.status === "running").at(-1) : undefined;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-56 flex-1">
          <div className="mb-1 flex items-baseline justify-between text-small">
            <span className="text-muted-foreground">
              {writing ? t("desc.writing") : t("desc.withDescription")}
            </span>
            <span className="nums">
              {writing
                ? `${step?.current ?? 0}/${step?.total ?? kg.totals.taggable}`
                : `${described}/${kg.totals.taggable}`}
            </span>
          </div>
          {writing ? (
            <Progress value={step?.current ?? 0} max={step?.total ?? null} />
          ) : (
            <Progress
              value={described}
              max={kg.totals.taggable}
              tone={missing.length === 0 ? "settled" : "attention"}
            />
          )}
        </div>

        {/* The button stayed the same when pressed: `submit.isPending` only lasts as long as the
            POST, and from then on the job ran without this screen saying anything. What rules now is
            the job's state in the event stream, the same one that paints the bar below. */}
        <Button
          variant={missing.length > 0 ? "default" : "outline"}
          disabled={submit.isPending || writing || Boolean(offline)}
          title={offline ?? undefined}
          onClick={() => submit.mutate({ kind: "describe_concepts", params: {}, force: true })}
        >
          {submit.isPending || writing ? <Spinner /> : <Sparkles />}
          {writing ? t("desc.writingShort") : t("desc.generateMissing")}
        </Button>
        <Button
          variant="ghost"
          disabled={submit.isPending || writing || Boolean(offline)}
          title={offline ?? t("desc.regenerateAllHint")}
          onClick={() =>
            submit.mutate({ kind: "describe_concepts", params: { overwrite: true }, force: true })
          }
        >
          <RefreshCw />
          {t("desc.regenerateAll")}
        </Button>
        <Button
          variant="secondary"
          disabled={submit.isPending || writing || Boolean(offline)}
          title={
            offline ??
            t("desc.indexHint")
          }
          onClick={() => submit.mutate({ kind: "index", params: {}, force: true })}
        >
          {t("desc.index")}
        </Button>
      </div>

      <WritingProgress />

      {/* Said once, visibly, and not behind an (i): it is the only sentence that explains why
          this tab exists and why nothing has to be pressed to have them. */}
      <p className="text-small leading-relaxed text-muted-foreground">
        {t("desc.why")}
      </p>

      {missing.length > 0 && !writing ? (
        <Alert tone="attention" title={plural("desc.missing", missing.length)} />
      ) : null}

      {unanchored.length > 0 ? (
        <Alert
          tone="attention"
          title={plural("desc.unanchored", unanchored.length)}
          action={
            <InfoHint label={t("desc.unanchoredHintLabel")}>{t("desc.unanchoredHint")}</InfoHint>
          }
        />
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label={t("desc.filter")}
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder={t("desc.filterPlaceholder")}
          className="max-w-72"
        />
        <Button
          size="sm"
          variant={onlyMissing ? "default" : "outline"}
          onClick={() => setOnlyMissing((value) => !value)}
        >
          <TriangleAlert />
          {t("desc.onlyMissing")}
        </Button>
        <span className="text-small text-muted-foreground">
          {plural("desc.conceptCount", rows.length)}
        </span>
      </div>

      <div className="space-y-2">
        {rows.map((concept) => {
          const stored = descriptions[concept.name] ?? "";
          const value = edits[concept.name] ?? stored;
          const dirty = value !== stored;
          return (
            <div
              key={concept.name}
              className={cn(
                "rounded-lg border border-border p-3",
                !stored && "border-[color-mix(in_oklch,var(--attention)_45%,var(--border))]",
              )}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="text-body font-medium">{concept.name}</span>
                <Badge variant="outline">{concept.domain}</Badge>
                {hasExemplars(concept) ? null : (
                  <Badge variant="attention">{t("desc.noExamples")}</Badge>
                )}
                <div className="ml-auto flex items-center gap-2">
                  {saved[concept.name] ? (
                    <span className="flex items-center gap-1 text-small text-settled">
                      <Check className="size-3.5" />
                      {t("desc.saved")}
                    </span>
                  ) : null}
                  {dirty ? (
                    <>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          setEdits((current) => {
                            const next = { ...current };
                            delete next[concept.name];
                            return next;
                          })
                        }
                      >
                        {t("common.discard")}
                      </Button>
                      <Button
                        size="sm"
                        disabled={save.isPending}
                        onClick={() =>
                          save.mutate({ concept: concept.name, description: value })
                        }
                      >
                        {t("common.save")}
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
              <Textarea
                aria-label={t("desc.of", { name: concept.name })}
                value={value}
                onChange={(event) =>
                  setEdits((current) => ({ ...current, [concept.name]: event.target.value }))
                }
                placeholder={t("desc.placeholder")}
                className="min-h-20"
              />
              <SourcePassages
                sources={sources[concept.name] ?? []}
                named={namedDocuments}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

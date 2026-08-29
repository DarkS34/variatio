import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, Pencil, Save, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { InfoHint } from "@/components/ui/hint";
import { Input, Textarea } from "@/components/ui/input";
import { Alert, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { truncate } from "@/lib/format";
import { useCanEdit } from "@/state/auth";
import { keys, useContentContext } from "@/state/queries";
import { useT, type Key } from "@/lib/i18n";

// The paragraph is paid for in every call the system makes and may reach 900 characters
// (`CONTENT_CONTEXT_MAX_CHARS`). On the panel it is read to RECOGNISE it — «yes, this is
// the right subject» — not to review it, and the `line-clamp-2` beside this is the half
// that holds whatever the character count lets through. It is shown whole when editing.
const PREVIEW_CHARS = 160;

const FACT_LABEL: Record<string, Key> = {
  subject: "context.fact.subject",
  educational_level: "context.fact.level",
  language_of_instruction: "context.fact.language",
};

/**
 * What subject this instance is about, in prose.
 *
 * It lives on the panel and not in a stage because it is not one: it has no raw data of its
 * own, no builder of its own, and it is not in `review.ARTIFACTS`. The graph and profile
 * builds synthesise it, each with what its artifact knows about the subject, and each
 * writes the DRAFT. What is edited here is the curated one, which wins on read — that pair
 * is what keeps a rebuild from rewriting what a person wrote.
 *
 * The three loose facts are neither decoration nor a leftover of the old format: the
 * evaluation's naive arm composes a sentence from them and cannot read the paragraph.
 */
export function ContextCard() {
  const { t } = useT();
  const query = useContentContext();
  const canEdit = useCanEdit();
  const client = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [narrative, setNarrative] = useState("");
  const [facts, setFacts] = useState<Record<string, string>>({});

  const data = query.data;

  useEffect(() => {
    if (!data || editing) return;
    setNarrative(data.narrative);
    setFacts(data.facts);
  }, [data, editing]);

  const refresh = () => client.invalidateQueries({ queryKey: keys.context });

  const save = useMutation({
    mutationFn: () => api.saveContext(narrative, facts),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });

  const adopt = useMutation({
    mutationFn: () => api.adoptContextDraft(),
    onSuccess: refresh,
  });

  if (query.isLoading) return <Skeleton className="h-40" />;
  if (!data)
    return <LoadError title={t("context.unreadable")} error={query.error} onRetry={query.refetch} />;

  const factKeys = Array.from(new Set([...data.canonical_keys, ...Object.keys(facts)]));

  return (
    <Card>
      <CardHeader className="pb-2">
        {/* What this is FOR goes behind the (i), like every other card in this column: it
            is three lines of prose about a file that is read here to be recognised, not to
            be studied, and on a panel of eight blocks it was the longest thing on the
            screen that nobody was going to act on. */}
        <div className="flex items-center gap-2">
          <CardTitle className="flex items-center gap-1.5">
            <BookOpen className="size-4 text-muted-foreground" />
            {t("context.title")}
            <InfoHint label={t("context.whatIsThis")}>{t("context.interpolated")}</InfoHint>
          </CardTitle>
          {data.source ? (
            <Badge variant="outline" className="ml-auto">
              {data.source === "curated" ? t("context.curated") : t("context.draft")}
            </Badge>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {!data.exists && !editing ? (
          <Alert tone="attention" title={t("context.none")}>
            <p>
              {t("context.noneBody")}
            </p>
          </Alert>
        ) : null}

        {editing ? (
          <>
            <Field
              label={t("context.prose")}
              description={t("context.proseHelp")}
            >
              <Textarea
                value={narrative}
                onChange={(event) => setNarrative(event.target.value)}
                className="min-h-28 text-small"
                placeholder={t("context.prosePlaceholder")}
              />
            </Field>

            <div className="grid gap-2 sm:grid-cols-3">
              {factKeys.map((key) => (
                <Field key={key} label={FACT_LABEL[key] ? t(FACT_LABEL[key]) : key}>
                  <Input
                    value={facts[key] ?? ""}
                    className="h-8"
                    onChange={(event) =>
                      setFacts((current) => ({ ...current, [key]: event.target.value }))
                    }
                  />
                </Field>
              ))}
            </div>
            <p className="text-small text-muted-foreground">
              {t("context.threeFacts")}
            </p>

            <div className="flex gap-2">
              <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
                {save.isPending ? <Spinner /> : <Save />}
                {t("common.save")}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                <X />
                {t("common.cancel")}
              </Button>
            </div>
          </>
        ) : (
          <>
            {data.narrative ? (
              <p className="line-clamp-2 text-small text-muted-foreground" title={data.narrative}>
                {truncate(data.narrative, PREVIEW_CHARS)}
              </p>
            ) : data.block ? (
              <pre className="line-clamp-2 whitespace-pre-wrap font-mono text-small text-muted-foreground">
                {truncate(data.block, PREVIEW_CHARS)}
              </pre>
            ) : null}

            {canEdit ? (
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
                  <Pencil />
                  {data.exists ? t("common.edit") : t("context.write")}
                </Button>
                {/* A build always writes the draft, so with a curated context the latest synthesis sits
                    there unread. The notice that said so with the whole text inside left the panel; what
                    stays is the way to adopt it, the one thing that cannot be done from anywhere else. */}
                {data.pending_draft ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => adopt.mutate()}
                    disabled={adopt.isPending}
                    title={t("context.adoptHint")}
                  >
                    {adopt.isPending ? <Spinner /> : <Check />}
                    {t("context.adopt")}
                  </Button>
                ) : null}
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

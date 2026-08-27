import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Save, X } from "lucide-react";
import { useMemo, useState } from "react";

import { ConceptSelector } from "@/components/ConceptSelector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/input";
import { Alert, Skeleton, Switch } from "@/components/ui/misc";
import { adjacency, priors } from "@/features/run/prerequisites";
import { getCurriculum, putCurriculum } from "@/lib/api";
import { when } from "@/lib/format";
import { useKg, useKgGraph } from "@/state/queries";
import { useT, type Key } from "@/lib/i18n";

const sorted = (names: string[]) => [...names].sort((a, b) => a.localeCompare(b, "es"));

// The server's own sentinel (`KG_BUILDER_UNCLASSIFIED_DOMAIN`), matched against rather
// than read. Translating it breaks the match.
const UNCLASSIFIED_DOMAIN = "Sin clasificar"; // i18n-exempt

// `adjacency()` returns null for two unrelated reasons — the graph declares no prerequisite
// relation, or there is no graph payload to read — and only the first one means that what
// is on screen is what will be saved. The server closes the prerequisites regardless, so
// promising otherwise while the request is failing is the one way to save a curriculum
// larger than the screen announced.
const NOTICE = {
  none: {
    tone: "attention",
    titleKey: "curric.notice.none.title",
    bodyKey: "curric.notice.none.body",
  },
  loading: {
    tone: "info",
    titleKey: "curric.notice.loading.title",
    bodyKey: "curric.notice.loading.body",
  },
  error: {
    tone: "attention",
    titleKey: "curric.notice.error.title",
    bodyKey: "curric.notice.error.body",
  },
} as const satisfies Record<string, { tone: string; titleKey: Key; bodyKey: Key }>;

// Membership rather than a joined string: a concept name is free Spanish text, so any
// separator would be a guess about what cannot appear inside one.
const same = (a: string[], b: string[]) => {
  if (a.length !== b.length) return false;
  const set = new Set(a);
  return b.every((name) => set.has(name));
};

export function CurriculumTab() {
  const { plural, t } = useT();
  const client = useQueryClient();
  const kg = useKg();
  const graph = useKgGraph();
  const curriculum = useQuery({ queryKey: ["kg", "curriculum"], queryFn: getCurriculum });

  const [draft, setDraft] = useState<string[] | null>(null);
  const [closePrerequisites, setClosePrerequisites] = useState(false);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stored = curriculum.data?.concepts ?? [];
  const dropped = curriculum.data?.dropped ?? [];
  const selected = draft ?? stored;

  const adj = useMemo(() => adjacency(graph.data), [graph.data]);
  const notice = graph.data
    ? adj
      ? null
      : NOTICE.none
    : graph.isError
      ? NOTICE.error
      : NOTICE.loading;

  // Proposed in the open, never rewritten behind the user: this is the same closure the
  // server computes on PUT, so what the alert lists is exactly what gets saved.
  const implied = useMemo(
    () => (closePrerequisites && adj ? priors(adj, selected) : []),
    [closePrerequisites, adj, selected],
  );
  const impliedSet = useMemo(() => new Set(implied), [implied]);

  const save = useMutation({
    mutationFn: () => putCurriculum(selected, closePrerequisites),
    onSuccess: (next) => {
      client.setQueryData(["kg", "curriculum"], next);
      setDraft(null);
      setError(null);
    },
    onError: (e: Error) => setError(e.message),
  });

  if (curriculum.isLoading || kg.isLoading) return <Skeleton className="h-96" />;

  const concepts = kg.data?.concepts ?? [];
  const units = (kg.data?.domains ?? []).filter(
    (unit) =>
      unit.concepts.length > 0 &&
      unit.name.toLowerCase() !== UNCLASSIFIED_DOMAIN.toLowerCase(),
  );
  const dirty = draft !== null && !same(draft, stored);
  const canSave = dirty || implied.length > 0 || dropped.length > 0;

  return (
    <div className="space-y-4">
      <Alert tone="info" title={t("curric.whatItDeclares")}>
        <p>{t("curric.whatItDeclares.body")}</p>
      </Alert>

      {units.length > 1 ? (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle>{t("curric.howFar")}</CardTitle>
            <p className="mt-1 text-small text-muted-foreground">{t("curric.howFar.body")}</p>
          </CardHeader>
          <CardContent>
            <Field label={t("curric.upTo")} className="max-w-md">
              {(injected) => (
                <Select
                  {...injected}
                  value=""
                  onChange={(event) => {
                    const upTo = Number(event.target.value);
                    if (!upTo) return;
                    setDraft([...new Set(units.slice(0, upTo).flatMap((u) => u.concepts))]);
                  }}
                >
                  <option value="">{t("curric.chooseUnit")}</option>
                  {units.map((unit, index) => (
                    <option key={unit.name} value={index + 1}>
                      {t("curric.unitOption", {
                        index: index + 1,
                        name: unit.name,
                        concepts: plural("outline.conceptCount", unit.concepts.length),
                      })}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
          <div className="min-w-0">
            <CardTitle>
              {t("curric.title", {
                concepts: plural("outline.conceptCount", selected.length),
              })}
            </CardTitle>
            <p className="mt-1 text-small text-muted-foreground">
              {t("curric.lastSaved", { when: when(curriculum.data?.updated_at ?? null) })}
              {dirty ? t("curric.unsaved") : null}
            </p>
          </div>
          <Button variant="outline" onClick={() => setPicking(true)}>
            <Pencil />
            {t("curric.edit")}
          </Button>
        </CardHeader>
        <CardContent>
          {selected.length === 0 ? (
            <p className="text-body text-muted-foreground">{t("curric.emptyMeansAll")}</p>
          ) : (
            <div className="thin-scroll flex max-h-64 flex-wrap gap-1 overflow-y-auto">
              {sorted(selected).map((name) => (
                <Badge key={name} variant="secondary" className="pr-1">
                  {name}
                  <button
                    type="button"
                    aria-label={t("curric.remove", { name })}
                    onClick={() => setDraft(selected.filter((c) => c !== name))}
                    className="rounded-full p-0.5 hover:bg-background/60"
                  >
                    <X className="size-3" />
                  </button>
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {dropped.length > 0 ? (
        <Alert tone="attention" title={t("curric.dropped.title")}>
          <p>{t("curric.dropped.body", { names: dropped.join(", ") })}</p>
        </Alert>
      ) : null}

      {closePrerequisites && implied.length > 0 ? (
        <Alert tone="info" title={plural("curric.impliedTitle", implied.length)}>
          <p>{implied.join(", ")}.</p>
        </Alert>
      ) : null}

      {closePrerequisites && notice ? (
        <Alert tone={notice.tone} title={t(notice.titleKey)}>
          <p>{t(notice.bodyKey)}</p>
        </Alert>
      ) : null}

      {error ? (
        <Alert tone="danger" title={t("curric.saveFailed")}>
          <p>{error}</p>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3">
        <div className="flex items-center gap-2">
          <Switch
            checked={closePrerequisites}
            onCheckedChange={setClosePrerequisites}
            label={t("curric.closeSwitch")}
          />
          <div>
            <p className="text-body">{t("curric.closeTitle")}</p>
            <p className="text-small text-muted-foreground">{t("curric.closeBody")}</p>
          </div>
        </div>
        <Button disabled={!canSave || save.isPending} onClick={() => save.mutate()}>
          <Save />
          {t("curric.save")}
        </Button>
      </div>

      <ConceptSelector
        open={picking}
        onClose={() => setPicking(false)}
        title={t("curric.selectorTitle")}
        concepts={concepts}
        graph={graph.data}
        selected={selected}
        onChange={setDraft}
        implied={impliedSet}
        allowNonTaggable
        showExemplarCount={false}
      />
    </div>
  );
}

import { ListChecks, Undo2 } from "lucide-react";
import { useMemo, useState } from "react";

import { ConceptSelector } from "@/components/ConceptSelector";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { adjacency, priors } from "@/features/generate/prerequisites";
import { domainColours } from "@/lib/domains";
import { when } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { progressByUnit } from "@/lib/courseProgress";
import type { CurriculumState } from "@/lib/types";
import { useCurriculum, useKg, useKgGraph, useSaveCurriculum } from "@/state/queries";

/** The line under «Avance de la asignatura» in the section list: how much of the syllabus is covered. */
export function progressDetail(
  state: CurriculumState | undefined,
  t: ReturnType<typeof useT>["t"],
): string | null {
  if (!state) return null;
  return state.concepts.length > 0
    ? t("class.progress.detail", { n: state.concepts.length })
    : t("class.progress.none");
}

/**
 * «Avance de la asignatura»: what the class has covered, which bounds what its students practise.
 *
 * The same selector the generate form uses to declare a coverage, closed under the graph's
 * prerequisites as it is saved (`PUT /api/kg/curriculum`): ticking «Recursividad» covers
 * what it rests on. A student's commission then runs inside it (`curriculum.resolve`), the
 * syllabus tints it, and «Quitar el límite» saves the empty list, which bounds nobody.
 * Read unit by unit, in the syllabus' order, because «Tema 3 · 2 de 7» is the reading a
 * teacher has of a course.
 */
export function ProgressSection() {
  const { t } = useT();
  const toast = useToast();
  const confirm = useConfirm();
  const state = useCurriculum();
  const kg = useKg();
  const graph = useKgGraph();
  const save = useSaveCurriculum();
  const [draft, setDraft] = useState<string[] | null>(null);

  const adj = useMemo(() => adjacency(graph.data), [graph.data]);
  const implied = useMemo(
    () => new Set(adj && draft ? priors(adj, draft) : []),
    [adj, draft],
  );
  const covered = state.data?.concepts ?? [];
  const units = useMemo(
    () => progressByUnit(kg.data?.domains ?? [], covered),
    [kg.data, covered],
  );
  const colours = useMemo(() => domainColours(kg.data?.concepts ?? []), [kg.data]);

  const failed = (error: Error) =>
    toast({ title: t("class.failed"), description: error.message, tone: "danger" });

  const store = (concepts: string[]) =>
    save.mutate(concepts, {
      onSuccess: (saved) =>
        toast({
          title: saved.concepts.length > 0 ? t("class.progress.saved") : t("class.progress.lifted"),
        }),
      onError: failed,
    });

  const lift = async () => {
    const asked = await confirm({
      title: t("class.progress.liftConfirm"),
      body: t("class.progress.liftConfirmBody"),
      confirmLabel: t("class.progress.lift"),
    });
    if (asked) store([]);
  };

  const header = (
    <SectionHeader title={t("class.progress")} description={t("class.progress.lead")} />
  );

  if (state.isError || kg.isError) {
    return (
      <>
        {header}
        <LoadError
          title={t("class.progress.unreadable")}
          error={state.error ?? kg.error}
          onRetry={() => {
            state.refetch();
            kg.refetch();
          }}
        />
      </>
    );
  }
  if (state.isLoading || kg.isLoading) {
    return (
      <>
        {header}
        <Skeleton className="h-48" />
      </>
    );
  }

  const total = kg.data?.concepts.length ?? 0;
  const set = covered.length > 0;

  return (
    <>
      {header}
      {/* Drawn as «Funcionalidades permitidas» draws its switches: ruled rows, each a name,
          one line under it and its control on the right. */}
      <section className="surface p-5" aria-label={t("class.progress")}>
        <ul className="rows">
          <li className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 space-y-0.5">
              <p className="font-medium">
                {set ? t("class.progress.covered", { n: covered.length, total }) : t("class.progress.noLimit")}
              </p>
              <p className="text-small text-muted-foreground">
                {set
                  ? t("class.progress.savedOn", { date: when(state.data?.updated_at ?? null) })
                  : t("class.progress.noLimitBody")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-1">
              {save.isPending ? <Spinner /> : null}
              <Button
                size="sm"
                variant="outline"
                disabled={save.isPending || total === 0}
                onClick={() => setDraft([...covered])}
              >
                <ListChecks />
                {t(set ? "class.progress.change" : "class.progress.mark")}
              </Button>
              {set ? (
                <Button size="sm" variant="ghost" disabled={save.isPending} onClick={lift}>
                  <Undo2 />
                  {t("class.progress.lift")}
                </Button>
              ) : null}
            </div>
          </li>
          {set
            ? units.map((unit) => (
                <li key={unit.name} className="flex items-center gap-3">
                  <span
                    aria-hidden
                    className="size-2.5 shrink-0 rounded-full"
                    style={{ background: colours.get(unit.name) }}
                  />
                  <span className="min-w-0 flex-1 truncate font-medium">{unit.name}</span>
                  <span className="hidden h-2 w-40 overflow-hidden rounded-full bg-muted sm:block">
                    <span
                      className="block h-full rounded-full bg-ink"
                      style={{ width: `${unit.total ? (100 * unit.covered) / unit.total : 0}%` }}
                    />
                  </span>
                  <span className="nums w-16 shrink-0 text-right text-small text-muted-foreground">
                    {t("class.progress.ofUnit", { n: unit.covered, total: unit.total })}
                  </span>
                </li>
              ))
            : null}
        </ul>

        {state.data && state.data.dropped.length > 0 ? (
          <p className="pt-3 text-small text-attention">
            {t("class.progress.dropped", { names: state.data.dropped.join(", ") })}
          </p>
        ) : null}
      </section>

      <ConceptSelector
        title={t("class.progress.pickTitle")}
        concepts={kg.data?.concepts ?? []}
        graph={graph.data}
        selected={draft ?? []}
        onChange={setDraft}
        implied={implied}
        allowNonTaggable
        open={draft !== null}
        onClose={() => setDraft(null)}
        onConfirm={() => {
          if (draft !== null) store(draft);
          setDraft(null);
        }}
        confirmLabel={t("class.progress.save")}
      />
    </>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  FolderPlus,
  Link2,
  ListChecks,
  Maximize2,
  Plus,
  Search,
  Trash2,
  Waypoints,
} from "lucide-react";
import { useMemo, useState } from "react";

import { JobProgress } from "@/components/BuildProgress";
import { LOCKED_HINT, StageGate, useStageLocked } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Field } from "@/components/ui/field";
import { Input, Select } from "@/components/ui/input";
import { Alert, LoadError, Separator, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, getCurriculum } from "@/lib/api";
import { relationColour, when } from "@/lib/format";
import { useRouter } from "@/lib/router";
import type { KgConcept, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useEngineOffline,
  useInvalidateChain,
  useJobPhases,
  useJobRun,
  useJobRunning,
  useKg,
  useKgGraph,
  usePipeline,
  useSubmitJob,
} from "@/state/queries";
import { ConceptOutline, FrontierKey, type CurriculumPlace } from "./ConceptOutline";
import { CurriculumTab } from "./CurriculumTab";
import { DescriptionReview } from "./DescriptionReview";
import { GraphCanvas } from "./GraphCanvas";
import { buildModel, frontierOf } from "./graph/model";
import { useT } from "@/lib/i18n";

function ConceptDetail({
  concept,
  domains,
  relations,
  concepts,
  onChanged,
}: {
  concept: KgConcept;
  domains: string[];
  relations: string[];
  concepts: KgConcept[];
  onChanged: () => void;
}) {
  const { t } = useT();
  const locked = useStageLocked();
  const [name, setName] = useState(concept.name);
  const [domain, setDomain] = useState(concept.domain);
  const [relation, setRelation] = useState(relations[0] ?? "");
  const [target, setTarget] = useState("");
  const [error, setError] = useState<string | null>(null);

  const toast = useToast();
  const neighbours = useQuery({
    queryKey: ["kg", "neighbours", concept.name],
    queryFn: () => api.kgNeighbours(concept.name),
  });

  // Every edit of the graph goes through here, so this is where the acknowledgement
  // belongs. Deleting a concept takes its relations with it and the only way back is the
  // history file; it was one of the actions that said nothing at all.
  const run = <T,>(action: () => Promise<T>, done?: string) => {
    setError(null);
    return action()
      .then(() => {
        onChanged();
        neighbours.refetch();
        if (done) toast({ title: done });
      })
      .catch((e: Error) => {
        setError(e.message);
        toast({ title: t("kg.saveFailed"), description: e.message, tone: "danger" });
      });
  };

  const update = useMutation({
    mutationFn: (body: Parameters<typeof api.updateConcept>[0]) => api.updateConcept(body),
  });

  const dirty = name !== concept.name || domain !== concept.domain;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Field label={t("kg.conceptName")}>
          <Input
            value={name}
            readOnly={locked}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>
        <Field label={t("kg.unit")}>
          <Select
            value={domain}
            disabled={locked}
            title={locked ? t(LOCKED_HINT) : undefined}
            onChange={(event) => setDomain(event.target.value)}
          >
            {domains.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex items-center justify-between rounded-md border border-border p-2">
          <div className="flex items-center gap-1.5">
            <p className="text-body">{t("kg.taggable")}</p>
            <InfoHint label={t("kg.taggable.hintLabel")}>{t("kg.taggable.hint")}</InfoHint>
          </div>
          <Switch
            checked={concept.taggable}
            disabled={locked}
            onCheckedChange={(next) =>
              run(() => api.updateConcept({ name: concept.name, taggable: next }))
            }
            label="etiquetable"
          />
        </div>
        {dirty && !locked ? (
          <Button
            size="sm"
            className="w-full"
            disabled={update.isPending}
            onClick={() =>
              run(() =>
                api.updateConcept({
                  name: concept.name,
                  new_name: name !== concept.name ? name : undefined,
                  domain: domain !== concept.domain ? domain : undefined,
                }),
              )
            }
          >
            Guardar cambios
          </Button>
        ) : null}
      </div>

      {concept.description ? (
        <div className="space-y-1">
          <h4 className="text-micro font-condensed uppercase text-muted-foreground">
            {t("kg.description")}
          </h4>
          <p className="rounded-md border border-border bg-muted/40 p-2 text-body leading-relaxed">
            {concept.description}
          </p>
        </div>
      ) : (
        <Alert tone="attention">
          <p className="text-small">{t("kg.noDescription")}</p>
        </Alert>
      )}

      <div className="flex gap-4 text-small text-muted-foreground">
        <span>{t("kg.degree", { n: concept.degree })}</span>
      </div>

      <Separator />

      <div className="space-y-2">
        <h4 className="text-micro font-condensed uppercase text-muted-foreground">
          {t("kg.relations")}
        </h4>
        {neighbours.isLoading ? (
          <Spinner />
        ) : (
          Object.entries(neighbours.data?.relations ?? {}).map(([verb, data]) => (
            <div key={verb} className="space-y-1">
              <p className="text-small font-medium">{verb}</p>
              <div className="flex flex-wrap gap-1">
                {[...data.out.map((n) => ({ n, dir: "→" })), ...data.in.map((n) => ({ n, dir: "←" }))].map(
                  ({ n, dir }) => (
                    <Badge key={`${verb}-${dir}-${n}`} variant="secondary" className="pr-1">
                      <span className="text-muted-foreground">{dir}</span>
                      {n}
                      {locked ? null : (
                        <button
                          type="button"
                          aria-label={t("kg.removeEdge", { name: n })}
                          onClick={() =>
                            run(() =>
                              api.removeEdge(
                                verb,
                                dir === "→" ? concept.name : n,
                                dir === "→" ? n : concept.name,
                              ),
                            )
                          }
                          className="rounded-full p-0.5 hover:bg-background/60"
                        >
                          <Trash2 className="size-3" />
                        </button>
                      )}
                    </Badge>
                  ),
                )}
                {data.out.length === 0 && data.in.length === 0 ? (
                  <span className="text-small text-muted-foreground">—</span>
                ) : null}
              </div>
            </div>
          ))
        )}

        <div className="flex gap-1 pt-1">
          <Select
            aria-label={t("kg.relationType")}
            disabled={locked}
            value={relation}
            onChange={(event) => setRelation(event.target.value)}
            className="text-small"
          >
            {relations.map((verb) => (
              <option key={verb} value={verb}>
                {verb}
              </option>
            ))}
          </Select>
          <Select
            aria-label={t("kg.targetConcept")}
            disabled={locked}
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            className="text-small"
          >
            <option value="">{t("kg.conceptPlaceholder")}</option>
            {concepts
              .filter((c) => c.name !== concept.name)
              .map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
          </Select>
          <Button
            size="icon"
            variant="outline"
            disabled={locked || !target || !relation}
            title={locked ? t(LOCKED_HINT) : undefined}
            onClick={() => run(() => api.addEdge(relation, concept.name, target)).then(() => setTarget(""))}
            aria-label={t("kg.addRelation")}
          >
            <Link2 />
          </Button>
        </div>
      </div>

      {error ? <p className="text-small text-destructive">{error}</p> : null}

      <Separator />

      <Button
        variant="outline"
        disabled={locked}
        title={locked ? t(LOCKED_HINT) : undefined}
        className="w-full text-destructive hover:bg-destructive/10"
        onClick={() => {
          if (!window.confirm(t("kg.deleteConceptConfirm", { name: concept.name }))) return;
          run(() => api.deleteConcept(concept.name), t("kg.conceptDeleted"));
        }}
      >
        <Trash2 />
        {t("kg.deleteConcept")}
      </Button>
    </div>
  );
}

function AddConceptDialog({
  open,
  onClose,
  domains,
  initialDomain,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  domains: string[];
  /** The unit the dialog was opened from. Adding a concept is nearly always adding it to
   *  the unit you are looking at, and the outline is the one screen that knows which. */
  initialDomain?: string;
  onDone: () => void;
}) {
  const { t } = useT();
  const [name, setName] = useState("");
  const [domain, setDomain] = useState(initialDomain ?? domains[0] ?? "");
  const [taggable, setTaggable] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const create = useMutation({
    mutationFn: () => api.addConcept(name.trim(), domain, taggable),
    onSuccess: () => {
      onDone();
      toast({ title: t("kg.conceptCreated"), description: name.trim() });
      setName("");
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("kg.newConcept")}
      description={t("kg.newConcept.description")}
      className="max-w-md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button onClick={() => create.mutate()} disabled={!name.trim() || create.isPending}>
            {t("common.create")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label={t("kg.conceptName")}>
          <Input value={name} onChange={(event) => setName(event.target.value)} autoFocus />
        </Field>
        <Field label={t("kg.unit")}>
          <Select value={domain} onChange={(event) => setDomain(event.target.value)}>
            {domains.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex items-center gap-2">
          <Switch checked={taggable} onCheckedChange={setTaggable} label={t("kg.taggableSwitch")} />
          <span className="text-body">{t("kg.taggable")}</span>
        </div>
        {error ? <p className="text-small text-destructive">{error}</p> : null}
      </div>
    </Dialog>
  );
}

/**
 * The syllabus, with the map beside it.
 *
 * Curating a graph is a list of decisions taken concept by concept — is this a usable label,
 * does it have a description, has the course got here yet — and a force layout can show none
 * of them: it answers "what is near what", which is a question you ask once. So the outline
 * is the screen and the drawing is the reference, one click from filling the window.
 */
function GraphExplorer({ onGoToCurriculum }: { onGoToCurriculum: () => void }) {
  const { plural, t } = useT();
  const locked = useStageLocked();
  const kg = useKg();
  const graph = useKgGraph();
  // The workspace's own curriculum, read only to be drawn. `undefined` while it is loading
  // and when the workspace has none, because an empty set means "covered nothing yet",
  // which is a different statement and would dim the whole graph.
  const curriculum = useQuery({ queryKey: ["kg", "curriculum"], queryFn: () => getCurriculum() });
  const curriculumSet = useMemo(
    () => (curriculum.data ? new Set(curriculum.data.concepts) : undefined),
    [curriculum.data],
  );
  const invalidate = useInvalidateChain();

  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hiddenRelations, setHiddenRelations] = useState<Set<number>>(new Set());
  const [addingIn, setAddingIn] = useState<string | null>(null);
  const [mapOpen, setMapOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    invalidate();
    kg.refetch();
    graph.refetch();
  };

  const concepts = kg.data?.concepts ?? [];
  const domains = (kg.data?.domains ?? []).map((d) => d.name);
  const relations = (kg.data?.relations ?? []).map((r) => r.name);

  const model = useMemo(() => (graph.data ? buildModel(graph.data) : null), [graph.data]);

  // Where each concept falls relative to the frontier — the same three sets the generator
  // derives when it writes a prompt. Computed over indices because that is what the graph
  // model speaks, and handed back by name because that is what a row has.
  const frontierNames = useMemo(() => {
    if (!graph.data || !model || !curriculumSet) return null;
    const indices = new Set<number>();
    for (const name of curriculumSet) {
      const index = model.nameIndex.get(name);
      if (index !== undefined) indices.add(index);
    }
    return new Set(
      [...frontierOf(graph.data, model, indices)].map((index) => graph.data!.nodes[index][0]),
    );
  }, [graph.data, model, curriculumSet]);

  const place = (name: string): CurriculumPlace | null => {
    if (!curriculumSet) return null;
    if (curriculumSet.has(name)) return "covered";
    return frontierNames?.has(name) ? "frontier" : "ahead";
  };

  // Built from the whole graph, never from the filtered list: what a unit contains does not
  // change because a search is narrowing what is drawn, and «eliminar la unidad y sus N»
  // has to name the number that will actually be deleted.
  const unitStats = useMemo(() => {
    const stats = new Map<string, { total: number; covered: number }>();
    for (const concept of concepts) {
      const entry = stats.get(concept.domain) ?? { total: 0, covered: 0 };
      entry.total += 1;
      if (curriculumSet?.has(concept.name)) entry.covered += 1;
      stats.set(concept.domain, entry);
    }
    return stats;
  }, [concepts, curriculumSet]);

  const moveDomain = (name: string, delta: number) => {
    const from = domains.indexOf(name);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= domains.length) return;
    const next = [...domains];
    next.splice(to, 0, ...next.splice(from, 1));
    api.reorderDomains(next).then(refresh).catch((e) => setError(e.message));
  };

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return concepts;
    return concepts.filter(
      (concept) =>
        concept.name.toLowerCase().includes(needle) ||
        (concept.description ?? "").toLowerCase().includes(needle),
    );
  }, [concepts, query]);

  const highlight = useMemo(
    () => (query.trim() ? new Set(filtered.map((c) => c.name)) : undefined),
    [filtered, query],
  );

  const selectedConcept = concepts.find((c) => c.name === selected) ?? null;

  if (kg.isLoading || graph.isLoading) return <Skeleton className="h-[36rem]" />;
  if (!kg.data || !graph.data)
    return (
      <LoadError
        title={t("kg.unreadable")}
        error={kg.error ?? graph.error}
        onRetry={() => {
          kg.refetch();
          graph.refetch();
        }}
      />
    );

  if (!kg.data || !graph.data) return null;

  const totals = kg.data.totals;
  const covered = curriculumSet
    ? concepts.filter((concept) => curriculumSet.has(concept.name)).length
    : 0;

  const canvas = (compact: boolean) => (
    <GraphCanvas
      graph={graph.data!}
      selected={selected}
      onSelect={setSelected}
      highlight={highlight}
      hiddenRelations={hiddenRelations}
      curriculum={curriculumSet}
      compact={compact}
    />
  );

  const detail = (concept: KgConcept) => (
    <ConceptDetail
      key={concept.name}
      concept={concept}
      domains={domains}
      relations={relations}
      concepts={concepts}
      onChanged={refresh}
    />
  );

  return (
    <div className="space-y-3">
      {error ? (
        <Alert tone="danger" title={t("kg.editError")}>
          <p>{error}</p>
        </Alert>
      ) : null}

      {/* The list is the work and the map is the reference, so the list gets the width.
          `grid-cols-1` is not redundant with the single implicit track it replaces: an
          undeclared track is sized `auto`, i.e. to its item's MAX-content, and every row in
          the outline truncates — `white-space: nowrap` — so below `xl` the card grew to the
          width of the longest concept name and scrolled the whole page sideways. `grid-cols-1`
          is `minmax(0, 1fr)`, which is the cap, and `min-w-0` on the card is what then lets
          it take it. */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,26rem)]">
        {/* `min-w-0` is load-bearing, not tidiness: a grid item defaults to `min-width: auto`,
            and every row in here truncates — which means `white-space: nowrap`, which means a
            min-content width of the longest concept name in the graph. Without it the card
            grew to 2 940 px and put a horizontal scrollbar on the whole page. */}
        <Card className="flex max-h-[clamp(32rem,74vh,60rem)] min-h-0 min-w-0 flex-col overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 p-3">
            <span className="text-micro font-condensed uppercase text-muted-foreground">
              {t("kg.outlineHeader", {
                concepts: plural("outline.conceptCount", totals.concepts),
                taggable: totals.taggable,
              })}
            </span>
            <span className="flex-1" />
            <div className="relative min-w-56 flex-1 sm:flex-none">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
              <Input
                aria-label={t("kg.search")}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={t("kg.searchPlaceholder")}
                className="h-8 pl-8"
              />
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={locked}
              title={locked ? t(LOCKED_HINT) : undefined}
              onClick={() => {
                const name = window.prompt(t("kg.newUnitPrompt"));
                if (name?.trim())
                  api.addDomain(name.trim()).then(refresh).catch((e) => setError(e.message));
              }}
            >
              <FolderPlus />
              {t("kg.unitButton")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={locked}
              title={locked ? t(LOCKED_HINT) : undefined}
              onClick={() => setAddingIn(domains[0] ?? "")}
            >
              <Plus />
              {t("kg.conceptButton")}
            </Button>
          </div>

          <div className="thin-scroll min-h-0 flex-1 overflow-y-auto">
            <ConceptOutline
              concepts={filtered}
              units={domains}
              groups={graph.data.groups.map((group) => group.name)}
              place={place}
              unitStats={(unit) => unitStats.get(unit) ?? { total: 0, covered: 0 }}
              hasCurriculum={Boolean(curriculumSet)}
              filtering={Boolean(query.trim())}
              selected={selected}
              onSelect={setSelected}
              onRenameUnit={(name) => {
                const next = window.prompt(t("kg.renameUnitPrompt"), name);
                if (next?.trim() && next !== name)
                  api
                    .renameDomain(name, next.trim())
                    .then(refresh)
                    .catch((e) => setError(e.message));
              }}
              onMoveUnit={moveDomain}
              onDeleteUnit={(name, count) => {
                if (
                  !window.confirm(
                    t("kg.deleteUnitConfirm", {
                      name,
                      concepts: plural("outline.conceptCount", count),
                    }),
                  )
                )
                  return;
                api.deleteDomain(name).then(refresh).catch((e) => setError(e.message));
              }}
              onAddConcept={setAddingIn}
            />
          </div>
        </Card>

        {selectedConcept ? (
          <Card className="flex max-h-[clamp(32rem,74vh,60rem)] min-h-0 min-w-0 flex-col overflow-hidden">
            <CardHeader className="flex-row items-center gap-1.5 space-y-0 pb-2">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setSelected(null)}
                aria-label={t("kg.backToMap")}
              >
                <ArrowLeft />
              </Button>
              <CardTitle className="min-w-0 truncate">{selectedConcept.name}</CardTitle>
            </CardHeader>
            <CardContent className="thin-scroll min-h-0 flex-1 overflow-y-auto">
              {detail(selectedConcept)}
            </CardContent>
          </Card>
        ) : (
          /* ONE CARD, NOT THREE. The map, the curriculum and the frontier key were three
             stacked boxes down the right-hand side, each with its own border and its own
             micro heading — and the second and third are three lines and a legend that only
             mean anything ABOUT the map beside them. They are its footer now, so the column
             reads as one object: here is the graph, here is how far the course has got
             through it, here is what the colours on it mean. */
          <Card className="flex max-h-[clamp(32rem,74vh,60rem)] min-h-0 flex-col overflow-hidden">
            <div className="flex items-center justify-between gap-2 p-3 pb-2">
              <span className="text-micro font-condensed uppercase text-muted-foreground">
                {t("kg.map")}
              </span>
              <Button size="sm" variant="outline" onClick={() => setMapOpen(true)}>
                <Maximize2 />
                {t("kg.enlarge")}
              </Button>
            </div>
            <div className="h-72 shrink-0 border-y border-border">{canvas(true)}</div>

            <div className="thin-scroll min-h-0 flex-1 overflow-y-auto">

              {/* A stroke, not a dot: it is the colour of an edge on the canvas, not of a node. */}
              <div className="p-1">
                {graph.data.relations.map((relation, index) => {
                  const hidden = hiddenRelations.has(index);
                  return (
                    <button
                      key={relation.key}
                      title={hidden ? t("kg.showRelation") : t("kg.hideRelation")}
                      onClick={() =>
                        setHiddenRelations((current) => {
                          const next = new Set(current);
                          if (next.has(index)) next.delete(index);
                          else next.add(index);
                          return next;
                        })
                      }
                      className={cn(
                        "flex w-full items-center gap-2.5 px-2 py-1.5 text-left transition-colors hover:bg-accent",
                        hidden && "opacity-45",
                      )}
                    >
                      <span
                        className="h-0.5 w-3.5 shrink-0 rounded-full"
                        style={{ background: relationColour(relation.type ?? relation.key, index) }}
                      />
                      <span
                        className={cn(
                          "min-w-0 flex-1 truncate text-small",
                          hidden && "line-through",
                        )}
                      >
                        {relation.verbose ?? relation.key}
                      </span>
                      {relation.prerequisite ? (
                        <Waypoints
                          className="size-3 shrink-0 text-muted-foreground"
                          aria-label={t("kg.ordersCurriculum")}
                        />
                      ) : null}
                      <span className="nums shrink-0 text-small text-muted-foreground">
                        {relation.count}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>

            {curriculumSet ? (
              <div className="shrink-0 space-y-2 border-t border-border p-3">
                <FrontierKey />
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 text-small text-muted-foreground">
                    {covered === 0
                      ? t("kg.noCurriculum")
                      : t("kg.curriculumSaved", {
                          when: when(curriculum.data?.updated_at ?? null),
                          frontier: plural("kg.frontierCount", frontierNames?.size ?? 0),
                        })}
                  </span>
                  <span className="shrink-0 nums text-small text-muted-foreground">
                    {covered}/{totals.concepts}
                  </span>
                </div>
                <span className="block h-1 w-full bg-muted">
                  <span
                    className="block h-full bg-settled"
                    style={{
                      width: `${Math.round((covered / Math.max(1, totals.concepts)) * 100)}%`,
                    }}
                  />
                </span>
                <Button size="sm" variant="ghost" onClick={onGoToCurriculum}>
                  <Waypoints />
                  {t("kg.editCurriculum")}
                </Button>
              </div>
            ) : null}
          </Card>
        )}
      </div>

      {/* The flag is absent from every graph written before it existed, so it reads `false`
          even on one whose exclusion list proves the old in-build pass ran. The second half
          is what tells those apart, and it mirrors `stages/initialize.py`. */}
      {/* No button of its own: the header's is the only one, with its reason in the tooltip and
          its progress bar below. What stays here is what the header cannot say — what it means
          that the review has not been done. */}
      {!totals.taggability_reviewed && totals.taggable === totals.concepts ? (
        <Alert tone="attention" title={t("kg.unreviewed")}>
          <p>{t("kg.unreviewed.body", { n: totals.concepts })}</p>
        </Alert>
      ) : null}

      {/* The expanded map carries the inspector with it. Without it, choosing a concept here
          answered with a card in the rail underneath — behind the scrim, invisible — so the
          big view was the one place you could see the whole graph and change nothing in it. */}
      <Dialog
        open={mapOpen}
        onClose={() => setMapOpen(false)}
        title={t("kg.mapTitle")}
        description={t("kg.mapDescription")}
        className="sm:max-w-[100rem]"
      >
        {/* Side by side once there is room for both, stacked below it — and the map keeps
            the larger half either way, because the inspector is what you read AFTER
            choosing a node on it. */}
        <div className="flex h-[70vh] flex-col gap-3 lg:h-[68vh] lg:flex-row lg:gap-4">
          <div className="min-h-0 min-w-0 flex-1">{canvas(false)}</div>
          <div className="flex max-h-[45%] w-full shrink-0 flex-col overflow-hidden rounded-lg border border-border lg:max-h-none lg:w-[23rem]">
            {selectedConcept ? (
              <>
                <header className="flex items-center gap-1.5 border-b border-border p-3">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setSelected(null)}
                    aria-label={t("kg.clearSelection")}
                  >
                    <ArrowLeft />
                  </Button>
                  <h3 className="min-w-0 truncate text-heading">{selectedConcept.name}</h3>
                </header>
                <div className="thin-scroll min-h-0 flex-1 overflow-y-auto p-3">
                  {detail(selectedConcept)}
                </div>
              </>
            ) : (
              <p className="m-auto max-w-56 p-4 text-center text-small text-muted-foreground">
                {t("kg.pickOnMap")}
              </p>
            )}
          </div>
        </div>
      </Dialog>

      <AddConceptDialog
        open={addingIn !== null}
        onClose={() => setAddingIn(null)}
        domains={domains}
        initialDomain={addingIn ?? undefined}
        key={addingIn ?? "none"}
        onDone={refresh}
      />
    </div>
  );
}

export function KgScreen({ stage }: { stage: StageState | undefined }) {
  const { t } = useT();
  const [tab, setTab] = useState("graph");
  const kg = useKg();
  const pipeline = usePipeline();
  const submitReview = useSubmitJob();
  const offline = useEngineOffline();
  const reviewRun = useJobRun("review_taggability");
  const reviewing = useJobRunning("review_taggability");
  const reviewPhases = useJobPhases("review_taggability");
  const { navigate } = useRouter();
  const missing = (kg.data?.totals.taggable ?? 0) - (kg.data?.totals.described ?? 0);

  // Taggability is launched from the header, like everything else an artifact knows how to
  // do to itself, and not from a notice buried in the graph tab. It does not put the stage in
  // «construyendo» — it patches a list in place, rewrites nothing — so its progress goes under
  // the header and the rest of the screen stays live.
  const totals = kg.data?.totals;
  const reviewed = Boolean(totals?.taggability_reviewed);
  const profileReady =
    pipeline.data?.stages.find((s) => s.artifact === "exemplars_profile")?.status === "approved";
  const reviewReason =
    !stage || stage.status === "missing"
      ? t("kg.review.buildFirst")
      : stage.status === "building"
        ? t("kg.review.rebuilding")
        : stage.status === "approved"
          ? t(LOCKED_HINT)
          : offline
            ? offline
            : !profileReady
              ? t("kg.review.needsProfile")
              : reviewing
                ? t("kg.review.running")
                : null;

  return (
    <StageGate
      stage={stage}
      title={t("kg.stage.title")}
      description={t("kg.stage.description")}
    >
      {/* THE TABS COME OUT OF THE HEADER. They were in `StageGate`'s `actions` slot, which
          put a three-way view switch on the same line as «Construir de nuevo», «Aprobar»
          and the taggability review: six controls in a row, of which three change what you
          are looking at and three change the artifact. They are different kinds of thing
          and they now sit on different lines.

          The review stays beside the tabs rather than in the header for the same reason it
          is not in the notice below: it is something you do TO the graph, it exists in both
          states — a first review and a re-run — and the notice only exists in one of them. */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <Tabs
          items={[
            { value: "graph", label: t("kg.tab.graph") },
            {
              value: "descriptions",
              label: t("kg.tab.descriptions"),
              badge:
                missing > 0 ? (
                  <Badge variant="attention" className="ml-1">
                    {missing}
                  </Badge>
                ) : undefined,
            },
            { value: "curriculum", label: t("kg.tab.curriculum") },
          ]}
          value={tab}
          onChange={setTab}
        />
        <Button
          size="sm"
          variant={reviewed ? "ghost" : "attention"}
          disabled={Boolean(reviewReason) || submitReview.isPending}
          title={reviewReason ?? (reviewed ? t("kg.review.again") : t("kg.review.first"))}
          onClick={() => submitReview.mutate({ kind: "review_taggability" })}
        >
          {submitReview.isPending || reviewing ? <Spinner /> : <ListChecks />}
          {reviewing ? t("kg.review.reviewing") : t("kg.review.button")}
        </Button>
      </div>

      {reviewing || reviewRun?.job?.status === "failed" ? (
        <JobProgress
          run={reviewRun}
          phases={reviewPhases}
          className="mb-4"
          waiting={t("kg.review.waiting")}
        />
      ) : null}

      {tab === "graph" ? (
        <GraphExplorer onGoToCurriculum={() => setTab("curriculum")} />
      ) : tab === "curriculum" ? (
        <CurriculumTab />
      ) : kg.data ? (
        <DescriptionReview kg={kg.data} />
      ) : (
        <Skeleton className="h-96" />
      )}

      {stage?.status === "approved" && missing === 0 ? (
        <Alert
          tone="settled"
          className="mt-4"
          title={t("kg.readyToTag")}
          action={
            <Button size="sm" onClick={() => navigate("/prepare/bank")}>
              {t("kg.goToBank")}
              <ArrowRight />
            </Button>
          }
        />
      ) : null}
    </StageGate>
  );
}

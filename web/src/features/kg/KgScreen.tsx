import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ChevronRight,
  FolderPlus,
  Link2,
  ListChecks,
  Maximize2,
  Plus,
  Search,
  Trash2,
  Waypoints,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { JobProgress } from "@/components/BuildProgress";
import { LOCKED_HINT, StageGate, useStageLocked } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ConfirmDialog, PromptDialog } from "@/components/ui/prompt";
import { Field } from "@/components/ui/field";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Alert, LoadError, Separator, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { api, getCurriculum } from "@/lib/api";
import { relationColour } from "@/lib/format";
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
import { ConceptOutline } from "./ConceptOutline";
import { GraphCanvas } from "./GraphCanvas";
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
  const [description, setDescription] = useState(concept.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

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
  const saveDescription = useMutation({
    mutationFn: (body: { concept: string; description: string }) =>
      api.saveDescription(body.concept, body.description),
  });

  // The outgoing half of every relation, flattened out of the per-verb map the API sends.
  // Order is the API's — its relation list is the schema's — so two concepts read their
  // relations in the same order.
  const outgoing = Object.entries(neighbours.data?.relations ?? {}).flatMap(([verb, data]) =>
    data.out.map((target) => ({ verb, target })),
  );

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
        {/* NO TAGGABILITY SWITCH HERE since 2026-09-01 (explicit user request): it is on the
            concept's own row in the list, where the state is judged — a pass down the
            syllabus deciding which concepts work as labels — instead of one click inside
            each concept. Its (i) went to the column header with it. */}
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
            {t("kg.saveChanges")}
          </Button>
        ) : null}
      </div>

      {/* LA DESCRIPCIÓN SE CORRIGE AQUÍ (2026-09-01, explicit user request), que es donde
          se está leyendo. Antes vivía en una pestaña propia que revisaba las 162 en fila,
          lo cual es una tarea distinta de la única que se hace de verdad: leer un concepto,
          ver que su descripción no lo describe y arreglarla.

          Es un fichero aparte del artefacto, así que editarla NO caduca la aprobación de la
          etapa — por eso el campo sigue vivo con el temario aprobado, a diferencia del
          nombre y la unidad. */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <h4 className="text-micro font-condensed uppercase text-muted-foreground">
            {t("kg.description")}
          </h4>
          {!concept.description ? (
            <Badge variant="attention">{t("kg.noDescriptionBadge")}</Badge>
          ) : null}
        </div>
        <Textarea
          autoGrow
          aria-label={t("kg.description")}
          value={description}
          placeholder={t("kg.descriptionPlaceholder")}
          onChange={(event) => setDescription(event.target.value)}
          className="min-h-20 text-small"
        />
        <div className="flex items-center gap-2">
          <p className="min-w-0 flex-1 text-small text-muted-foreground">
            {t("kg.descriptionNote")}
          </p>
          {description !== (concept.description ?? "") ? (
            <Button
              size="sm"
              disabled={saveDescription.isPending}
              onClick={() =>
                saveDescription.mutate(
                  { concept: concept.name, description },
                  {
                    onSuccess: () => {
                      onChanged();
                      toast({ title: t("kg.descriptionSaved") });
                    },
                    onError: (e: Error) => setError(e.message),
                  },
                )
              }
            >
              {saveDescription.isPending ? <Spinner /> : null}
              {t("common.save")}
            </Button>
          ) : null}
        </div>
      </div>

      <Separator />

      <div className="space-y-2">
        <h4 className="text-micro font-condensed uppercase text-muted-foreground">
          {t("kg.relations")}
        </h4>
        {/* UNA FRASE POR RELACIÓN, Y SÓLO LAS QUE SALEN DE ESTE CONCEPTO (2026-09-01,
            explicit user request). Antes era una rejilla de distintivos con «→» y «←»
            delante de cada vecino, agrupados por verbo: para leer «Algoritmo tiene como
            prerrequisito Pensamiento computacional» había que componer la frase uno mismo a
            partir de un título, una flecha y un nombre.

            Las entrantes se van con las flechas. Son las mismas aristas vistas del otro
            lado — si «Algoritmo de búsqueda se engloba en Algoritmo», eso es algo que dice
            «Algoritmo de búsqueda» — y listarlas aquí duplicaba cada arista en las dos
            fichas, que es exactamente de donde venía la necesidad de la flecha. */}
        {neighbours.isLoading ? (
          <Spinner />
        ) : outgoing.length === 0 ? (
          <p className="text-small text-muted-foreground">{t("kg.noRelations")}</p>
        ) : (
          <ul className="space-y-0.5">
            {outgoing.map(({ verb, target }) => (
              <li
                key={`${verb}-${target}`}
                className="group flex items-baseline gap-1.5 rounded-md px-1.5 py-1 hover:bg-accent/50"
              >
                <span className="min-w-0 flex-1 text-body leading-relaxed">
                  <span className="font-medium">{concept.name}</span>{" "}
                  <span className="text-muted-foreground">{verb}</span>{" "}
                  <span className="font-medium">{target}</span>
                </span>
                {locked ? null : (
                  <button
                    type="button"
                    aria-label={t("kg.removeEdge", { name: target })}
                    title={t("kg.removeEdge", { name: target })}
                    onClick={() => run(() => api.removeEdge(verb, concept.name, target))}
                    className="shrink-0 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity hover:text-destructive focus-visible:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                )}
              </li>
            ))}
          </ul>
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
        onClick={() => setConfirmDelete(true)}
      >
        <Trash2 />
        {t("kg.deleteConcept")}
      </Button>

      <ConfirmDialog
        open={confirmDelete}
        tone="danger"
        title={t("kg.deleteConceptTitle", { name: concept.name })}
        confirmLabel={t("common.delete")}
        onCancel={() => setConfirmDelete(false)}
        onConfirm={() => {
          setConfirmDelete(false);
          run(() => api.deleteConcept(concept.name), t("kg.conceptDeleted"));
        }}
      >
        <p>{t("kg.deleteConceptBody")}</p>
      </ConfirmDialog>
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
        <Switch checked={taggable} onCheckedChange={setTaggable}>
          <span className="text-body">{t("kg.taggable")}</span>
        </Switch>
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
function GraphExplorer() {
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
  // The three unit operations, as dialogs of this application rather than the browser's.
  // `window.prompt` cannot validate — it does not know which names are taken — and
  // `window.confirm` guarded «eliminar la unidad y sus 28 conceptos» with one click while
  // deleting an empty workspace asks you to type its slug.
  const [newUnit, setNewUnit] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [deletingUnit, setDeletingUnit] = useState<{ name: string; count: number } | null>(null);
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

  // Where a concept falls relative to the frontier is no longer DRAWN here (2026-09-01,
  // explicit user request) — neither as a column nor as a key under the map. The canvas
  // still receives `curriculumSet` and still tints its own curriculum layout with it,
  // which is the one place the three sets are visible; what left is the reporting of them
  // row by row, along with the editor that used to set the list.

  // Built from the whole graph, never from the filtered list: what a unit contains does not
  // change because a search is narrowing what is drawn, and «eliminar la unidad y sus N»
  // has to name the number that will actually be deleted.
  const unitStats = useMemo(() => {
    const stats = new Map<string, { total: number }>();
    for (const concept of concepts) {
      const entry = stats.get(concept.domain) ?? { total: 0 };
      entry.total += 1;
      stats.set(concept.domain, entry);
    }
    return stats;
  }, [concepts]);

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
      {/* EL CONCEPTO SE ABRE A LA DERECHA DE LA LISTA (2026-09-01, explicit user request),
          que es donde estaba antes de volverse un diálogo unas horas antes ese mismo día.
          Lo que hacía imposible la columna era el cuestionario de la etapa ocupando la
          mitad derecha de forma permanente; se convirtió en un cajón esa misma tarde, así
          que ese ancho ha vuelto y la respuesta a un clic puede estar al lado de la fila
          que se ha pulsado. La segunda pista solo existe mientras hay concepto elegido: sin
          él la lista se queda con la pantalla entera, que es lo que pide una fila que
          trunca. Por debajo de `xl` la ficha se apila bajo la lista — es el único ancho en
          el que no cabe al lado. El mapa sigue plegado bajo la lista: lo que estaba plegado
          sigue estando, y la leyenda de la frontera no vive en ningún otro sitio. */}
      <div
        className={cn(
          "grid gap-4",
          selectedConcept && "xl:grid-cols-[minmax(0,1fr)_23rem]",
        )}
      >
      <div className="min-w-0 space-y-4">
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
              onClick={() => setNewUnit(true)}
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
              unitStats={(unit) => unitStats.get(unit) ?? { total: 0 }}
              filtering={Boolean(query.trim())}
              selected={selected}
              onSelect={setSelected}
              onRenameUnit={setRenaming}
              onMoveUnit={moveDomain}
              onDeleteUnit={(name, count) => setDeletingUnit({ name, count })}
              onAddConcept={setAddingIn}
              onSetTaggable={(name, next) =>
                api
                  .updateConcept({ name, taggable: next })
                  .then(refresh)
                  .catch((e) => setError(e.message))
              }
            />
          </div>
        </Card>

        {/* Plegado por defecto: lo primero que se ve del temario es el temario, no su
            dibujo. */}
        <details className="group border border-border bg-card open:pb-1">
          <summary className="flex cursor-pointer list-none items-center gap-2 p-3 text-small font-medium hover:bg-accent">
            <ChevronRight className="size-4 shrink-0 transition-transform group-open:rotate-90" />
            {t("kg.mapFold")}
          </summary>
          {/* ONE CARD, NOT THREE. The map, the curriculum and the frontier key were three
             stacked boxes down the right-hand side, each with its own border and its own
             micro heading — and the second and third are three lines and a legend that only
             mean anything ABOUT the map beside them. They are its footer now, so the column
             reads as one object: here is the graph, here is how far the course has got
             through it, here is what the colours on it mean. */}
          <Card className="flex max-h-[clamp(32rem,74vh,60rem)] min-h-0 flex-col overflow-hidden border-0">
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

          </Card>
        </details>
      </div>

        {/* `sticky` and not a second scroller for the page: the list scrolls inside its own
            card, so the panel would otherwise sit at the top of a column as tall as the map
            fold and drift off screen. `self-start` is what lets a sticky grid item be
            shorter than its track — stretched to the full row height it has nothing to
            stick within. `detail`'s `key` remounts per concept, which is what resets the
            description draft when you move to the next one. */}
        {selectedConcept ? (
          <aside className="min-w-0 xl:sticky xl:top-20 xl:self-start">
            <Card className="flex max-h-[clamp(28rem,74vh,60rem)] min-h-0 flex-col overflow-hidden">
              <header className="flex items-center gap-1.5 border-b border-border p-3">
                <h3 className="min-w-0 flex-1 truncate text-heading">
                  {selectedConcept.name}
                </h3>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setSelected(null)}
                  aria-label={t("kg.clearSelection")}
                >
                  <X />
                </Button>
              </header>
              <div className="thin-scroll min-h-0 flex-1 overflow-y-auto p-3">
                {detail(selectedConcept)}
              </div>
            </Card>
          </aside>
        ) : null}
      </div>

      {/* The flag is absent from every graph written before it existed, so it reads `false`
          even on one whose exclusion list proves the old in-build pass ran. The second half
          is what tells those apart, and it mirrors `stages/initialize.py`. */}
      {/* No button of its own: the header's is the only one, with its reason in the tooltip and
          its progress bar below. What stays here is what the header cannot say — what it means
          that the review has not been done. */}
      {!totals.taggability_reviewed && totals.taggable === totals.concepts ? (
        <Alert tone="attention" title={t("kg.unreviewed")}>
          <p>{plural("kg.unreviewed.body", totals.concepts)}</p>
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

      <PromptDialog
        open={newUnit}
        title={t("kg.newUnitTitle")}
        label={t("kg.unitName")}
        confirmLabel={t("kg.unitButton")}
        validate={(value) =>
          domains.some((d) => d.toLowerCase() === value.toLowerCase())
            ? t("kg.unitTaken")
            : null
        }
        onCancel={() => setNewUnit(false)}
        onConfirm={(value) => {
          setNewUnit(false);
          api.addDomain(value).then(refresh).catch((e) => setError(e.message));
        }}
      />

      <PromptDialog
        open={renaming !== null}
        title={t("kg.renameUnitTitle")}
        label={t("kg.unitName")}
        initial={renaming ?? ""}
        validate={(value) =>
          value !== renaming && domains.some((d) => d.toLowerCase() === value.toLowerCase())
            ? t("kg.unitTaken")
            : null
        }
        onCancel={() => setRenaming(null)}
        onConfirm={(value) => {
          const from = renaming!;
          setRenaming(null);
          if (value !== from)
            api.renameDomain(from, value).then(refresh).catch((e) => setError(e.message));
        }}
      />

      <ConfirmDialog
        open={deletingUnit !== null}
        tone="danger"
        title={t("kg.deleteUnitTitle", { name: deletingUnit?.name ?? "" })}
        confirmLabel={t("common.delete")}
        onCancel={() => setDeletingUnit(null)}
        onConfirm={() => {
          const name = deletingUnit!.name;
          setDeletingUnit(null);
          api.deleteDomain(name).then(refresh).catch((e) => setError(e.message));
        }}
      >
        <p>
          {t("kg.deleteUnitBody", {
            concepts: plural("outline.conceptCount", deletingUnit?.count ?? 0),
          })}
        </p>
      </ConfirmDialog>

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
  const kg = useKg();
  const pipeline = usePipeline();
  const submitReview = useSubmitJob();
  const offline = useEngineOffline();
  const reviewRun = useJobRun("review_taggability");
  const reviewing = useJobRunning("review_taggability");
  const reviewPhases = useJobPhases("review_taggability");
  // THE BUILD DOES NOT END WITH THE GRAPH, AND THE SCREEN HAS TO SAY SO (2026-09-01,
  // explicit user request). `jobs/chain.py` already queues `describe_concepts`, then the
  // taggability review, then the index behind every `build_kg`; what was missing is that
  // only the middle one had anywhere to report itself, and the description job lost its
  // last home when the «Descripciones» tab went. So the two that a person waits for are
  // one block with one sentence: the graph is there, this is what is still being finished,
  // and nothing below is blocked by it.
  const describeRun = useJobRun("describe_concepts");
  const describing = useJobRunning("describe_concepts");
  const describePhases = useJobPhases("describe_concepts");
  const finishing = describing || reviewing;

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
    <StageGate stage={stage}>
      {/* ONE VIEW, AND ONE THING TO DO TO IT (2026-09-01, explicit user request).
          The three-way tab strip is gone. «Descripciones» was a screen-wide review of a
          derived file the build already writes on its own — a description is corrected on
          the concept it belongs to, in the panel beside the list — and «Currículo» went
          with the saved taught-concepts list, which is chosen per commission on the
          generate and comparison screens instead. With one view left there is nothing to
          switch between, exactly as when the profile's raw-JSON tab went.

          The review button stays where the tabs were: it is something done TO the graph, it
          exists in both states (a first pass and a re-run), and the notice below exists in
          only one of them. */}
      <div className="mb-4 flex flex-wrap items-center justify-end gap-2">
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

      {finishing ? (
        <Alert tone="info" className="mb-4" title={t("kg.finishing")}>
          <p>{t(describing ? "kg.finishing.describing" : "kg.finishing.taggable")}</p>
        </Alert>
      ) : null}

      {describing || describeRun?.job?.status === "failed" ? (
        <JobProgress run={describeRun} phases={describePhases} className="mb-4" />
      ) : null}

      {reviewing || reviewRun?.job?.status === "failed" ? (
        <JobProgress
          run={reviewRun}
          phases={reviewPhases}
          className="mb-4"
          waiting={t("kg.review.waiting")}
        />
      ) : null}

      <GraphExplorer />
    </StageGate>
  );
}

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  FolderPlus,
  Link2,
  ListChecks,
  Pencil,
  Plus,
  Search,
  Trash2,
  TriangleAlert,
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
import { Alert, Separator, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { Table, TableEmpty, TBody, TD, TR } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, getCurriculum } from "@/lib/api";
import { domainColour, relationColour } from "@/lib/format";
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
import { CurriculumTab } from "./CurriculumTab";
import { DescriptionReview } from "./DescriptionReview";
import { GraphCanvas } from "./GraphCanvas";

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
        toast({ title: "No se ha podido guardar", description: e.message, tone: "danger" });
      });
  };

  const update = useMutation({
    mutationFn: (body: Parameters<typeof api.updateConcept>[0]) => api.updateConcept(body),
  });

  const dirty = name !== concept.name || domain !== concept.domain;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Field label="Nombre">
          <Input
            value={name}
            readOnly={locked}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>
        <Field label="Dominio">
          <Select
            value={domain}
            disabled={locked}
            title={locked ? LOCKED_HINT : undefined}
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
            <p className="text-body">Etiquetable</p>
            <InfoHint label="Qué significa etiquetable">
              Un concepto no etiquetable queda fuera del retrieval y de la generación: sigue en el
              grafo por sus relaciones, pero ningún ítem se le asigna.
            </InfoHint>
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
          <h4 className="text-micro font-condensed uppercase text-muted-foreground">Descripción</h4>
          <p className="rounded-md border border-border bg-muted/40 p-2 text-body leading-relaxed">
            {concept.description}
          </p>
        </div>
      ) : (
        <Alert tone="attention">
          <p className="text-small">Sin descripción: no compite en el retrieval.</p>
        </Alert>
      )}

      <div className="flex gap-4 text-small text-muted-foreground">
        <span>grado {concept.degree}</span>
      </div>

      <Separator />

      <div className="space-y-2">
        <h4 className="text-micro font-condensed uppercase text-muted-foreground">Relaciones</h4>
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
                          aria-label={`Quitar ${n}`}
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
            aria-label="Tipo de relación"
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
            aria-label="Concepto destino"
            disabled={locked}
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            className="text-small"
          >
            <option value="">concepto…</option>
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
            title={locked ? LOCKED_HINT : undefined}
            onClick={() => run(() => api.addEdge(relation, concept.name, target)).then(() => setTarget(""))}
            aria-label="Añadir relación"
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
        title={locked ? LOCKED_HINT : undefined}
        className="w-full text-destructive hover:bg-destructive/10"
        onClick={() => {
          if (!window.confirm(`¿Eliminar el concepto "${concept.name}" y sus relaciones?`)) return;
          run(() => api.deleteConcept(concept.name), "Concepto eliminado");
        }}
      >
        <Trash2 />
        Eliminar concepto
      </Button>
    </div>
  );
}

function AddConceptDialog({
  open,
  onClose,
  domains,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  domains: string[];
  onDone: () => void;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState(domains[0] ?? "");
  const [taggable, setTaggable] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const create = useMutation({
    mutationFn: () => api.addConcept(name.trim(), domain, taggable),
    onSuccess: () => {
      onDone();
      toast({ title: "Concepto creado", description: name.trim() });
      setName("");
      onClose();
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Nuevo concepto"
      description="Se añadirá al grafo y quedará disponible para etiquetar y generar."
      className="max-w-md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={() => create.mutate()} disabled={!name.trim() || create.isPending}>
            Crear
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <Field label="Nombre">
          <Input value={name} onChange={(event) => setName(event.target.value)} autoFocus />
        </Field>
        <Field label="Dominio">
          <Select value={domain} onChange={(event) => setDomain(event.target.value)}>
            {domains.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </Field>
        <div className="flex items-center gap-2">
          <Switch checked={taggable} onCheckedChange={setTaggable} label="etiquetable" />
          <span className="text-body">Etiquetable</span>
        </div>
        {error ? <p className="text-small text-destructive">{error}</p> : null}
      </div>
    </Dialog>
  );
}

function GraphExplorer() {
  const locked = useStageLocked();
  const kg = useKg();
  const graph = useKgGraph();
  // The workspace's own curriculum, read only to be drawn. `undefined` while it is loading
  // and when the workspace has none, because an empty set means "covered nothing yet",
  // which is a different statement and would dim the whole graph.
  const curriculum = useQuery({ queryKey: ["kg", "curriculum"], queryFn: getCurriculum });
  const curriculumSet = useMemo(
    () => (curriculum.data ? new Set(curriculum.data.concepts) : undefined),
    [curriculum.data],
  );
  const invalidate = useInvalidateChain();

  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [hiddenRelations, setHiddenRelations] = useState<Set<number>>(new Set());
  const [addingConcept, setAddingConcept] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    invalidate();
    kg.refetch();
    graph.refetch();
  };

  const concepts = kg.data?.concepts ?? [];
  const domains = (kg.data?.domains ?? []).map((d) => d.name);
  const relations = (kg.data?.relations ?? []).map((r) => r.name);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return concepts.filter(
      (concept) =>
        (!domainFilter || concept.domain === domainFilter) &&
        (!needle ||
          concept.name.toLowerCase().includes(needle) ||
          (concept.description ?? "").toLowerCase().includes(needle)),
    );
  }, [concepts, query, domainFilter]);

  const highlight = useMemo(
    () => (query.trim() || domainFilter ? new Set(filtered.map((c) => c.name)) : undefined),
    [filtered, query, domainFilter],
  );

  const selectedConcept = concepts.find((c) => c.name === selected) ?? null;

  if (kg.isLoading || graph.isLoading) return <Skeleton className="h-[36rem]" />;

  if (!kg.data || !graph.data) return null;

  const totals = kg.data.totals;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            aria-label="Buscar concepto o descripción"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar concepto o descripción…"
            className="pl-8"
          />
        </div>
        <Select
          aria-label="Filtrar por dominio"
          value={domainFilter}
          onChange={(event) => setDomainFilter(event.target.value)}
          className="max-w-56"
        >
          <option value="">Todos los dominios</option>
          {domains.map((domain) => (
            <option key={domain} value={domain}>
              {domain}
            </option>
          ))}
        </Select>
        <Button
          variant="outline"
          disabled={locked}
          title={locked ? LOCKED_HINT : undefined}
          onClick={() => setAddingConcept(true)}
        >
          <Plus />
          Concepto
        </Button>
        <Button
          variant="outline"
          disabled={locked}
          title={locked ? LOCKED_HINT : undefined}
          onClick={() => {
            const name = window.prompt("Nombre del nuevo dominio");
            if (name?.trim()) api.addDomain(name.trim()).then(refresh).catch((e) => setError(e.message));
          }}
        >
          <FolderPlus />
          Dominio
        </Button>
      </div>

      {error ? (
        <Alert tone="danger" title="Error al editar el grafo">
          <p>{error}</p>
        </Alert>
      ) : null}

      {/* The canvas is the map and the inspector is the reading: editing happens beside the
          picture, not below the fold. On narrow screens the pair stacks and nothing is lost. */}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,23rem)]">
        <div className="h-[clamp(28rem,66vh,50rem)] min-w-0">
          <GraphCanvas
            graph={graph.data}
            selected={selected}
            onSelect={setSelected}
            highlight={highlight}
            hiddenRelations={hiddenRelations}
            curriculum={curriculumSet}
          />
        </div>

        <Card className="flex max-h-[36rem] min-h-0 flex-col overflow-hidden xl:max-h-[clamp(28rem,66vh,50rem)]">
          {selectedConcept ? (
            <>
              <CardHeader className="flex-row items-center gap-1.5 space-y-0 pb-2">
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setSelected(null)}
                  aria-label="Volver a la lista de conceptos"
                >
                  <ArrowLeft />
                </Button>
                <CardTitle className="min-w-0 truncate">{selectedConcept.name}</CardTitle>
              </CardHeader>
              <CardContent className="thin-scroll min-h-0 flex-1 overflow-y-auto">
                <ConceptDetail
                  key={selectedConcept.name}
                  concept={selectedConcept}
                  domains={domains}
                  relations={relations}
                  concepts={concepts}
                  onChanged={refresh}
                />
              </CardContent>
            </>
          ) : (
            <>
              <CardHeader className="pb-2">
                <CardTitle>Conceptos ({filtered.length})</CardTitle>
                <p className="text-small text-muted-foreground">
                  {totals.taggable} etiquetables ·{" "}
                  <span className={totals.described < totals.taggable ? "text-attention" : undefined}>
                    {totals.described} con descripción
                  </span>
                </p>
              </CardHeader>
              <CardContent className="thin-scroll min-h-0 flex-1 overflow-y-auto p-0">
                <Table minWidth="16rem">
                  <TBody>
                    {filtered.map((concept) => {
                      const groupIndex = graph.data!.groups.findIndex(
                        (g) => g.name === concept.domain,
                      );
                      const colour = domainColour(
                        Math.max(0, groupIndex),
                        graph.data!.groups.length,
                      );
                      return (
                        <TR
                          key={concept.name}
                          selected={selected === concept.name}
                          onSelect={() => setSelected(concept.name)}
                        >
                          <TD className="w-1 pr-0">
                            {/* The same code as the canvas: filled is a taggable target,
                                hollow is structure. */}
                            <span
                              className="block size-2 rounded-full"
                              style={
                                concept.taggable
                                  ? { background: colour }
                                  : { border: `1.5px solid ${colour}` }
                              }
                            />
                          </TD>
                          <TD className="min-w-0">
                            <span
                              className={cn(!concept.taggable && "text-muted-foreground")}
                              title={concept.taggable ? undefined : "No etiquetable"}
                            >
                              {concept.name}
                            </span>
                          </TD>
                          <TD align="num" className="whitespace-nowrap">
                            {!concept.description ? (
                              <TriangleAlert
                                className="inline size-3.5 text-attention"
                                aria-label="Sin descripción"
                              />
                            ) : null}
                          </TD>
                        </TR>
                      );
                    })}
                    {filtered.length === 0 ? (
                      <TableEmpty colSpan={3}>Ningún concepto coincide con el filtro.</TableEmpty>
                    ) : null}
                  </TBody>
                </Table>
              </CardContent>
            </>
          )}
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-small">
        <span className="flex flex-wrap items-center gap-1">
          <span className="mr-1 text-muted-foreground">Relaciones:</span>
          {graph.data.relations.map((relation, index) => (
            <button
              key={relation.key}
              title={
                hiddenRelations.has(index)
                  ? "Mostrar esta relación"
                  : "Ocultar esta relación del grafo"
              }
              onClick={() =>
                setHiddenRelations((current) => {
                  const next = new Set(current);
                  if (next.has(index)) next.delete(index);
                  else next.add(index);
                  return next;
                })
              }
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2 py-0.5 transition-colors",
                hiddenRelations.has(index)
                  ? "border-border text-muted-foreground/50 line-through"
                  : "border-border text-foreground hover:bg-accent",
              )}
            >
              {/* A stroke, not a dot: it is the colour of an edge on the canvas, not of a node. */}
              <span
                className="h-0.5 w-3 rounded-full"
                style={{
                  background: relationColour(relation.type ?? relation.key, index),
                  opacity: hiddenRelations.has(index) ? 0.3 : 1,
                }}
              />
              {relation.verbose ?? relation.key} · {relation.count}
              {relation.prerequisite ? (
                <span className="text-muted-foreground" title="Ordena la vista de currículo">
                  ↕
                </span>
              ) : null}
            </button>
          ))}
        </span>

        {/* One home for the domains: the chip filters the canvas and the list, and carries
            its own rename and delete, so the screen stops repeating them in a card below. */}
        <span className="flex flex-wrap items-center gap-1">
          <span className="mr-1 text-muted-foreground">Dominios:</span>
          {graph.data.groups.map((group, index) => (
            <span
              key={group.name}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2 py-0.5 transition-colors",
                domainFilter === group.name
                  ? "border-primary text-foreground"
                  : "border-border text-muted-foreground",
              )}
            >
              <button
                onClick={() => setDomainFilter(domainFilter === group.name ? "" : group.name)}
                title="Filtrar por este dominio"
                className="flex items-center gap-1.5 transition-colors hover:text-foreground"
              >
                <span
                  className="size-2 rounded-full"
                  style={{ background: domainColour(index, graph.data!.groups.length) }}
                />
                {group.name}
                <span className="nums">{group.count}</span>
              </button>
              {locked ? null : (
                <>
                  <button
                    aria-label={`Renombrar ${group.name}`}
                    title="Renombrar"
                    onClick={() => {
                      const next = window.prompt("Nuevo nombre del dominio", group.name);
                      if (next?.trim() && next !== group.name)
                        api
                          .renameDomain(group.name, next.trim())
                          .then(refresh)
                          .catch((e) => setError(e.message));
                    }}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <Pencil className="size-3" />
                  </button>
                  <button
                    aria-label={`Eliminar ${group.name}`}
                    title={`Eliminar el dominio y sus ${group.count} concepto(s)`}
                    onClick={() => {
                      if (
                        !window.confirm(
                          `¿Eliminar "${group.name}"? Sus ${group.count} concepto(s) se eliminarán también.`,
                        )
                      )
                        return;
                      api.deleteDomain(group.name).then(refresh).catch((e) => setError(e.message));
                    }}
                    className="text-muted-foreground transition-colors hover:text-destructive"
                  >
                    <Trash2 className="size-3" />
                  </button>
                </>
              )}
            </span>
          ))}
        </span>
      </div>

      {/* The flag is absent from every graph written before it existed, so it reads `false`
          even on one whose exclusion list proves the old in-build pass ran. The second half
          is what tells those apart, and it mirrors `stages/initialize.py`. */}
      {/* No button of its own: the header's is the only one, with its reason in the tooltip and
          its progress bar below. What stays here is what the header cannot say — what it means
          that the review has not been done. */}
      {!totals.taggability_reviewed && totals.taggable === totals.concepts ? (
        <Alert tone="attention" title="Etiquetabilidad sin revisar">
          <p>
            Los {totals.concepts} conceptos se tratan como etiquetables, incluidos los que no
            identifican nada. La revisión decide cuáles descartar, y necesita el perfil de
            ejemplares: qué sirve como etiqueta depende de qué forma tienen los ejercicios de
            esta asignatura.
          </p>
        </Alert>
      ) : null}

      <AddConceptDialog
        open={addingConcept}
        onClose={() => setAddingConcept(false)}
        domains={domains}
        onDone={refresh}
      />
    </div>
  );
}

export function KgScreen({ stage }: { stage: StageState | undefined }) {
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
      ? "Construye antes el grafo."
      : stage.status === "building"
        ? "El grafo se está reconstruyendo."
        : stage.status === "approved"
          ? LOCKED_HINT
          : offline
            ? offline
            : !profileReady
              ? "Aprueba antes el perfil de ejemplares: qué sirve como etiqueta depende de qué forma tienen los ejercicios."
              : reviewing
                ? "La revisión está en marcha."
                : null;

  return (
    <StageGate
      stage={stage}
      title="Grafo de conocimiento"
      description={
        <>
          El vocabulario del sistema. Todo lo que se etiquete y se genere después saldrá de aquí:
          ni el modelo ni tú podéis usar un concepto que no esté en el grafo. Al terminar, revisa
          las descripciones — son el texto contra el que se hace el emparejamiento.
        </>
      }
      actions={
        <>
          <Button
            size="sm"
            variant={reviewed ? "outline" : "default"}
            disabled={Boolean(reviewReason) || submitReview.isPending}
            title={
              reviewReason ??
              (reviewed
                ? "Vuelve a decidir qué conceptos sirven como etiqueta"
                : "Decide qué conceptos sirven como etiqueta contra las modalidades del perfil")
            }
            onClick={() => submitReview.mutate({ kind: "review_taggability" })}
          >
            {submitReview.isPending || reviewing ? <Spinner /> : <ListChecks />}
            {reviewing ? "Revisando…" : "Revisar etiquetabilidad"}
          </Button>
          <Tabs
            items={[
              { value: "graph", label: "Grafo y conceptos" },
              {
                value: "descriptions",
                label: "Descripciones",
                badge:
                  missing > 0 ? (
                    <Badge variant="attention" className="ml-1">
                      {missing}
                    </Badge>
                  ) : undefined,
              },
              { value: "curriculum", label: "Currículo" },
            ]}
            value={tab}
            onChange={setTab}
          />
        </>
      }
    >
      {reviewing || reviewRun?.job?.status === "failed" ? (
        <JobProgress
          run={reviewRun}
          phases={reviewPhases}
          className="mb-4"
          waiting="Revisando la etiquetabilidad. El detalle aparecerá con el primer dominio."
        />
      ) : null}

      {tab === "graph" ? (
        <GraphExplorer />
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
          title="Grafo listo para etiquetar"
          action={
            <Button size="sm" onClick={() => navigate("/preparar/banco")}>
              Ir al banco
              <ArrowRight />
            </Button>
          }
        />
      ) : null}
    </StageGate>
  );
}

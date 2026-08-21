import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  FolderPlus,
  Link2,
  Pencil,
  Plus,
  Search,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";

import { StageGate } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select } from "@/components/ui/input";
import { Alert, Separator, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { domainColour, relationColour } from "@/lib/format";
import { useRouter } from "@/lib/router";
import type { KgConcept, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useInvalidateChain,
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
  const [name, setName] = useState(concept.name);
  const [domain, setDomain] = useState(concept.domain);
  const [relation, setRelation] = useState(relations[0] ?? "");
  const [target, setTarget] = useState("");
  const [error, setError] = useState<string | null>(null);

  const neighbours = useQuery({
    queryKey: ["kg", "neighbours", concept.name],
    queryFn: () => api.kgNeighbours(concept.name),
  });

  const run = <T,>(action: () => Promise<T>) => {
    setError(null);
    return action()
      .then(() => {
        onChanged();
        neighbours.refetch();
      })
      .catch((e: Error) => setError(e.message));
  };

  const update = useMutation({
    mutationFn: (body: Parameters<typeof api.updateConcept>[0]) => api.updateConcept(body),
  });

  const dirty = name !== concept.name || domain !== concept.domain;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="space-y-1">
          <Label>Nombre</Label>
          <Input value={name} onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Dominio</Label>
          <Select value={domain} onChange={(event) => setDomain(event.target.value)}>
            {domains.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex items-center justify-between rounded-md border border-border p-2">
          <div className="flex items-center gap-1.5">
            <p className="text-sm">Etiquetable</p>
            <InfoHint label="Qué significa etiquetable">
              Un concepto no etiquetable queda fuera del retrieval y de la generación: sigue en el
              grafo por sus relaciones, pero ningún ítem se le asigna.
            </InfoHint>
          </div>
          <Switch
            checked={concept.taggable}
            onCheckedChange={(next) =>
              run(() => api.updateConcept({ name: concept.name, taggable: next }))
            }
            label="etiquetable"
          />
        </div>
        {dirty ? (
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
          <Label>Descripción</Label>
          <p className="rounded-md border border-border bg-muted/40 p-2 text-sm leading-relaxed">
            {concept.description}
          </p>
        </div>
      ) : (
        <Alert tone="warning">
          <p className="text-xs">Sin descripción: no compite en el retrieval.</p>
        </Alert>
      )}

      <div className="flex gap-4 text-xs text-muted-foreground">
        <span>grado {concept.degree}</span>
      </div>

      <Separator />

      <div className="space-y-2">
        <Label>Relaciones</Label>
        {neighbours.isLoading ? (
          <Spinner />
        ) : (
          Object.entries(neighbours.data?.relations ?? {}).map(([verb, data]) => (
            <div key={verb} className="space-y-1">
              <p className="text-xs font-medium">{verb}</p>
              <div className="flex flex-wrap gap-1">
                {[...data.out.map((n) => ({ n, dir: "→" })), ...data.in.map((n) => ({ n, dir: "←" }))].map(
                  ({ n, dir }) => (
                    <Badge key={`${verb}-${dir}-${n}`} variant="secondary" className="pr-1">
                      <span className="text-muted-foreground">{dir}</span>
                      {n}
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
                    </Badge>
                  ),
                )}
                {data.out.length === 0 && data.in.length === 0 ? (
                  <span className="text-xs text-muted-foreground">—</span>
                ) : null}
              </div>
            </div>
          ))
        )}

        <div className="flex gap-1 pt-1">
          <Select value={relation} onChange={(event) => setRelation(event.target.value)} className="text-xs">
            {relations.map((verb) => (
              <option key={verb} value={verb}>
                {verb}
              </option>
            ))}
          </Select>
          <Select value={target} onChange={(event) => setTarget(event.target.value)} className="text-xs">
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
            disabled={!target || !relation}
            onClick={() => run(() => api.addEdge(relation, concept.name, target)).then(() => setTarget(""))}
            aria-label="Añadir relación"
          >
            <Link2 />
          </Button>
        </div>
      </div>

      {error ? <p className="text-xs text-destructive">{error}</p> : null}

      <Separator />

      <Button
        variant="outline"
        className="w-full text-destructive hover:bg-destructive/10"
        onClick={() => {
          if (!window.confirm(`¿Eliminar el concepto "${concept.name}" y sus relaciones?`)) return;
          run(() => api.deleteConcept(concept.name));
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

  const create = useMutation({
    mutationFn: () => api.addConcept(name.trim(), domain, taggable),
    onSuccess: () => {
      onDone();
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
        <div className="space-y-1">
          <Label>Nombre</Label>
          <Input value={name} onChange={(event) => setName(event.target.value)} autoFocus />
        </div>
        <div className="space-y-1">
          <Label>Dominio</Label>
          <Select value={domain} onChange={(event) => setDomain(event.target.value)}>
            {domains.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={taggable} onCheckedChange={setTaggable} label="etiquetable" />
          <span className="text-sm">Etiquetable</span>
        </div>
        {error ? <p className="text-xs text-destructive">{error}</p> : null}
      </div>
    </Dialog>
  );
}

function GraphExplorer() {
  const kg = useKg();
  const graph = useKgGraph();
  const invalidate = useInvalidateChain();
  const pipeline = usePipeline();
  const submitReview = useSubmitJob();
  const running = useJobRunning("review_taggability");

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
  const profileReady =
    pipeline.data?.stages.find((s) => s.artifact === "exemplars_profile")?.status === "approved";
  const launchReview = () => submitReview.mutate({ kind: "review_taggability" });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar concepto o descripción…"
            className="pl-8"
          />
        </div>
        <Select
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
        <Button variant="outline" onClick={() => setAddingConcept(true)}>
          <Plus />
          Concepto
        </Button>
        <Button
          variant="outline"
          onClick={() => {
            const name = window.prompt("Nombre del nuevo dominio");
            if (name?.trim()) api.addDomain(name.trim()).then(refresh).catch((e) => setError(e.message));
          }}
        >
          <FolderPlus />
          Dominio
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span>{totals.concepts} conceptos</span>
        <span>{totals.taggable} etiquetables</span>
        <span className={totals.described < totals.taggable ? "text-[var(--warning)]" : undefined}>
          {totals.described} con descripción
        </span>
      </div>

      {error ? (
        <Alert tone="danger" title="Error al editar el grafo">
          <p>{error}</p>
        </Alert>
      ) : null}

      {/* El grafo manda: ancho completo y alto de ventana. Las listas van debajo, donde
          caben en horizontal en vez de estrangular el lienzo. */}
      <div className="h-[clamp(26rem,60vh,46rem)] w-full">
        <GraphCanvas
          graph={graph.data}
          selected={selected}
          onSelect={setSelected}
          highlight={highlight}
          hiddenRelations={hiddenRelations}
        />
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
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
              {/* Un trazo, no un punto: es el color de una arista del lienzo, no el de un nodo. */}
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
        <span className="flex flex-wrap items-center gap-1">
          <span className="mr-1 text-muted-foreground">Dominios:</span>
          {graph.data.groups.map((group, index) => (
            <button
              key={group.name}
              onClick={() => setDomainFilter(domainFilter === group.name ? "" : group.name)}
              title="Filtrar por este dominio"
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2 py-0.5 transition-colors",
                domainFilter === group.name
                  ? "border-primary text-foreground"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              <span
                className="size-2 rounded-full"
                style={{ background: domainColour(index, graph.data!.groups.length) }}
              />
              {group.name}
              <span className="tabular-nums">{group.count}</span>
            </button>
          ))}
        </span>
      </div>

      {/* The flag is absent from every graph written before it existed, so it reads `false`
          even on one whose exclusion list proves the old in-build pass ran. The second half
          is what tells those apart, and it mirrors `stages/initialize.py`. */}
      {!totals.taggability_reviewed && totals.taggable === totals.concepts ? (
        <Alert
          tone="warning"
          title="Etiquetabilidad sin revisar"
          action={
            <Button size="sm" disabled={!profileReady || running} onClick={launchReview}>
              Revisar etiquetabilidad
            </Button>
          }
        >
          <p>
            Los {totals.concepts} conceptos se tratan como etiquetables, incluidos los que no
            identifican nada. La revisión decide cuáles descartar, y necesita el perfil de
            ejemplares: qué sirve como etiqueta depende de qué forma tienen los ejercicios de
            esta asignatura.
            {!profileReady ? " Construye antes el perfil de ejemplares." : null}
          </p>
        </Alert>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <Card className="flex min-h-0 flex-col overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle>Conceptos ({filtered.length})</CardTitle>
          </CardHeader>
          <CardContent className="thin-scroll max-h-[26rem] min-h-0 flex-1 overflow-y-auto p-0">
            <table className="w-full text-sm">
              <tbody>
                {filtered.map((concept) => {
                  const groupIndex = graph.data!.groups.findIndex((g) => g.name === concept.domain);
                  return (
                    <tr
                      key={concept.name}
                      onClick={() => setSelected(concept.name)}
                      className={cn(
                        "cursor-pointer border-b border-border transition-colors hover:bg-accent",
                        selected === concept.name && "bg-primary/10",
                      )}
                    >
                      <td className="w-1 py-1.5 pl-3">
                        <span
                          className="block size-2 rounded-full"
                          style={{
                            background: domainColour(
                              Math.max(0, groupIndex),
                              graph.data!.groups.length,
                            ),
                          }}
                        />
                      </td>
                      <td className="min-w-0 py-1.5 pl-2 pr-2">
                        <span className={cn(!concept.taggable && "text-muted-foreground line-through")}>
                          {concept.name}
                        </span>
                      </td>
                      <td className="whitespace-nowrap py-1.5 pr-3 text-right text-xs text-muted-foreground">
                        {!concept.description ? (
                          <TriangleAlert className="inline size-3.5 text-[var(--warning)]" />
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="p-4 text-center text-sm text-muted-foreground">
                      Ningún concepto coincide con el filtro.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card className="flex min-h-0 flex-col overflow-hidden">
          <CardHeader className="pb-2">
            <CardTitle>{selectedConcept ? selectedConcept.name : "Detalle"}</CardTitle>
          </CardHeader>
          <CardContent className="thin-scroll max-h-[26rem] min-h-0 flex-1 overflow-y-auto">
            {selectedConcept ? (
              <ConceptDetail
                key={selectedConcept.name}
                concept={selectedConcept}
                domains={domains}
                relations={relations}
                concepts={concepts}
                onChanged={refresh}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                Selecciona un concepto en el grafo o en la lista para editarlo.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Dominios ({(kg.data.domains ?? []).length})</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {(kg.data.domains ?? []).map((domain, index) => (
            <div
              key={domain.name}
              className="flex items-center gap-2 rounded-full border border-border px-3 py-1 text-sm"
            >
              <span
                className="size-2 rounded-full"
                style={{ background: domainColour(index, kg.data!.domains.length) }}
              />
              {domain.name}
              <span className="text-xs text-muted-foreground">{domain.concepts.length}</span>
              <button
                aria-label={`Renombrar ${domain.name}`}
                title="Renombrar"
                onClick={() => {
                  const next = window.prompt("Nuevo nombre del dominio", domain.name);
                  if (next?.trim() && next !== domain.name)
                    api.renameDomain(domain.name, next.trim()).then(refresh).catch((e) => setError(e.message));
                }}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                <Pencil className="size-3.5" />
              </button>
              <button
                aria-label={`Eliminar ${domain.name}`}
                title={`Eliminar el dominio y sus ${domain.concepts.length} concepto(s)`}
                onClick={() => {
                  if (
                    !window.confirm(
                      `¿Eliminar "${domain.name}"? Sus ${domain.concepts.length} concepto(s) se eliminarán también.`,
                    )
                  )
                    return;
                  api.deleteDomain(domain.name).then(refresh).catch((e) => setError(e.message));
                }}
                className="text-muted-foreground transition-colors hover:text-destructive"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}
        </CardContent>
      </Card>

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
  const { navigate } = useRouter();
  const missing = (kg.data?.totals.taggable ?? 0) - (kg.data?.totals.described ?? 0);

  return (
    <StageGate
      stage={stage}
      title="1 · Grafo de conocimiento"
      description={
        <>
          El vocabulario del sistema. Todo lo que se etiquete y se genere después saldrá de aquí:
          ni el modelo ni tú podéis usar un concepto que no esté en el grafo. Al terminar, revisa
          las descripciones — son el texto contra el que se hace el emparejamiento.
        </>
      }
      actions={
        <Tabs
          items={[
            { value: "graph", label: "Grafo y conceptos" },
            {
              value: "descriptions",
              label: "Descripciones",
              badge:
                missing > 0 ? (
                  <Badge variant="warning" className="ml-1">
                    {missing}
                  </Badge>
                ) : undefined,
            },
            { value: "curriculum", label: "Currículo" },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
    >
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
          tone="success"
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

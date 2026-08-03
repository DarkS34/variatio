import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, FolderPlus, Link2, Plus, Search, Trash2, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { StageGate } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";
import { Alert, Separator, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { domainColour } from "@/lib/format";
import { useRouter } from "@/lib/router";
import type { KgConcept, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useInvalidateChain, useKg, useKgGraph } from "@/state/queries";
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
          <div>
            <p className="text-sm">Etiquetable</p>
            <p className="text-xs text-muted-foreground">
              Los no etiquetables quedan fuera del retrieval y de la generación.
            </p>
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
          <p className="text-xs">
            Sin descripción: este concepto no puede competir en el retrieval. Genérala en la
            pestaña de descripciones.
          </p>
        </Alert>
      )}

      <div className="flex gap-4 text-xs text-muted-foreground">
        <span>grado {concept.degree}</span>
        <span
          className={concept.exemplars === 0 ? "text-[var(--warning)]" : undefined}
          title={concept.exemplars === 0 ? "Se generará en zero-shot" : undefined}
        >
          {concept.exemplars} ejemplo(s)
        </span>
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

  if (!kg.data || !graph.data) {
    return (
      <Alert tone="info" title="Todavía no hay grafo de conocimiento">
        <p>Constrúyelo desde el panel para poder revisarlo.</p>
      </Alert>
    );
  }

  const totals = kg.data.totals;

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
        <span>{totals.with_exemplars} con ejemplos</span>
        <span className="ml-auto flex flex-wrap items-center gap-1">
          {graph.data.relations.map((relation, index) => (
            <button
              key={relation.key}
              onClick={() =>
                setHiddenRelations((current) => {
                  const next = new Set(current);
                  if (next.has(index)) next.delete(index);
                  else next.add(index);
                  return next;
                })
              }
              className={cn(
                "rounded-full border px-2 py-0.5 transition-colors",
                hiddenRelations.has(index)
                  ? "border-border text-muted-foreground/50 line-through"
                  : "border-border text-foreground",
              )}
            >
              {relation.verbose ?? relation.key} · {relation.count}
            </button>
          ))}
        </span>
      </div>

      {error ? (
        <Alert tone="danger" title="Error al editar el grafo">
          <p>{error}</p>
        </Alert>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="h-[36rem]">
          <GraphCanvas
            graph={graph.data}
            selected={selected}
            onSelect={setSelected}
            highlight={highlight}
            hiddenRelations={hiddenRelations}
          />
        </div>

        <div className="grid min-h-0 gap-4 lg:grid-cols-2 xl:h-[36rem] xl:grid-cols-1 xl:grid-rows-2">
          <Card className="flex min-h-0 flex-col overflow-hidden">
            <CardHeader className="pb-2">
              <CardTitle>Conceptos ({filtered.length})</CardTitle>
            </CardHeader>
            <CardContent className="thin-scroll min-h-0 max-h-96 flex-1 overflow-y-auto p-0 xl:max-h-none">
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
                          <span className="ml-2 tabular-nums">{concept.exemplars}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card className="flex min-h-0 flex-col overflow-hidden">
            <CardHeader className="pb-2">
              <CardTitle>{selectedConcept ? selectedConcept.name : "Detalle"}</CardTitle>
            </CardHeader>
            <CardContent className="thin-scroll min-h-0 max-h-[28rem] flex-1 overflow-y-auto xl:max-h-none">
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
                  Selecciona un concepto en el grafo o en la lista para verlo y editarlo.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Dominios</CardTitle>
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
                onClick={() => {
                  const next = window.prompt("Nuevo nombre del dominio", domain.name);
                  if (next?.trim() && next !== domain.name)
                    api.renameDomain(domain.name, next.trim()).then(refresh).catch((e) => setError(e.message));
                }}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                renombrar
              </button>
              <button
                onClick={() => {
                  if (
                    !window.confirm(
                      `¿Eliminar "${domain.name}"? Sus ${domain.concepts.length} concepto(s) se eliminarán también.`,
                    )
                  )
                    return;
                  api.deleteDomain(domain.name).then(refresh).catch((e) => setError(e.message));
                }}
                className="text-xs text-destructive"
              >
                eliminar
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
      title="2 · Grafo de conocimiento"
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
          ]}
          value={tab}
          onChange={setTab}
        />
      }
    >
      {tab === "graph" ? (
        <GraphExplorer />
      ) : kg.data ? (
        <DescriptionReview kg={kg.data} />
      ) : (
        <Skeleton className="h-96" />
      )}

      {stage?.status === "approved" && missing === 0 ? (
        <Alert
          tone="success"
          className="mt-4"
          title="El grafo está listo para etiquetar"
          action={
            <Button size="sm" onClick={() => navigate("/preparar/banco")}>
              Ir al banco
              <ArrowRight />
            </Button>
          }
        >
          <p>Todos los conceptos etiquetables tienen descripción.</p>
        </Alert>
      ) : null}
    </StageGate>
  );
}

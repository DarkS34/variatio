import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ChevronRight,
  Hammer,
  RefreshCw,
  Search,
  Tags,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { ConceptPicker } from "@/components/ConceptPicker";
import { StageGate } from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Alert, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { TAGGING_METHOD, truncate } from "@/lib/format";
import type { BankItem, KgConcept, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCoverage, useInvalidateChain, useKg, useSubmitJob } from "@/state/queries";

function ItemEditor({
  item,
  fields,
  primaryField,
  concepts,
  onClose,
  onSaved,
}: {
  item: BankItem;
  fields: string[];
  primaryField: string;
  concepts: KgConcept[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const field of fields) {
      const value = item[field];
      initial[field] = value === null || value === undefined ? "" : String(value);
    }
    return initial;
  });
  const [selected, setSelected] = useState<string[]>(item.concepts ?? []);
  const [primary, setPrimary] = useState<string | null>(item.primary_concept ?? null);
  const [error, setError] = useState<string | null>(null);

  const saveFields = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {};
      for (const field of fields) {
        const raw = values[field];
        payload[field] = raw === "" ? null : raw;
      }
      return api.patchItem(item.id, payload);
    },
  });

  const saveConcepts = useMutation({
    mutationFn: () => api.setConcepts(item.id, selected, primary),
  });

  const submit = async () => {
    setError(null);
    try {
      await saveFields.mutateAsync();
      await saveConcepts.mutateAsync();
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const pending = saveFields.isPending || saveConcepts.isPending;

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Ítem ${item.id}`}
      description={item.source ? `Origen: ${item.source}` : undefined}
      className="max-w-4xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={pending}>
            {pending ? <Spinner /> : null}
            Guardar
          </Button>
        </>
      }
    >
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="space-y-3">
          {fields.map((field) => (
            <div key={field} className="space-y-1">
              <Label>
                {field}
                {field === primaryField ? " · primario" : ""}
              </Label>
              <Textarea
                value={values[field] ?? ""}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [field]: event.target.value }))
                }
                className={cn("text-sm", field === primaryField ? "min-h-28" : "min-h-20")}
              />
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <div>
            <div className="mb-2 flex items-center gap-1.5">
              <Label>Conceptos</Label>
              <InfoHint label="Cómo se etiqueta un ítem">
                Solo conceptos del grafo. El marcado como principal es el que decide de qué
                concepto es ejemplo este ítem.
              </InfoHint>
            </div>
            <ConceptPicker
              concepts={concepts}
              selected={selected}
              onChange={setSelected}
              primary={primary}
              onPrimaryChange={setPrimary}
              maxHeight="14rem"
            />
          </div>

          {item._tagging ? (
            <div className="rounded-lg border border-border p-3">
              <p className="mb-2 text-xs font-medium text-muted-foreground">
                Cómo se decidió: {TAGGING_METHOD[item._tagging.method] ?? item._tagging.method}
              </p>
              {item._tagging.candidates.length === 0 ? (
                <p className="text-xs text-[var(--warning)]">
                  Ningún candidato superó el umbral de similitud.
                </p>
              ) : (
                <ul className="space-y-1">
                  {item._tagging.candidates.map(([name, score]) => (
                    <li key={name} className="flex items-center gap-2 text-xs">
                      <span className="w-12 shrink-0 tabular-nums text-muted-foreground">
                        {score.toFixed(3)}
                      </span>
                      <div className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full bg-primary"
                          style={{ width: `${Math.min(100, score * 100)}%` }}
                        />
                      </div>
                      <span className="min-w-0 truncate">{name}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </div>
      </div>

      {error ? <p className="mt-3 text-xs text-destructive">{error}</p> : null}
    </Dialog>
  );
}

function ItemRow({
  item,
  primaryField,
  selected,
  onToggle,
  onEdit,
  onDelete,
}: {
  item: BankItem;
  primaryField: string;
  selected: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const untagged = !item.concepts || item.concepts.length === 0;
  const text = String(item[primaryField] ?? "");

  return (
    <>
      <tr
        className={cn(
          "border-b border-border align-top transition-colors hover:bg-accent/60",
          untagged && "bg-[color-mix(in_oklch,var(--warning)_8%,transparent)]",
        )}
      >
        <td className="py-2 pl-3">
          <input type="checkbox" checked={selected} onChange={onToggle} className="mt-1" />
        </td>
        <td className="py-2 pl-2 font-mono text-xs text-muted-foreground">{item.id}</td>
        <td className="min-w-0 py-2 pl-2 pr-3">
          <button onClick={onEdit} className="block text-left text-sm hover:underline">
            {truncate(text, 200)}
          </button>
          {open ? (
            <div className="mt-2 space-y-2">
              {String(item.solution ?? "") ? (
                <CodeBlock code={String(item.solution)} maxHeight="16rem" />
              ) : null}
              {item._tagging ? (
                <div className="rounded-md border border-border p-2">
                  <p className="mb-1 text-xs text-muted-foreground">
                    {TAGGING_METHOD[item._tagging.method] ?? item._tagging.method}
                    {item._tagging.model ? ` · ${item._tagging.model}` : ""}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {item._tagging.candidates.map(([name, score]) => (
                      <span key={name} className="text-xs">
                        <span className="tabular-nums text-muted-foreground">
                          {score.toFixed(3)}
                        </span>{" "}
                        {name}
                      </span>
                    ))}
                    {item._tagging.candidates.length === 0 ? (
                      <span className="text-xs text-[var(--warning)]">
                        sin candidatos sobre el umbral
                      </span>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </td>
        <td className="py-2 pr-3">
          <div className="flex max-w-64 flex-wrap gap-1">
            {untagged ? (
              <Badge variant="warning">
                <TriangleAlert />
                sin concepto
              </Badge>
            ) : (
              item.concepts!.map((concept) => (
                <Badge key={concept} variant={concept === item.primary_concept ? "default" : "secondary"}>
                  {concept}
                </Badge>
              ))
            )}
          </div>
        </td>
        <td className="whitespace-nowrap py-2 pr-3 text-right">
          <Button variant="ghost" size="icon-sm" onClick={() => setOpen((value) => !value)} aria-label="Detalle">
            <ChevronRight className={cn("transition-transform", open && "rotate-90")} />
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={onDelete} aria-label="Eliminar">
            <Trash2 />
          </Button>
        </td>
      </tr>
    </>
  );
}

export function BankScreen({ stage }: { stage: StageState | undefined }) {
  const kg = useKg();
  const coverage = useCoverage();
  const submit = useSubmitJob();
  const invalidate = useInvalidateChain();

  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [concept, setConcept] = useState("");
  const [source, setSource] = useState("");
  const [untagged, setUntagged] = useState<boolean | undefined>(undefined);
  const [order, setOrder] = useState<"suspicion" | "id">("suspicion");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState<BankItem | null>(null);

  const params = { q: query, concept, source, untagged, order, page, page_size: 40 };
  const bank = useQuery({
    queryKey: ["bank", params],
    queryFn: () => api.bank(params as never),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteItem(id),
    onSuccess: () => {
      invalidate();
      bank.refetch();
    },
  });

  const concepts = kg.data?.concepts ?? [];
  const listing = bank.data;

  const pages = useMemo(
    () => (listing ? Math.max(1, Math.ceil(listing.total / listing.page_size)) : 1),
    [listing],
  );

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <StageGate
      stage={stage}
      title="3 · Banco de ejemplos"
      description={
        <>
          Los ítems extraídos de los documentos y etiquetados con conceptos del grafo. Se revisan
          por sospecha: primero los que se quedaron sin concepto, después las decisiones que se
          ganaron por poco margen.
        </>
      }
      actions={
        <>
          <Button
            variant="outline"
            disabled={submit.isPending}
            onClick={() => submit.mutate({ kind: "build_bank" })}
            title="Vuelve a extraer los ítems de los documentos en bruto"
          >
            <Hammer />
            Extraer
          </Button>
          <Button
            disabled={submit.isPending}
            onClick={() =>
              submit.mutate({
                kind: "tag",
                params: selected.size > 0 ? { ids: [...selected] } : {},
              })
            }
          >
            {submit.isPending ? <Spinner /> : <Tags />}
            {selected.size > 0 ? `Re-etiquetar (${selected.size})` : "Etiquetar pendientes"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Etiquetado</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {listing ? (
                <>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-muted-foreground">Ítems con concepto</span>
                    <span className="tabular-nums">
                      {listing.totals.tagged}/{listing.totals.items}
                    </span>
                  </div>
                  <Progress
                    value={listing.totals.tagged}
                    max={listing.totals.items}
                    tone={listing.totals.untagged === 0 ? "success" : "warning"}
                  />
                  {listing.totals.untagged > 0 ? (
                    <button
                      onClick={() => {
                        setUntagged(true);
                        setPage(1);
                      }}
                      className="text-xs text-[var(--warning)] hover:underline"
                    >
                      Ver los {listing.totals.untagged} sin concepto →
                    </button>
                  ) : null}
                </>
              ) : (
                <Skeleton className="h-12" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-1.5">
                <CardTitle>Cobertura del currículo</CardTitle>
                <InfoHint label="Qué mide la cobertura">
                  Cuántos conceptos etiquetables tienen al menos un ítem del banco. Los que no lo
                  tienen se generan en zero-shot, sin ejemplo que imitar.
                </InfoHint>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {coverage.data ? (
                <>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-muted-foreground">Conceptos con ejemplo</span>
                    <span className="tabular-nums">
                      {coverage.data.covered}/{coverage.data.total}
                    </span>
                  </div>
                  <Progress value={coverage.data.covered} max={coverage.data.total} />
                </>
              ) : (
                <Skeleton className="h-12" />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-1.5">
                <CardTitle>Umbrales de recuperación</CardTitle>
                <InfoHint label="Qué controlan los umbrales">
                  Por debajo de la similitud mínima un ítem se queda sin candidatos y, por tanto,
                  sin concepto. El número de candidatos es cuántos conceptos del grafo llegan al
                  LLM para que decida entre ellos.
                </InfoHint>
              </div>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Similitud mínima</span>
                <span className="tabular-nums">{listing?.thresholds.similarity ?? "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Candidatos por ítem</span>
                <span className="tabular-nums">{listing?.thresholds.top_k ?? "—"}</span>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
              placeholder="Buscar en el enunciado o por id…"
              className="pl-8"
            />
          </div>
          <Select
            value={concept}
            onChange={(event) => {
              setConcept(event.target.value);
              setPage(1);
            }}
            className="max-w-56"
          >
            <option value="">Todos los conceptos</option>
            {concepts
              .filter((c) => c.taggable)
              .map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({c.exemplars})
                </option>
              ))}
          </Select>
          <Select
            value={source}
            onChange={(event) => {
              setSource(event.target.value);
              setPage(1);
            }}
            className="max-w-48"
          >
            <option value="">Todos los orígenes</option>
            {(listing?.sources ?? []).map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
          <Button
            variant={untagged === true ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setUntagged(untagged === true ? undefined : true);
              setPage(1);
            }}
          >
            <TriangleAlert />
            Sin concepto
          </Button>
          <Select
            value={order}
            onChange={(event) => setOrder(event.target.value as "suspicion" | "id")}
            className="max-w-56"
          >
            <option value="suspicion">Ordenar por sospecha</option>
            <option value="id">Ordenar por id</option>
          </Select>
        </div>

        {bank.isError ? (
          <Alert tone="danger" title="No se pudo leer el banco">
            <p>{(bank.error as Error).message}</p>
          </Alert>
        ) : null}

        {listing ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="w-8 py-2 pl-3" />
                  <th className="w-16 py-2 pl-2 font-medium">id</th>
                  <th className="py-2 pl-2 font-medium">{listing.primary_field}</th>
                  <th className="w-72 py-2 font-medium">conceptos</th>
                  <th className="w-24 py-2" />
                </tr>
              </thead>
              <tbody>
                {listing.items.map((item) => (
                  <ItemRow
                    key={item.id}
                    item={item}
                    primaryField={listing.primary_field}
                    selected={selected.has(item.id)}
                    onToggle={() => toggle(item.id)}
                    onEdit={() => setEditing(item)}
                    onDelete={() => {
                      if (window.confirm(`¿Eliminar el ítem ${item.id}?`)) remove.mutate(item.id);
                    }}
                  />
                ))}
              </tbody>
            </table>
            {listing.items.length === 0 ? (
              <p className="p-8 text-center text-sm text-muted-foreground">
                Ningún ítem con estos filtros.
              </p>
            ) : null}
          </div>
        ) : (
          <Skeleton className="h-96" />
        )}

        {listing && pages > 1 ? (
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {listing.total} ítem(s) · página {listing.page} de {pages}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
              >
                Anterior
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= pages}
                onClick={() => setPage((value) => value + 1)}
              >
                Siguiente
              </Button>
            </div>
          </div>
        ) : null}

        {selected.size > 0 ? (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-card p-3 text-sm">
            <span>{selected.size} ítem(s) seleccionados</span>
            <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
              Deseleccionar
            </Button>
            <Button
              size="sm"
              className="ml-auto"
              onClick={() => submit.mutate({ kind: "tag", params: { ids: [...selected] } })}
            >
              <RefreshCw />
              Re-etiquetar selección
            </Button>
          </div>
        ) : null}
      </div>

      {editing && listing ? (
        <ItemEditor
          item={editing}
          fields={listing.fields}
          primaryField={listing.primary_field}
          concepts={concepts}
          onClose={() => setEditing(null)}
          onSaved={() => {
            invalidate();
            bank.refetch();
            coverage.refetch();
          }}
        />
      ) : null}
    </StageGate>
  );
}

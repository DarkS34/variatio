import { useMutation } from "@tanstack/react-query";
import { Check, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Alert, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import type { KgSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useDescriptions, useSubmitJob } from "@/state/queries";

/**
 * Descriptions are not documentation: they are the text concept retrieval matches
 * against. A wrong one quietly mis-tags every item near it, which is why they get a
 * review step of their own before anything is indexed.
 */
export function DescriptionReview({ kg }: { kg: KgSummary }) {
  const query = useDescriptions();
  const submit = useSubmitJob();
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
  const described = kg.totals.taggable - missing.length;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-56 flex-1">
          <div className="mb-1 flex items-baseline justify-between text-xs">
            <span className="text-muted-foreground">Conceptos con descripción</span>
            <span className="tabular-nums">
              {described}/{kg.totals.taggable}
            </span>
          </div>
          <Progress
            value={described}
            max={kg.totals.taggable}
            tone={missing.length === 0 ? "success" : "warning"}
          />
        </div>

        <Button
          variant={missing.length > 0 ? "default" : "outline"}
          disabled={submit.isPending}
          onClick={() => submit.mutate({ kind: "describe_concepts", params: {}, force: true })}
        >
          {submit.isPending ? <Spinner /> : <Sparkles />}
          Generar las que faltan
        </Button>
        <Button
          variant="ghost"
          disabled={submit.isPending}
          title="Vuelve a escribir todas las descripciones desde cero"
          onClick={() =>
            submit.mutate({ kind: "describe_concepts", params: { overwrite: true }, force: true })
          }
        >
          <RefreshCw />
          Regenerar todas
        </Button>
        <Button
          variant="secondary"
          disabled={submit.isPending || missing.length > 0}
          title={
            missing.length > 0
              ? "Faltan descripciones: genéralas antes de indexar"
              : "Calcula los embeddings de los conceptos"
          }
          onClick={() => submit.mutate({ kind: "index", params: {}, force: true })}
        >
          Indexar conceptos
        </Button>
      </div>

      {missing.length > 0 ? (
        <Alert tone="warning" title={`${missing.length} concepto(s) sin descripción`}>
          <p>
            Sin descripción no hay vector con el que comparar: esos conceptos nunca saldrán como
            candidatos al etiquetar.
          </p>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filtrar por concepto o dominio…"
          className="max-w-72"
        />
        <Button
          size="sm"
          variant={onlyMissing ? "default" : "outline"}
          onClick={() => setOnlyMissing((value) => !value)}
        >
          <TriangleAlert />
          Solo sin descripción
        </Button>
        <span className="text-xs text-muted-foreground">{rows.length} concepto(s)</span>
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
                !stored && "border-[color-mix(in_oklch,var(--warning)_45%,var(--border))]",
              )}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">{concept.name}</span>
                <Badge variant="outline">{concept.domain}</Badge>
                {concept.exemplars > 0 ? (
                  <Badge variant="secondary">{concept.exemplars} ejemplos</Badge>
                ) : (
                  <Badge variant="warning">sin ejemplos</Badge>
                )}
                <div className="ml-auto flex items-center gap-2">
                  {saved[concept.name] ? (
                    <span className="flex items-center gap-1 text-xs text-[var(--success)]">
                      <Check className="size-3.5" />
                      guardada
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
                        Descartar
                      </Button>
                      <Button
                        size="sm"
                        disabled={save.isPending}
                        onClick={() =>
                          save.mutate({ concept: concept.name, description: value })
                        }
                      >
                        Guardar
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
              <Textarea
                value={value}
                onChange={(event) =>
                  setEdits((current) => ({ ...current, [concept.name]: event.target.value }))
                }
                placeholder="Sin descripción: se generará con el modelo o puedes escribirla aquí."
                className="min-h-20 text-sm"
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

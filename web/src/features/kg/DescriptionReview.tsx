import { useMutation } from "@tanstack/react-query";
import { Ban, Check, FileText, Hourglass, RefreshCw, Sparkles, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Textarea } from "@/components/ui/input";
import { Alert, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { hasExemplars } from "@/lib/concepts";
import { duration } from "@/lib/format";
import type { ConceptSource, KgSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useCancelJob,
  useDescriptions,
  useElapsed,
  useEngineOffline,
  useJobRun,
  useSubmitJob,
} from "@/state/queries";

/**
 * What the chain writes on its own, put where it can be read and corrected.
 *
 * The descriptions are NOT a manual step: `initialize` — and therefore «Indexar conceptos»,
 * and any generation — builds the `Embedder`, and the first thing it does is write the
 * description of every taggable concept that lacks one. This screen is where they are
 * reviewed and where a rewrite can be forced, not where they originate.
 *
 * Each is composed against the paragraphs of the theory corpus the concept came from
 * (`sources`), which is what is shown under the text: without that evidence a description is
 * what the model knew about the topic, and not what the syllabus says.
 */

/** What is happening while they are being written, on the screen where it was asked for. */
function WritingProgress() {
  const run = useJobRun("describe_concepts");
  const cancel = useCancelJob();
  const status = run?.job?.status;
  const active = status === "running" || status === "queued";
  const elapsed = useElapsed(run?.job?.started_at ?? null, active);

  if (!run || !active) return null;

  const step = run.steps.filter((s) => s.status === "running").at(-1);

  return (
    <Card>
      <CardContent className="space-y-2 py-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Spinner />
          <p className="text-body font-medium">{step?.label ?? run.job?.label}</p>
          <span className="flex items-center gap-1 text-small nums text-muted-foreground">
            <Hourglass className="size-3" />
            {duration(elapsed)}
          </span>
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            onClick={() => cancel.mutate(run.jobId)}
            disabled={cancel.isPending}
          >
            <Ban />
            Cancelar
          </Button>
        </div>
        {/* No bar: the header's is already this job's while it runs. Two stacked bars counting the
            same thing read as two different things. */}
        {/* Saved after each concept, so cancelling keeps what was written. Saying so here is what
            makes the button above not scary. */}
        <p className="truncate text-small text-muted-foreground">
          {step?.detail ?? "Preparando…"} · se guarda tras cada concepto, cancelar no pierde
          lo ya escrito
        </p>
      </CardContent>
    </Card>
  );
}

function SourcePassages({ sources, named }: { sources: ConceptSource[]; named: boolean }) {
  const [open, setOpen] = useState(false);

  if (sources.length === 0) {
    return (
      <p className="mt-2 flex items-center gap-1.5 text-small text-attention">
        <TriangleAlert className="size-3.5" />
        Sin respaldo en el corpus: se redactó solo con las relaciones del grafo.
      </p>
    );
  }

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-1.5 text-small text-muted-foreground transition-colors hover:text-foreground"
      >
        <FileText className="size-3.5" />
        {open ? "Ocultar" : "Ver"} el material del que sale ({sources.length})
      </button>
      {open ? (
        <div className="mt-2 space-y-2">
          {sources.map((source, index) => (
            <blockquote
              key={index}
              className="border-l-2 border-border bg-muted/40 px-3 py-2 text-small leading-relaxed"
            >
              {named || source.location ? (
                <p className="mb-1 font-mono text-[11px] text-muted-foreground">
                  {[named ? source.document : "", source.location]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              ) : null}
              <p className="whitespace-pre-wrap">{source.text}</p>
            </blockquote>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function DescriptionReview({ kg }: { kg: KgSummary }) {
  const query = useDescriptions();
  const submit = useSubmitJob();
  const offline = useEngineOffline();
  const run = useJobRun("describe_concepts");
  const writing = run?.job?.status === "running" || run?.job?.status === "queued";
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
  const sources = query.data?.sources ?? {};
  const unanchored = query.data?.unanchored ?? [];
  const namedDocuments = Boolean(query.data?.many_documents);
  const described = kg.totals.taggable - missing.length;

  /* One bar: while writing it counts the job, and the rest of the time the coverage. There
     were two, stacked and advancing together, which reads as two different measures when
     during a generation they are the same one. */
  const step = writing ? run?.steps.filter((s) => s.status === "running").at(-1) : undefined;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-56 flex-1">
          <div className="mb-1 flex items-baseline justify-between text-small">
            <span className="text-muted-foreground">
              {writing ? "Escribiendo descripciones" : "Conceptos con descripción"}
            </span>
            <span className="nums">
              {writing
                ? `${step?.current ?? 0}/${step?.total ?? kg.totals.taggable}`
                : `${described}/${kg.totals.taggable}`}
            </span>
          </div>
          {writing ? (
            <Progress value={step?.current ?? 0} max={step?.total ?? null} />
          ) : (
            <Progress
              value={described}
              max={kg.totals.taggable}
              tone={missing.length === 0 ? "settled" : "attention"}
            />
          )}
        </div>

        {/* The button stayed the same when pressed: `submit.isPending` only lasts as long as the
            POST, and from then on the job ran without this screen saying anything. What rules now is
            the job's state in the event stream, the same one that paints the bar below. */}
        <Button
          variant={missing.length > 0 ? "default" : "outline"}
          disabled={submit.isPending || writing || Boolean(offline)}
          title={offline ?? undefined}
          onClick={() => submit.mutate({ kind: "describe_concepts", params: {}, force: true })}
        >
          {submit.isPending || writing ? <Spinner /> : <Sparkles />}
          {writing ? "Escribiendo…" : "Generar las que faltan"}
        </Button>
        <Button
          variant="ghost"
          disabled={submit.isPending || writing || Boolean(offline)}
          title={offline ?? "Vuelve a escribir todas las descripciones desde cero"}
          onClick={() =>
            submit.mutate({ kind: "describe_concepts", params: { overwrite: true }, force: true })
          }
        >
          <RefreshCw />
          Regenerar todas
        </Button>
        <Button
          variant="secondary"
          disabled={submit.isPending || writing || Boolean(offline)}
          title={
            offline ??
            "Escribe las descripciones que falten y calcula los embeddings de los conceptos"
          }
          onClick={() => submit.mutate({ kind: "index", params: {}, force: true })}
        >
          Indexar conceptos
        </Button>
      </div>

      <WritingProgress />

      {/* Said once, visibly, and not behind an (i): it is the only sentence that explains why
          this tab exists and why nothing has to be pressed to have them. */}
      <p className="text-small leading-relaxed text-muted-foreground">
        Las descripciones son el texto contra el que se emparejan los ítems al etiquetar:
        un concepto sin ella no tiene vector y nunca sale como candidato. Se escriben solas
        al indexar, a partir de los párrafos del corpus de teoría en los que aparece cada
        concepto — los mismos que se pueden abrir debajo de cada texto. Los botones de
        arriba solo sirven para adelantarlo o para rehacerlo.
      </p>

      {missing.length > 0 && !writing ? (
        <Alert tone="attention" title={`${missing.length} concepto(s) sin descripción`} />
      ) : null}

      {unanchored.length > 0 ? (
        <Alert
          tone="attention"
          title={`${unanchored.length} concepto(s) sin respaldo en el corpus`}
          action={
            <InfoHint label="Qué significa sin respaldo">
              El anclaje lo escribe la construcción del grafo. Un concepto sin él, o bien se
              añadió a mano, o bien viene de un grafo construido antes de que esto existiera:
              su descripción se redacta solo con las relaciones. Reconstruir el grafo lo
              devuelve.
            </InfoHint>
          }
        />
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="Filtrar por concepto o dominio"
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
        <span className="text-small text-muted-foreground">{rows.length} concepto(s)</span>
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
                !stored && "border-[color-mix(in_oklch,var(--attention)_45%,var(--border))]",
              )}
            >
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="text-body font-medium">{concept.name}</span>
                <Badge variant="outline">{concept.domain}</Badge>
                {hasExemplars(concept) ? null : (
                  <Badge variant="attention">sin ejemplos</Badge>
                )}
                <div className="ml-auto flex items-center gap-2">
                  {saved[concept.name] ? (
                    <span className="flex items-center gap-1 text-small text-settled">
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
                aria-label={`Descripción de ${concept.name}`}
                value={value}
                onChange={(event) =>
                  setEdits((current) => ({ ...current, [concept.name]: event.target.value }))
                }
                placeholder="Sin descripción: se generará con el modelo o puedes escribirla aquí."
                className="min-h-20"
              />
              <SourcePassages
                sources={sources[concept.name] ?? []}
                named={namedDocuments}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

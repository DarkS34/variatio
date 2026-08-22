import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Save, X } from "lucide-react";
import { useMemo, useState } from "react";

import { ConceptSelector } from "@/components/ConceptSelector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, Skeleton, Switch } from "@/components/ui/misc";
import { adjacency, priors } from "@/features/run/prerequisites";
import { getCurriculum, putCurriculum } from "@/lib/api";
import { when } from "@/lib/format";
import { useKg, useKgGraph } from "@/state/queries";

const sorted = (names: string[]) => [...names].sort((a, b) => a.localeCompare(b, "es"));

// `adjacency()` returns null for two unrelated reasons — the graph declares no prerequisite
// relation, or there is no graph payload to read — and only the first one means that what
// is on screen is what will be saved. The server closes the prerequisites regardless, so
// promising otherwise while the request is failing is the one way to save a curriculum
// larger than the screen announced.
const NOTICE = {
  none: {
    tone: "attention",
    title: "El grafo no declara prerrequisitos",
    body: "Sin una relación de prerrequisito no hay nada que cerrar: se guardará exactamente lo que hayas elegido.",
  },
  loading: {
    tone: "info",
    title: "Todavía no se sabe qué prerrequisitos entrarán",
    body: "El grafo se está cargando. En cuanto llegue se listarán aquí, antes de guardar.",
  },
  error: {
    tone: "attention",
    title: "No se ha podido leer el grafo",
    body: "No se puede decir cuáles entrarán, pero al guardar el servidor los añadirá igualmente: el currículo guardado puede acabar siendo mayor que el que ves aquí. Vuelve a cargar la página, o apaga el cierre por prerrequisitos para guardar solo lo elegido.",
  },
} as const;

// Membership rather than a joined string: a concept name is free Spanish text, so any
// separator would be a guess about what cannot appear inside one.
const same = (a: string[], b: string[]) => {
  if (a.length !== b.length) return false;
  const set = new Set(a);
  return b.every((name) => set.has(name));
};

export function CurriculumTab() {
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
  const dirty = draft !== null && !same(draft, stored);
  const canSave = dirty || implied.length > 0 || dropped.length > 0;

  return (
    <div className="space-y-4">
      <Alert tone="info" title="Qué declara el currículo">
        <p>
          El temario ya impartido. Mientras esté definido, la generación se limita a estos
          conceptos y no introduce ninguno de fuera; vacío significa sin restricción, es decir
          todo el grafo. Un concepto no etiquetable también puede formar parte: aquí se declara
          cobertura, no objetivos.
        </p>
      </Alert>

      <Card>
        <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
          <div className="min-w-0">
            <CardTitle>Currículo ({selected.length} concepto(s))</CardTitle>
            <p className="mt-1 text-small text-muted-foreground">
              Guardado por última vez: {when(curriculum.data?.updated_at ?? null)}
              {dirty ? " · con cambios sin guardar" : null}
            </p>
          </div>
          <Button variant="outline" onClick={() => setPicking(true)}>
            <Pencil />
            Editar el currículo
          </Button>
        </CardHeader>
        <CardContent>
          {selected.length === 0 ? (
            <p className="text-body text-muted-foreground">
              Sin currículo: la generación puede usar cualquier concepto del grafo.
            </p>
          ) : (
            <div className="thin-scroll flex max-h-64 flex-wrap gap-1 overflow-y-auto">
              {sorted(selected).map((name) => (
                <Badge key={name} variant="secondary" className="pr-1">
                  {name}
                  <button
                    type="button"
                    aria-label={`Quitar ${name}`}
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
        <Alert tone="attention" title="Conceptos que ya no están en el grafo">
          <p>
            Estos estaban en el currículo y el grafo ya no los tiene, así que dejan de contar:{" "}
            {dropped.join(", ")}. Vuelve a guardar para quitarlos del fichero.
          </p>
        </Alert>
      ) : null}

      {closePrerequisites && implied.length > 0 ? (
        <Alert tone="info" title={`Al guardar entrarán ${implied.length} prerrequisito(s)`}>
          <p>{implied.join(", ")}.</p>
        </Alert>
      ) : null}

      {closePrerequisites && notice ? (
        <Alert tone={notice.tone} title={notice.title}>
          <p>{notice.body}</p>
        </Alert>
      ) : null}

      {error ? (
        <Alert tone="danger" title="No se pudo guardar el currículo">
          <p>{error}</p>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border p-3">
        <div className="flex items-center gap-2">
          <Switch
            checked={closePrerequisites}
            onCheckedChange={setClosePrerequisites}
            label="cerrar bajo prerrequisitos"
          />
          <div>
            <p className="text-body">Cerrar bajo prerrequisitos al guardar</p>
            <p className="text-small text-muted-foreground">
              Añade también todo aquello de lo que dependen los conceptos elegidos. Se propone
              antes de guardar; nada se añade sin que lo veas.
            </p>
          </div>
        </div>
        <Button disabled={!canSave || save.isPending} onClick={() => save.mutate()}>
          <Save />
          Guardar currículo
        </Button>
      </div>

      <ConceptSelector
        open={picking}
        onClose={() => setPicking(false)}
        title="Conceptos del currículo"
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

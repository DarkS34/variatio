import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, Pencil, Save, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { truncate } from "@/lib/format";
import { useCanEdit } from "@/state/auth";
import { keys, useContentContext } from "@/state/queries";

// The paragraph is paid for in every call the system makes and may reach 900 characters
// (`CONTENT_CONTEXT_MAX_CHARS`). On the panel it is read to recognise it, not to review it:
// in full it turned a card of the column into a wall. It is shown whole when editing.
const PREVIEW_CHARS = 200;

const FACT_LABEL: Record<string, string> = {
  subject: "Materia",
  educational_level: "Nivel",
  language_of_instruction: "Idioma",
};

/**
 * What subject this instance is about, in prose.
 *
 * It lives on the panel and not in a stage because it is not one: it has no raw data of its
 * own, no builder of its own, and it is not in `review.ARTIFACTS`. The graph and profile
 * builds synthesise it, each with what its artifact knows about the subject, and each
 * writes the DRAFT. What is edited here is the curated one, which wins on read — that pair
 * is what keeps a rebuild from rewriting what a person wrote.
 *
 * The three loose facts are neither decoration nor a leftover of the old format: the
 * evaluation's naive arm composes a sentence from them and cannot read the paragraph.
 */
export function ContextCard() {
  const query = useContentContext();
  const canEdit = useCanEdit();
  const client = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [narrative, setNarrative] = useState("");
  const [facts, setFacts] = useState<Record<string, string>>({});

  const data = query.data;

  useEffect(() => {
    if (!data || editing) return;
    setNarrative(data.narrative);
    setFacts(data.facts);
  }, [data, editing]);

  const refresh = () => client.invalidateQueries({ queryKey: keys.context });

  const save = useMutation({
    mutationFn: () => api.saveContext(narrative, facts),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });

  const adopt = useMutation({
    mutationFn: () => api.adoptContextDraft(),
    onSuccess: refresh,
  });

  if (query.isLoading) return <Skeleton className="h-40" />;
  if (!data) return null;

  const factKeys = Array.from(new Set([...data.canonical_keys, ...Object.keys(facts)]));

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="size-4 text-muted-foreground" />
            La asignatura
          </CardTitle>
          {data.source ? (
            <Badge variant="outline" className="ml-auto">
              {data.source === "curated" ? "curado" : "borrador"}
            </Badge>
          ) : null}
        </div>
        <p className="text-small text-muted-foreground">
          Se interpola en todos los prompts del sistema: fija la materia, el nivel y el idioma
          de lo que se genera. Lo escriben las construcciones del grafo y del perfil; lo que
          guardes aquí manda sobre lo que escriban.
        </p>
      </CardHeader>

      <CardContent className="space-y-3">
        {!data.exists && !editing ? (
          <Alert tone="attention" title="Todavía no hay contexto">
            <p>
              Ningún prompt sabe de qué materia se trata. Lo sintetiza la próxima construcción
              del grafo o del perfil, o puedes escribirlo tú ahora.
            </p>
          </Alert>
        ) : null}

        {editing ? (
          <>
            <Field
              label="En prosa"
              description="Una o dos frases: qué materia es, a quién se dirige, en qué idioma y con qué convenciones. Nada de listas."
            >
              <Textarea
                value={narrative}
                onChange={(event) => setNarrative(event.target.value)}
                className="min-h-28 text-small"
                placeholder="Introducción a la Programación, asignatura de primer curso…"
              />
            </Field>

            <div className="grid gap-2 sm:grid-cols-3">
              {factKeys.map((key) => (
                <Field key={key} label={FACT_LABEL[key] ?? key}>
                  <Input
                    value={facts[key] ?? ""}
                    className="h-8"
                    onChange={(event) =>
                      setFacts((current) => ({ ...current, [key]: event.target.value }))
                    }
                  />
                </Field>
              ))}
            </div>
            <p className="text-small text-muted-foreground">
              Estos tres se leen por separado para la rama de referencia de la evaluación, que
              no puede usar el párrafo. Deben decir lo mismo que él.
            </p>

            <div className="flex gap-2">
              <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
                {save.isPending ? <Spinner /> : <Save />}
                Guardar
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                <X />
                Cancelar
              </Button>
            </div>
          </>
        ) : (
          <>
            {data.narrative ? (
              <p className="text-body" title={data.narrative}>
                {truncate(data.narrative, PREVIEW_CHARS)}
              </p>
            ) : data.block ? (
              <pre className="whitespace-pre-wrap font-mono text-small text-muted-foreground">
                {truncate(data.block, PREVIEW_CHARS)}
              </pre>
            ) : null}

            {canEdit ? (
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                  <Pencil />
                  {data.exists ? "Editar" : "Escribirlo"}
                </Button>
                {/* A build always writes the draft, so with a curated context the latest synthesis sits
                    there unread. The notice that said so with the whole text inside left the panel; what
                    stays is the way to adopt it, the one thing that cannot be done from anywhere else. */}
                {data.pending_draft ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => adopt.mutate()}
                    disabled={adopt.isPending}
                    title="Sustituye este texto por la síntesis de la última construcción"
                  >
                    {adopt.isPending ? <Spinner /> : <Check />}
                    Adoptar el borrador
                  </Button>
                ) : null}
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

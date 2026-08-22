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
import { useCanEdit } from "@/state/auth";
import { keys, useContentContext } from "@/state/queries";

const FACT_LABEL: Record<string, string> = {
  subject: "Materia",
  educational_level: "Nivel",
  language_of_instruction: "Idioma",
};

/**
 * De qué asignatura es esta instancia, en prosa.
 *
 * Vive en el panel y no en una etapa porque no es una: no tiene datos en bruto propios ni
 * constructor propio, y no está en `review.ARTIFACTS`. Lo sintetizan las construcciones del
 * grafo y del perfil, cada una con lo que su artefacto sabe de la asignatura, y cada una
 * escribe el BORRADOR. Lo que se edita aquí es el curado, que es el que manda al leer —
 * ese par es lo que impide que una reconstrucción reescriba lo que escribió una persona.
 *
 * Los tres datos sueltos no son decoración ni un resto del formato viejo: la rama naive de
 * la evaluación compone una frase con ellos y no puede leer el párrafo.
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
              <p className="text-body">{data.narrative}</p>
            ) : data.block ? (
              <pre className="whitespace-pre-wrap font-mono text-small text-muted-foreground">
                {data.block}
              </pre>
            ) : null}

            {canEdit ? (
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                <Pencil />
                {data.exists ? "Editar" : "Escribirlo"}
              </Button>
            ) : null}
          </>
        )}

        {/* Una construcción siempre escribe el borrador, así que con un contexto curado la
            última síntesis queda ahí sin leerse. Decirlo es justo para lo que sirve tener
            los dos ficheros: si no, reconstruir parecería no haber hecho nada. */}
        {data.pending_draft && !editing ? (
          <Alert tone="info" title="La última construcción escribió otra versión">
            <p className="text-small">{data.pending_draft}</p>
            {canEdit ? (
              <Button
                size="sm"
                variant="outline"
                className="mt-2"
                onClick={() => adopt.mutate()}
                disabled={adopt.isPending}
              >
                {adopt.isPending ? <Spinner /> : <Check />}
                Adoptarla
              </Button>
            ) : null}
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  );
}

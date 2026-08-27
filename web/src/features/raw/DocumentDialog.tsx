import { CircleAlert, CircleSlash, Plus, Save, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { Alert, EmptyState, Skeleton, Spinner } from "@/components/ui/misc";
import { truncate } from "@/lib/format";
import type { RawKind } from "@/lib/types";
import { cn } from "@/lib/utils";

import { useDocumentPages, usePageActions } from "./queries";
import type { DocumentPage } from "./types";

const FAILED_MARK = "> [TRANSCRIPCIÓN FALLIDA";

type PageMark = "failed" | "empty" | "ok";

function pageMark(page: DocumentPage): PageMark {
  if (page.failed) return "failed";
  return page.text.trim() ? "ok" : "empty";
}

function draftMark(text: string): PageMark {
  if (text.trimStart().startsWith(FAILED_MARK)) return "failed";
  return text.trim() ? "ok" : "empty";
}

const MARK_LABEL: Record<PageMark, string> = {
  failed: "fallida",
  empty: "vacía",
  ok: "",
};

function PageMarkBadge({ mark }: { mark: PageMark }) {
  if (mark === "failed") {
    return (
      <Badge variant="danger" mark={<CircleAlert />}>
        {MARK_LABEL.failed}
      </Badge>
    );
  }
  if (mark === "empty") {
    return (
      <Badge variant="attention" mark={<CircleSlash />}>
        {MARK_LABEL.empty}
      </Badge>
    );
  }
  return null;
}

export function DocumentDialog({
  kind,
  name,
  onClose,
}: {
  kind: RawKind;
  name: string;
  onClose: () => void;
}) {
  const listing = useDocumentPages(kind, name);
  const { save, insert, remove } = usePageActions(kind, name);

  const [selected, setSelected] = useState(1);
  const [draft, setDraft] = useState<string | null>(null);

  const pages = listing.data?.pages ?? [];
  const current = pages.find((page) => page.index === selected) ?? pages[0] ?? null;
  const shown = current?.index ?? selected;
  const original = current?.text ?? "";
  const text = draft ?? original;
  const dirty = draft !== null && draft !== original;
  const working = save.isPending || insert.isPending || remove.isPending;

  const attention = pages.filter((page) => pageMark(page) !== "ok").length;

  const goTo = (index: number) => {
    if (index === shown) return;
    if (
      dirty &&
      !window.confirm(
        `Hay cambios sin guardar en la página ${shown}. ¿Descartarlos y cambiar de página?`,
      )
    ) {
      return;
    }
    setDraft(null);
    setSelected(index);
  };

  const attemptClose = () => {
    if (
      dirty &&
      !window.confirm(
        `Hay cambios sin guardar en la página ${shown}. ¿Cerrar y descartarlos?`,
      )
    ) {
      return;
    }
    setDraft(null);
    onClose();
  };

  const onSave = () =>
    save.mutate({ index: shown, text }, { onSuccess: () => setDraft(null) });

  const onInsert = () =>
    insert.mutate(
      { after: shown, text: "" },
      {
        onSuccess: (data) => {
          setDraft(null);
          setSelected(data.index);
        },
      },
    );

  const onDelete = () => {
    if (
      !window.confirm(
        `¿Borrar la página ${shown} de «${name}»? Las siguientes se renumeran.`,
      )
    ) {
      return;
    }
    remove.mutate(shown, {
      onSuccess: (data) => {
        setDraft(null);
        setSelected(Math.max(1, Math.min(shown, data.pages.length)));
      },
    });
  };

  return (
    <Dialog
      open
      onClose={attemptClose}
      title={name}
      description="Lo que corrijas aquí gana sobre lo que dijo el modelo: las construcciones siguientes leen estas páginas del disco, no vuelven a preguntarle."
      className="sm:max-w-[80rem]"
      footer={
        pages.length > 0 ? (
          <>
            <p className="mr-auto text-small text-muted-foreground">
              {dirty
                ? `Página ${shown} con cambios sin guardar.`
                : `Página ${shown} de ${pages.length}.`}
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={onDelete}
              disabled={working || pages.length === 1}
              title={
                pages.length === 1
                  ? "Es la única página del documento."
                  : "Borra esta página y renumera las siguientes."
              }
            >
              {remove.isPending ? <Spinner /> : <Trash2 />}
              Borrar página
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={onInsert}
              disabled={working}
              title="Añade una página en blanco justo después de esta y renumera las siguientes."
            >
              {insert.isPending ? <Spinner /> : <Plus />}
              Insertar después
            </Button>
            <Button size="sm" onClick={onSave} disabled={!dirty || working}>
              {save.isPending ? <Spinner /> : <Save />}
              Guardar página
            </Button>
          </>
        ) : null
      }
    >
      {listing.isLoading ? (
        <Skeleton className="h-[60vh]" />
      ) : !listing.data ? (
        <Alert tone="danger" title="No se pudieron leer las páginas">
          <p>
            El servidor no respondió a la transcripción de «{name}». Vuelve a abrirlo dentro
            de un momento.
          </p>
        </Alert>
      ) : pages.length === 0 ? (
        <EmptyState title="Todavía no hay páginas">
          <p>
            Este documento no se ha transcrito aún. Lánzala desde «Transcripción», en datos
            en bruto, y vuelve aquí a revisar el resultado.
          </p>
        </EmptyState>
      ) : (
        <div className="flex h-[68vh] flex-col gap-3 lg:flex-row lg:gap-4">
          <div className="flex max-h-[38%] w-full shrink-0 flex-col overflow-hidden rounded-lg border border-border lg:max-h-none lg:w-[19rem]">
            <div className="space-y-1 border-b border-border p-2.5">
              <div className="flex items-center gap-2">
                <span className="text-micro font-condensed uppercase text-muted-foreground">
                  Páginas ({pages.length})
                </span>
                {attention > 0 ? (
                  <Badge variant="attention" className="ml-auto">
                    {attention} por revisar
                  </Badge>
                ) : null}
              </div>
              <p className="text-small leading-relaxed text-muted-foreground">
                Van numeradas: borrar o insertar una renumera las siguientes.
              </p>
            </div>
            <ul className="thin-scroll min-h-0 flex-1 divide-y divide-border overflow-y-auto">
              {pages.map((page) => {
                const mark = pageMark(page);
                return (
                  <li key={page.index}>
                    <button
                      type="button"
                      onClick={() => goTo(page.index)}
                      className={cn(
                        "flex w-full flex-col gap-0.5 px-2.5 py-2 text-left transition-colors hover:bg-accent/60",
                        page.index === shown && "bg-accent",
                      )}
                    >
                      <span className="flex items-center gap-2">
                        <span
                          className={cn(
                            "text-body font-medium nums",
                            page.index === shown && "font-expanded",
                          )}
                        >
                          Página {page.index}
                        </span>
                        <PageMarkBadge mark={mark} />
                      </span>
                      <span className="truncate text-small text-muted-foreground">
                        {mark === "empty"
                          ? "Sin contenido"
                          : truncate(page.text.replace(/\s+/g, " ").trim(), 64)}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
            {draftMark(text) === "failed" ? (
              <Alert tone="danger" title="La transcripción de esta página falló">
                <p>
                  El modelo no devolvió nada utilizable y se dejó este aviso en su lugar.
                  Escribe aquí lo que hubiera en la página del documento original.
                </p>
              </Alert>
            ) : draftMark(text) === "empty" ? (
              <Alert tone="attention" title="Página en blanco">
                <p>
                  Puede ser una página realmente vacía del original —una portada, un
                  separador— o algo que el modelo no supo leer. Compruébalo antes de
                  construir.
                </p>
              </Alert>
            ) : null}

            <Field
              label={`Markdown de la página ${shown}`}
              className="min-h-0 flex-1"
              description="Se guarda tal cual, sin reformatear."
            >
              {(props) => (
                <Textarea
                  {...props}
                  value={text}
                  onChange={(event) => setDraft(event.target.value)}
                  spellCheck={false}
                  className="min-h-0 flex-1 font-mono leading-relaxed"
                />
              )}
            </Field>
          </div>
        </div>
      )}
    </Dialog>
  );
}

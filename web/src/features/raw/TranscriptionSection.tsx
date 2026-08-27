import { Ban, FileText, Hammer, Hourglass, PenLine, RefreshCw } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, PhaseBar, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import type { RawSlot } from "@/lib/types";
import { useCanEdit } from "@/state/auth";
import { useCancelJob, useEngineOffline } from "@/state/queries";

import { DocumentDialog } from "./DocumentDialog";
import { busyDocument, documentLoop, innerLoop, loopLabel } from "./progress";
import {
  useStartTranscription,
  useTranscribePhases,
  useTranscribeRun,
  useTranscribing,
  useTranscription,
} from "./queries";
import type { DocumentState } from "./types";

const STATE: Record<
  DocumentState,
  { label: string; variant: "settled" | "outline" | "attention" }
> = {
  done: { label: "transcrito", variant: "settled" },
  pending: { label: "pendiente", variant: "outline" },
  stale: { label: "caducado", variant: "attention" },
};

function launchLabel(pending: number, stale: number, done: number): string {
  if (stale > 0 && pending > 0) return "Transcribir lo pendiente y lo caducado";
  if (stale > 0) return "Volver a transcribir lo caducado";
  if (done > 0) return "Transcribir lo pendiente";
  return "Comenzar transcripción";
}

function SlotTranscription({ slot }: { slot: RawSlot }) {
  const hasFiles = slot.files.length > 0;
  const state = useTranscription(slot.kind, hasFiles);
  const run = useTranscribeRun(slot.kind);
  const running = useTranscribing(slot.kind);
  const phases = useTranscribePhases();
  const start = useStartTranscription();
  const cancel = useCancelJob();
  const offline = useEngineOffline();
  const canEdit = useCanEdit();
  const [opened, setOpened] = useState<string | null>(null);

  const data = state.data;
  const todo = (data?.pending ?? 0) + (data?.stale ?? 0);
  const overall = run?.overall ?? null;
  const queued = run?.job?.status === "queued";
  // Two nested loops, drawn as two bars: which document of how many, and how far into that
  // document's pages (or, once they are done, into its seams).
  const docs = documentLoop(run);
  const inner = innerLoop(run);
  // The one document nobody may correct while this runs: the transcriber rewrites its whole
  // directory at the end, so an edit saved into it now would be discarded without a word.
  const busy = busyDocument(run);

  const reason = !canEdit
    ? "Tu permiso sobre esta instancia es de solo lectura."
    : offline
      ? offline
      : running
        ? "Ya se está transcribiendo este origen."
        : start.isPending
          ? "Enviando…"
          : todo === 0
            ? "Todos los documentos están transcritos y al día."
            : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <FileText className="size-4 shrink-0 text-muted-foreground" />
          <CardTitle className="flex-1">{slot.label}</CardTitle>
          {data ? (
            data.stale > 0 ? (
              <Badge variant="attention">{data.stale} caducado(s)</Badge>
            ) : data.pending > 0 ? (
              <Badge variant="outline">{data.pending} pendiente(s)</Badge>
            ) : (
              <Badge variant="settled">al día</Badge>
            )
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {!hasFiles ? (
          <p className="text-small text-muted-foreground">
            Sin documentos que transcribir. Importa algo arriba y aparecerá aquí.
          </p>
        ) : state.isLoading ? (
          <Skeleton className="h-24" />
        ) : !data ? (
          <Alert tone="danger" title="No se pudo leer el estado de la transcripción">
            <p>El servidor no respondió a /api/raw/{slot.kind}/transcription.</p>
          </Alert>
        ) : (
          <>
            <p className="text-small nums text-muted-foreground">
              {data.documents.length} documento(s)
              {data.total_pages > 0 ? ` · ${data.total_pages} página(s)` : ""} · una llamada
              al modelo por página
            </p>

            <Button
              size="sm"
              variant={data.stale > 0 && data.pending === 0 ? "outline" : "default"}
              disabled={Boolean(reason)}
              title={
                reason ??
                (data.done > 0
                  ? "Transcribe a markdown lo que falta; lo que ya está al día se reutiliza."
                  : "Transcribe los documentos a markdown, página a página, y guarda cada página para que puedas corregirla.")
              }
              onClick={() => start.mutate(slot.kind)}
            >
              {start.isPending ? (
                <Spinner />
              ) : data.stale > 0 ? (
                <RefreshCw />
              ) : (
                <Hammer />
              )}
              {launchLabel(data.pending, data.stale, data.done)}
            </Button>

            {running ? (
              <div className="space-y-2 rounded-md border border-border p-2.5">
                <div className="flex items-center gap-2">
                  {queued ? (
                    <Hourglass className="size-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <Spinner className="shrink-0" />
                  )}
                  <span className="min-w-0 flex-1 truncate text-small">
                    {queued
                      ? "En cola: esperando a que se libere el motor"
                      : (overall?.label ?? docs?.label ?? "Preparando la transcripción…")}
                  </span>
                  {docs ? (
                    <span className="shrink-0 text-small font-medium nums">
                      {loopLabel(docs)} doc.
                    </span>
                  ) : null}
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={cancel.isPending || !run?.job}
                    title="Detiene la transcripción donde va. Las páginas ya guardadas se conservan y al volver a lanzarla se reanuda por donde quedó."
                    onClick={() => run?.job && cancel.mutate(run.job.id)}
                  >
                    <Ban />
                    Detener
                  </Button>
                </div>

                {!queued ? (
                  <>
                    {overall && phases.length > 0 ? (
                      <PhaseBar
                        phases={phases}
                        percent={overall.percent}
                        activeKey={overall.key}
                      />
                    ) : (
                      <Progress value={overall?.percent ?? 0} max={100} />
                    )}
                    {overall?.detail ? (
                      <p className="truncate text-small text-muted-foreground">
                        {overall.detail}
                      </p>
                    ) : null}

                    {/* The inner loop, drawn as its own bar: the outer one moves once per
                        document, so on a corpus of long PDFs it would sit still for as long
                        as it takes to read one — which reads as a stall and is not. */}
                    {inner ? (
                      <div className="space-y-1 border-l-2 border-border pl-2.5">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="min-w-0 truncate text-small text-muted-foreground">
                            {inner.detail ?? inner.label}
                          </span>
                          <span className="shrink-0 nums text-small text-muted-foreground">
                            {loopLabel(inner)}
                          </span>
                        </div>
                        <Progress value={inner.current} max={inner.total} />
                      </div>
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}

            {data.documents.length > 0 ? (
              <ul className="divide-y divide-border rounded-md border border-border">
                {data.documents.map((entry) => (
                  <li key={entry.name} className="space-y-0.5 px-2 py-1.5">
                    <div className="flex items-center gap-2 text-small">
                      {busy === entry.name ? <Spinner className="size-3.5 shrink-0" /> : null}
                      <span className="min-w-0 flex-1 truncate" title={entry.name}>
                        {entry.name}
                      </span>
                      {entry.pages > 0 ? (
                        <span className="shrink-0 nums text-muted-foreground">
                          {entry.pages} pág.
                        </span>
                      ) : null}
                      <Badge
                        variant={
                          busy === entry.name ? "outline" : STATE[entry.state].variant
                        }
                      >
                        {busy === entry.name ? "transcribiendo" : STATE[entry.state].label}
                      </Badge>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        aria-label={`Ver y corregir las páginas de ${entry.name}`}
                        title={
                          busy === entry.name
                            ? "Se está reescribiendo ahora mismo; lo que corrigieras aquí se perdería al terminar"
                            : entry.state === "pending"
                              ? "Todavía no hay páginas que ver"
                              : "Ver y corregir las páginas"
                        }
                        disabled={entry.state === "pending" || busy === entry.name}
                        onClick={() => setOpened(entry.name)}
                      >
                        <PenLine />
                      </Button>
                    </div>
                    {entry.reason ? (
                      <p className="text-small text-attention">{entry.reason}</p>
                    ) : null}
                    {entry.failed_pages > 0 ? (
                      <p className="text-small text-destructive">
                        {entry.failed_pages} página(s) que el modelo no pudo transcribir.
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </>
        )}
      </CardContent>

      {opened ? (
        <DocumentDialog
          key={opened}
          kind={slot.kind}
          name={opened}
          onClose={() => setOpened(null)}
        />
      ) : null}
    </Card>
  );
}

export function TranscriptionSection({ slots }: { slots: RawSlot[] }) {
  if (!slots.some((slot) => slot.files.length > 0)) return null;

  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h3 className="font-display font-expanded text-heading">Transcripción</h3>
        <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
          Pasar los documentos a markdown es lo primero que hace cada construcción, y es
          trabajo mecánico: hacerlo aquí una vez lo saca del principio del grafo, del perfil
          y del banco. Cada página se guarda por separado, así que lo que corrijas a mano
          gana sobre lo que dijo el modelo y sobrevive a las construcciones siguientes.
        </p>
        <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
          No es un requisito: si construyes sin haber transcrito, la construcción lo hará
          por su cuenta, como hasta ahora. Y si cambia el modelo de transcripción, el DPI,
          el OCR o el prompt, las páginas quedan marcadas como caducadas con el motivo, en
          vez de rehacerse en silencio.
        </p>
        <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
          Se puede detener en cualquier momento: lo que ya se guardó se queda, y al volver a
          lanzarla sigue por donde iba. Los documentos que ya han salido pueden revisarse y
          corregirse mientras el resto se transcribe; el único que no se deja abrir es el
          que se está reescribiendo en ese instante.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {slots.map((slot) => (
          <SlotTranscription key={slot.kind} slot={slot} />
        ))}
      </div>
    </section>
  );
}

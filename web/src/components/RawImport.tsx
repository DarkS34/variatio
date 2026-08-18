import { useQueryClient } from "@tanstack/react-query";
import { FileText, FolderOpen, Trash2, UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, Progress, Skeleton } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { bytes } from "@/lib/format";
import type { RawSlot } from "@/lib/types";
import { cn } from "@/lib/utils";
import { keys, useRaw } from "@/state/queries";

/**
 * The way in for a first-time instance.
 *
 * `raw_base_data/` is the user's own data and lives outside the package, so an empty
 * folder used to be a dead end: nothing in the UI could build anything and the only
 * fix was a file manager. Dropping documents here is the missing first step of the
 * chain — it writes nothing but files, and every build reads them from disk.
 */

const FEEDS: Record<string, string> = {
  exemplars_profile: "Perfil",
  knowledge_graph: "Grafo",
  exemplars_bank: "Banco",
};

const VISIBLE_FILES = 6;

function accepts(name: string, extensions: string[]) {
  const dot = name.lastIndexOf(".");
  return dot > 0 && extensions.includes(name.slice(dot).toLowerCase());
}

function SlotCard({ slot, extensions }: { slot: RawSlot; extensions: string[] }) {
  const client = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  const refresh = () => {
    client.invalidateQueries({ queryKey: keys.raw });
    client.invalidateQueries({ queryKey: keys.health });
  };

  const send = async (list: FileList | File[] | null) => {
    const files = Array.from(list ?? []);
    if (files.length === 0) return;

    const valid = files.filter((file) => accepts(file.name, extensions));
    const invalid = files.filter((file) => !accepts(file.name, extensions));

    setError(null);
    setNotice(null);
    if (valid.length === 0) {
      setError(`Ningún archivo admitido. Se aceptan: ${extensions.join(", ")}.`);
      return;
    }

    setProgress(0);
    try {
      const result = await api.uploadRaw(slot.kind, valid, setProgress);
      const renamed = result.added.filter((file) => file.renamed);
      const parts = [`${result.added.length} archivo(s) importado(s)`];
      if (renamed.length > 0) parts.push(`${renamed.length} renombrado(s) por nombre repetido`);
      if (invalid.length > 0) parts.push(`${invalid.length} descartado(s) por extensión`);
      for (const item of result.rejected) parts.push(`${item.name}: ${item.reason}`);
      setNotice(parts.join(" · "));
      refresh();
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setProgress(null);
    }
  };

  const remove = async (name: string) => {
    if (!window.confirm(`¿Eliminar "${name}" de ${slot.label.toLowerCase()}?`)) return;
    setError(null);
    try {
      await api.deleteRaw(slot.kind, name);
      setNotice(`"${name}" eliminado.`);
      refresh();
    } catch (exception) {
      setError((exception as Error).message);
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    send(event.dataTransfer.files);
  };

  const empty = slot.files.length === 0;
  const visible = expanded ? slot.files : slot.files.slice(0, VISIBLE_FILES);

  return (
    <Card className={cn(empty && "border-[color-mix(in_oklch,var(--warning)_45%,var(--border))]")}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <FolderOpen className="size-4 shrink-0 text-muted-foreground" />
          <CardTitle className="flex-1">{slot.label}</CardTitle>
          {empty ? (
            <Badge variant="warning">vacío</Badge>
          ) : (
            <Badge variant="outline">
              {slot.files.length} archivo(s) · {bytes(slot.bytes)}
            </Badge>
          )}
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">{slot.purpose}</p>
        <div className="flex flex-wrap items-center gap-1 pt-0.5">
          <span className="text-[11px] text-muted-foreground">Alimenta:</span>
          {slot.feeds.map((artifact) => (
            <Badge key={artifact} variant="secondary">
              {FEEDS[artifact] ?? artifact}
            </Badge>
          ))}
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => input.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") input.current?.click();
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border border-dashed p-6 text-center transition-colors",
            dragging
              ? "border-primary bg-primary/10"
              : "border-border hover:border-primary/60 hover:bg-accent/50",
          )}
        >
          <UploadCloud
            className={cn("size-6", dragging ? "text-primary" : "text-muted-foreground")}
          />
          <p className="text-sm font-medium">
            {dragging ? "Suelta aquí los documentos" : "Arrastra documentos o haz clic"}
          </p>
          <p className="text-xs text-muted-foreground">{extensions.join(" · ")}</p>
          <input
            ref={input}
            type="file"
            multiple
            accept={extensions.join(",")}
            className="hidden"
            onChange={(event) => {
              send(event.target.files);
              event.target.value = "";
            }}
          />
        </div>

        {progress !== null ? (
          <div className="space-y-1">
            <Progress value={progress * 100} max={100} />
            <p className="text-xs text-muted-foreground">
              Subiendo… {Math.round(progress * 100)}%
            </p>
          </div>
        ) : null}

        {error ? <p className="text-xs text-destructive">{error}</p> : null}
        {notice ? <p className="text-xs text-muted-foreground">{notice}</p> : null}

        {empty ? null : (
          <ul className="divide-y divide-border rounded-md border border-border">
            {visible.map((file) => (
              <li key={file.name} className="flex items-center gap-2 px-2 py-1.5 text-xs">
                <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate" title={file.name}>
                  {file.name}
                </span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {bytes(file.bytes)}
                </span>
                <button
                  type="button"
                  aria-label={`Eliminar ${file.name}`}
                  title="Eliminar del origen"
                  onClick={() => remove(file.name)}
                  className="shrink-0 text-muted-foreground transition-colors hover:text-destructive"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
            {slot.files.length > VISIBLE_FILES ? (
              <li className="px-2 py-1.5">
                <button
                  type="button"
                  onClick={() => setExpanded((value) => !value)}
                  className="text-xs text-muted-foreground transition-colors hover:text-foreground"
                >
                  {expanded
                    ? "Ver menos"
                    : `Ver los ${slot.files.length - VISIBLE_FILES} restantes`}
                </button>
              </li>
            ) : null}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function RawImport() {
  const raw = useRaw();

  if (raw.isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!raw.data) {
    return (
      <Alert tone="danger" title="No se pudieron leer los datos en bruto">
        <p>La API no respondió a /api/raw.</p>
      </Alert>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {raw.data.slots.map((slot) => (
        <SlotCard key={slot.kind} slot={slot} extensions={raw.data.supported_extensions} />
      ))}
    </div>
  );
}


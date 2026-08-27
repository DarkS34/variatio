import { useQueryClient } from "@tanstack/react-query";
import { FileText, Trash2, UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";

import { Progress } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { bytes } from "@/lib/format";
import type { RawSlot } from "@/lib/types";
import { cn } from "@/lib/utils";
import { keys, useRaw } from "@/state/queries";
import { useT } from "@/lib/i18n";

/**
 * The way in for a first-time instance.
 *
 * `raw/` is the user's own data and lives outside the package, so an empty folder used to
 * be a dead end: nothing in the UI could build anything and the only fix was a file
 * manager. Dropping documents here is the missing first step of the chain — it writes
 * nothing but files, and every build reads them from disk.
 *
 * This is the FILES half of a raw slot and nothing else. It used to be a card of its own,
 * with the slot's name, its purpose, what it feeds and a six-file list, sitting in a grid
 * beside a second card that spoke about the same slot's transcription — so one origin was
 * two boxes on two different rows of the panel. The slot is now one row (`features/raw`'s
 * `RawSection`), and this is what that row reveals when it is opened.
 */

const VISIBLE_FILES = 6;

function accepts(name: string, extensions: string[]) {
  const dot = name.lastIndexOf(".");
  return dot > 0 && extensions.includes(name.slice(dot).toLowerCase());
}

export function SlotFiles({ slot, extensions }: { slot: RawSlot; extensions: string[] }) {
  const { t, plural } = useT();
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
      setError(t("raw.noneAccepted", { extensions: extensions.join(", ") }));
      return;
    }

    setProgress(0);
    try {
      const result = await api.uploadRaw(slot.kind, valid, setProgress);
      const renamed = result.added.filter((file) => file.renamed);
      const parts = [plural("raw.imported", result.added.length)];
      if (renamed.length > 0) parts.push(plural("raw.renamed", renamed.length));
      if (invalid.length > 0) parts.push(plural("raw.invalid", invalid.length));
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
    if (!window.confirm(t("raw.confirmDelete", { name, slot: slot.label.toLowerCase() }))) return;
    setError(null);
    try {
      await api.deleteRaw(slot.kind, name);
      setNotice(t("raw.removed", { name }));
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
    <div className="space-y-3">
      {/* Roomy while the slot is empty — there it IS the screen's next step — and one line
          tall once there are files, where it is the way to add one more. */}
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
          "flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed text-center transition-colors",
          empty ? "flex-col gap-1.5 p-6" : "p-3",
          dragging
            ? "border-primary bg-primary/10"
            : "border-border hover:border-primary/60 hover:bg-accent/50",
        )}
      >
        <UploadCloud
          className={cn(empty ? "size-6" : "size-4", dragging ? "text-primary" : "text-muted-foreground")}
        />
        <p className="text-body font-medium">{dragging ? t("raw.drop") : t("raw.dropOrClick")}</p>
        <p className="text-small text-muted-foreground">{extensions.join(" · ")}</p>
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
          <p className="text-small text-muted-foreground">
            {t("raw.uploading", { pct: Math.round(progress * 100) })}
          </p>
        </div>
      ) : null}

      {error ? <p className="text-small text-destructive">{error}</p> : null}
      {notice ? <p className="text-small text-muted-foreground">{notice}</p> : null}

      {empty ? null : (
        <ul className="divide-y divide-border rounded-md border border-border">
          {visible.map((file) => (
            <li key={file.name} className="flex items-center gap-2 px-2 py-1.5 text-small">
              <FileText className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate" title={file.name}>
                {file.name}
              </span>
              <span className="shrink-0 nums text-muted-foreground">{bytes(file.bytes)}</span>
              <button
                type="button"
                aria-label={t("raw.deleteFile", { name: file.name })}
                title={t("raw.deleteFromSlot")}
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
                className="text-small text-muted-foreground transition-colors hover:text-foreground"
              >
                {expanded ? t("raw.showLess") : plural("raw.showRest", slot.files.length - VISIBLE_FILES)}
              </button>
            </li>
          ) : null}
        </ul>
      )}
    </div>
  );
}

/** The extensions every slot accepts, read once by the row that renders the slots. */
export function useRawExtensions(): string[] {
  const raw = useRaw();
  return raw.data?.supported_extensions ?? [];
}

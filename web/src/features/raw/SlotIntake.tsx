import { useQueryClient } from "@tanstack/react-query";
import { UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";

import { Progress } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useConfirm } from "@/components/ui/confirm";
import { useT } from "@/lib/i18n";
import { slotLabel } from "@/lib/raw";
import type { RawSlot } from "@/lib/types";
import { cn } from "@/lib/utils";
import { keys, useRaw } from "@/state/queries";

/**
 * THE WAY IN FOR A FIRST-TIME INSTANCE, and only that.
 *
 * `raw/` is the user's own data and lives outside the package, so an empty folder used to
 * be a dead end: nothing in the UI could build anything and the only fix was a file
 * manager. Dropping documents here is the missing first step of the chain — it writes
 * nothing but files, and every build reads them from disk.
 *
 * It used to render the file LIST as well, and that is the half that left. One origin
 * showed the same filenames twice — once here with its size, once in the transcription's
 * own list with its state — because the two halves lived in different components that had
 * never been on screen together. On a screen of its own they are one row per document, so
 * the list moved to `SlotCard` and what stays here is the dropzone and the two operations
 * a row cannot do for itself.
 *
 * It also moved out of `components/`: nothing outside `features/raw/` has ever imported
 * it, and the feature is a tree with its own `api` / `queries` / `types`.
 */

function accepts(name: string, extensions: string[]) {
  const dot = name.lastIndexOf(".");
  return dot > 0 && extensions.includes(name.slice(dot).toLowerCase());
}

export interface SlotIntake {
  send: (list: FileList | File[] | null) => Promise<void>;
  remove: (name: string) => Promise<void>;
  removeMany: (names: string[]) => Promise<void>;
  removing: boolean;
  progress: number | null;
  error: string | null;
  notice: string | null;
}

/** The two writes a slot accepts, shared by the dropzone and by every document row. */
export function useSlotIntake(slot: RawSlot, extensions: string[]): SlotIntake {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const client = useQueryClient();
  const [progress, setProgress] = useState<number | null>(null);
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = () => {
    client.invalidateQueries({ queryKey: keys.raw });
    client.invalidateQueries({ queryKey: keys.health });
    client.invalidateQueries({ queryKey: ["raw", "transcription", slot.kind] });
    // The chain reads the documents: a stage built from fewer of them is stale the moment
    // the drop lands, and the bar has to say so without waiting for its next poll.
    client.invalidateQueries({ queryKey: keys.pipeline });
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
    if (
      !(await confirm({
        title: t("raw.confirmDelete", { name, slot: slotLabel(slot, t).toLowerCase() }),
        tone: "danger",
      }))
    )
      return;
    setError(null);
    try {
      await api.deleteRaw(slot.kind, name);
      setNotice(t("raw.removed", { name }));
      refresh();
    } catch (exception) {
      setError((exception as Error).message);
    }
  };

  /**
   * The same delete, over a selection: ONE question and ONE refresh.
   *
   * There is no bulk endpoint and this does not invent one — it is still a `DELETE` per
   * document. What made emptying a slot take minutes is everything AROUND the request: a
   * confirmation dialog per file, and a `refresh()` per file that refetched the listing,
   * the health and the transcription state before the next one could be pressed. Asked
   * once and refreshed once, twenty files cost twenty requests and nothing else.
   *
   * Sequential and not `Promise.all`: they write into one directory, and a failure has to
   * name the document it happened on rather than one of twenty at random. What has already
   * gone is kept — the listing is refreshed even when it stops halfway, or the screen would
   * keep offering files that are no longer there.
   */
  const removeMany = async (names: string[]) => {
    if (names.length === 0) return;
    if (names.length === 1) return remove(names[0]);
    if (
      !(await confirm({
        title: t("raw.confirmDeleteMany", {
          n: names.length,
          slot: slotLabel(slot, t).toLowerCase(),
        }),
        tone: "danger",
      }))
    )
      return;
    setError(null);
    setNotice(null);
    setRemoving(true);
    let done = 0;
    try {
      for (const name of names) {
        await api.deleteRaw(slot.kind, name);
        done += 1;
      }
      setNotice(plural("raw.removedMany", done));
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setRemoving(false);
      refresh();
    }
  };

  return { send, remove, removeMany, removing, progress, error, notice };
}

/**
 * The dropzone, in the two sizes the screen needs.
 *
 * `fill` is the empty case and it takes the whole height its container has left: there the
 * import IS the screen's next step, and a 44 px strip at the top of an otherwise blank
 * card says the opposite. With documents in the slot it goes back to one line, where it is
 * the way to add one more.
 */
export function SlotDropzone({
  slot,
  extensions,
  intake,
  fill = false,
}: {
  slot: RawSlot;
  extensions: string[];
  intake: SlotIntake;
  fill?: boolean;
}) {
  const { t } = useT();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    void intake.send(event.dataTransfer.files);
  };

  return (
    <div className={cn("flex flex-col gap-3", fill && "min-h-0 flex-1")}>
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
        aria-label={t("raw.dropInto", { slot: slotLabel(slot, t) })}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") input.current?.click();
        }}
        className={cn(
          "flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed text-center transition-colors",
          // `flex-1` takes whatever the card has left — which, when the origin beside it
          // is stocked, is a lot. The floor is for the case where BOTH are empty and the
          // grid has no height to hand out: a first-run screen should still open on a drop
          // area you cannot miss, not on two short boxes.
          fill ? "min-h-[15rem] flex-1 flex-col gap-2.5 p-8" : "p-3",
          dragging
            ? "border-primary bg-primary/10"
            : "border-border hover:border-primary/60 hover:bg-accent/50",
        )}
      >
        <UploadCloud
          className={cn(
            fill ? "size-8" : "size-4",
            dragging ? "text-primary" : "text-muted-foreground",
          )}
        />
        {fill ? (
          <>
            <p className="text-title font-semibold">
              {dragging ? t("raw.drop") : t("raw.dropHere")}
            </p>
            <p className="text-body text-muted-foreground">{t("raw.orPick")}</p>
          </>
        ) : (
          <p className="text-body font-medium">{dragging ? t("raw.drop") : t("raw.dropOrClick")}</p>
        )}
        <p className="text-small text-muted-foreground">{extensions.join(" · ")}</p>
        <input
          ref={input}
          type="file"
          multiple
          accept={extensions.join(",")}
          className="hidden"
          onChange={(event) => {
            void intake.send(event.target.files);
            event.target.value = "";
          }}
        />
      </div>

      {intake.progress !== null ? (
        <div className="space-y-1">
          <Progress value={intake.progress * 100} max={100} />
          <p className="text-small text-muted-foreground">
            {t("raw.uploading", { pct: Math.round(intake.progress * 100) })}
          </p>
        </div>
      ) : null}

      {intake.error ? <p className="text-small text-destructive">{intake.error}</p> : null}
      {intake.notice ? <p className="text-small text-muted-foreground">{intake.notice}</p> : null}
    </div>
  );
}

/** The extensions every slot accepts, read once by the screen that renders the slots. */
export function useRawExtensions(): string[] {
  const raw = useRaw();
  return raw.data?.supported_extensions ?? [];
}

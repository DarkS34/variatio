import { BookOpen, Check, FileText, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, Checkbox, Skeleton, Spinner } from "@/components/ui/misc";
import { RowGestures, Table, TableBulk, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useT, type Key } from "@/lib/i18n";
import { slotLabel, slotPurpose, staleReasons } from "@/lib/raw";
import type { RawSlot } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCanEdit } from "@/state/auth";

import { DocumentReader } from "./DocumentReader";
import { busyDocument } from "./progress";
import { useTranscribeRun, useTranscribing, useTranscription } from "./queries";
import { SlotDropzone, useSlotIntake } from "./SlotIntake";
import { RunningBlock, TranscriptionBadge } from "./SlotTranscription";
import type { DocumentState } from "./types";

const STATE: Record<DocumentState, { labelKey: Key; variant: "settled" | "outline" | "attention" }> = {
  done: { labelKey: "transcribe.state.done", variant: "settled" },
  pending: { labelKey: "transcribe.state.pending", variant: "outline" },
  stale: { labelKey: "transcribe.state.stale", variant: "attention" },
};

const VISIBLE = 6;

function DocumentRow({
  name,
  extension,
  pages,
  state,
  reasons,
  failedPages,
  retryPages,
  unreadableImages,
  busy,
  canEdit,
  selected,
  onSelect,
  onOpen,
  onRemove,
}: {
  name: string;
  /** What the file is and how many pages its reading holds: the row's second line. */
  extension: string;
  pages: number;
  state: DocumentState;
  reasons: string[];
  failedPages: number;
  /** The failed pages the next read tries again; zero when pages were moved by hand. */
  retryPages: number;
  unreadableImages: number;
  busy: boolean;
  canEdit: boolean;
  /** Undefined where nobody can pick (no column); null on a row that cannot be picked now. */
  selected?: boolean | null;
  onSelect: (next: boolean) => void;
  onOpen: () => void;
  onRemove: () => void;
}) {
  const { t, plural } = useT();
  const meta = STATE[state];
  const notes = staleReasons(reasons, t);

  // A note under the row sits in a row of its own, so the rule falls under the note and the
  // document and its note read as one entry.
  const noted = notes.length > 0 || failedPages > 0;
  return (
    <>
      <TR joined={noted} className="group [&>td]:align-top">
        {/* The box goes where the eye starts the row, and it is drawn only for somebody
            who can actually delete: for a reader it would be a control down every row
            that does nothing at all. The icon beside it stays — it is what carries the
            spinner while a document is being re-read. */}
        {selected === undefined ? null : (
          <TD className="pr-0 pt-3.5">
            {selected === null ? null : (
              <Checkbox checked={selected} onCheckedChange={onSelect} label={t("raw.selectFile", { name })} />
            )}
          </TD>
        )}
        {/* The name takes what the state and the gestures leave: `max-w-0` lets its cell
            shrink below its text, so the text truncates instead of widening the table. */}
        <TD className="max-w-0 py-2.5">
          {/* Each document an entry of two lines (user's request, 2026-10-08: one thin line
              a document read as a list of nothing): its name — which opens its pages, as the
              pencil does — and under it what it is and how many pages were read. The size went
              the same day, at the user's request: nobody acts on it. */}
          <span className="flex min-w-0 items-start gap-2.5">
            {busy ? (
              <Spinner className="mt-0.5 size-4 shrink-0" />
            ) : (
              <FileText aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            )}
            <span className="min-w-0">
              {state === "pending" || busy ? (
                <span className="block truncate font-medium" title={name}>
                  {name}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={onOpen}
                  title={t("transcribe.reviewPages")}
                  className="block max-w-full truncate text-left font-medium underline-offset-4 hover:underline"
                >
                  {name}
                </button>
              )}
              <span className="nums block truncate text-small text-muted-foreground">
                {[
                  extension.replace(/^\./, "").toUpperCase(),
                  pages > 0 ? plural("raw.pages", pages) : null,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </span>
          </span>
        </TD>
        <TD className="py-2.5">
          <span className="flex items-center justify-end gap-1.5 whitespace-nowrap">
            {/* "leído" is a grey tick and the other two states keep their words: what a
                person scans this column for is the rows that still need something, and a word
                on every finished row buries them. Grey is `--settled`. */}
            {!busy && state === "done" ? (
              <span title={t("transcribe.state.done")} className="flex items-center px-1">
                <Check aria-hidden className="size-4 text-settled" />
                <span className="sr-only">{t("transcribe.state.done")}</span>
              </span>
            ) : (
              <Badge variant={busy ? "outline" : (meta?.variant ?? "outline")}>
                {busy ? t("transcribe.transcribing") : meta ? t(meta.labelKey) : state}
              </Badge>
            )}
            {!busy && failedPages > 0 ? (
              <Badge variant="danger">{plural("transcribe.failedCount", failedPages)}</Badge>
            ) : null}
            {/* A picture of a Word or PowerPoint file nothing could read — a WMF or EMF
                metafile, usually — leaves a mark in the page and this badge on the row, for
                the same reason a failed page does: a formula that vanished in silence is
                worse than one that says it is gone. */}
            {!busy && unreadableImages > 0 ? (
              <Badge variant="danger">{plural("transcribe.unreadableImages", unreadableImages)}</Badge>
            ) : null}
          </span>
        </TD>
        <TD className="w-20 py-2">
          <RowGestures>
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label={t("transcribe.reviewPagesOf", { name })}
              title={
                busy
                  ? t("transcribe.beingRewritten")
                  : state === "pending"
                    ? t("transcribe.noPagesYet")
                    : t("transcribe.reviewPages")
              }
              disabled={state === "pending" || busy}
              onClick={onOpen}
            >
              <BookOpen />
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label={t("raw.deleteFile", { name })}
              title={busy ? t("transcribe.beingRewritten") : t("raw.deleteFromSlot")}
              disabled={busy || !canEdit}
              onClick={onRemove}
              className="hover:text-destructive"
            >
              <Trash2 />
            </Button>
          </RowGestures>
        </TD>
      </TR>
      {noted ? (
        <TR>
          {selected === undefined ? null : <TD className="pr-0" />}
          <TD colSpan={3} className="pb-2.5 pl-[2.375rem] pt-0 text-small">
            {notes.length > 0 ? <p className="text-attention">{notes.join(" · ")}</p> : null}
            {/* A failed page the next read tries again says so: without it the row reports a
                loss nobody can act on, when pressing "Procesarlos todos ahora" is exactly the
                move. */}
            {failedPages > 0 ? (
              <p className="text-destructive">
                {retryPages > 0
                  ? plural("transcribe.failedPagesRetry", failedPages)
                  : plural("transcribe.failedPages", failedPages)}
              </p>
            ) : null}
          </TD>
        </TR>
      ) : null}
    </>
  );
}

export function SlotCard({ slot, extensions }: { slot: RawSlot; extensions: string[] }) {
  const { t, plural } = useT();
  const canEdit = useCanEdit();
  const empty = slot.files.length === 0;

  const intake = useSlotIntake(slot, extensions);
  const state = useTranscription(slot.kind, !empty);
  const running = useTranscribing(slot.kind);
  const run = useTranscribeRun(slot.kind);
  const busy = busyDocument(run);

  const [opened, setOpened] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);

  const rows = useMemo(() => {
    const read = new Map((state.data?.documents ?? []).map((entry) => [entry.name, entry]));
    return slot.files.map((file) => {
      const entry = read.get(file.name);
      return {
        name: file.name,
        state: entry?.state ?? ("pending" as DocumentState),
        reasons: entry?.reasons ?? [],
        failedPages: entry?.failed_pages ?? 0,
        retryPages: entry?.retry_pages ?? 0,
        unreadableImages: entry?.images_unreadable ?? 0,
        extension: file.extension,
        pages: entry?.pages ?? 0,
      };
    });
  }, [slot.files, state.data]);

  const visible = expanded ? rows : rows.slice(0, VISIBLE);

  /**
   * What is picked, and how it stops existing.
   *
   * A box per row and one "Eliminar" over the lot: one question, one pass, one refresh,
   * where deleting one at a time is a confirmation and three refetches per document.
   *
   * The picks are held as NAMES and intersected with the listing after every write, since
   * the delete changes that listing underneath them and a stale name keeps a count alive
   * over a file that is gone. The delete drops the selection itself, so this only catches
   * what somebody else removed.
   *
   * A document being re-read cannot be picked: `_write_pages` rewrites its whole directory
   * at the end, and the row already says so with its spinner.
   */
  const deletable = rows.filter((row) => busy !== row.name).map((row) => row.name);
  const selected = picked.filter((name) => deletable.includes(name));
  const allPicked = deletable.length > 0 && selected.length === deletable.length;

  useEffect(() => {
    setPicked((was) => {
      const kept = was.filter((name) => rows.some((row) => row.name === name));
      return kept.length === was.length ? was : kept;
    });
  }, [rows]);

  // The boxes are for somebody who can delete, and only where there is more than one thing
  // to pick: over a single document the column would be a control that says "choose which
  // of the one".
  const picking = canEdit && rows.length > 1;

  // A finished origin is the same block as one still owing something: its filled tick is
  // the whole announcement. The card was once lit with the coral from that corner, and the
  // user took the glow away (2026-10-05).
  return (
    <Card className="flex flex-col">
      <div className="mx-5 flex flex-col gap-1.5 border-b border-border py-5">
        <div className="flex min-h-7 flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <h2 className="min-w-0 flex-1 truncate text-heading">{slotLabel(slot, t)}</h2>
          {empty ? (
            <Badge variant="attention">{t("common.empty")}</Badge>
          ) : (
            <TranscriptionBadge slot={slot} />
          )}
        </div>

        <p className="w-[90%] text-small text-muted-foreground">{slotPurpose(slot, t)}</p>
      </div>

      <div className={cn("flex min-h-0 flex-1 flex-col gap-4 p-5")}>
        <SlotDropzone slot={slot} extensions={extensions} intake={intake} fill={empty} />

        {empty ? null : running ? <RunningBlock slot={slot} /> : null}

        {empty ? null : state.isLoading ? (
          <Skeleton className="h-24" />
        ) : state.isError ? (
          <Alert tone="danger" title={t("transcribe.unreadable")}>
            <p>{t("transcribe.noResponse", { path: `/api/raw/${slot.kind}/transcription` })}</p>
          </Alert>
        ) : (
          <Table aria-label={slotLabel(slot, t)} minWidth="0">
            <THead>
              <tr>
                {/* The select-all box sits in the column of its rows' boxes, and once
                    something is picked the head carries the one action over the picks over
                    its captions (`TableBulk`, in the first caption's cell) — the same line,
                    so ticking moves nothing. */}
                {picking ? (
                  <TH className="w-10 pr-0">
                    <Checkbox
                      checked={allPicked}
                      indeterminate={selected.length > 0 && !allPicked}
                      onCheckedChange={(next) => setPicked(next ? deletable : [])}
                      label={t("raw.selectAll")}
                      disabled={deletable.length === 0}
                    />
                  </TH>
                ) : null}
                {/* The list named, with its size: it reads as a list before a row is read. */}
                <TH className="w-full">
                  {selected.length > 0 ? (
                    <TableBulk count={plural("raw.selectedCount", selected.length)}>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={intake.removing}
                        onClick={async () => {
                          await intake.removeMany(selected);
                          setPicked([]);
                        }}
                        className="-my-1.5 h-7 text-destructive hover:text-destructive"
                      >
                        {intake.removing ? <Spinner /> : <Trash2 />}
                        {t("raw.deleteSelected")}
                      </Button>
                    </TableBulk>
                  ) : (
                    plural("raw.col.documents", rows.length)
                  )}
                </TH>
                <TH className="whitespace-nowrap text-right">{t("raw.col.state")}</TH>
                <TH className="w-20">
                  <span className="sr-only">{t("raw.col.document")}</span>
                </TH>
              </tr>
            </THead>
            <TBody>
              {visible.map((row) => (
                <DocumentRow
                  key={row.name}
                  {...row}
                  busy={busy === row.name}
                  canEdit={canEdit}
                  selected={picking ? (busy !== row.name ? selected.includes(row.name) : null) : undefined}
                  onSelect={(next) =>
                    setPicked((was) =>
                      next ? [...was, row.name] : was.filter((name) => name !== row.name),
                    )
                  }
                  onOpen={() => setOpened(row.name)}
                  onRemove={() => void intake.remove(row.name)}
                />
              ))}
              {rows.length > VISIBLE ? (
                <TR>
                  <TD colSpan={picking ? 4 : 3}>
                    <button
                      type="button"
                      onClick={() => setExpanded((was) => !was)}
                      className="text-small text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {expanded ? t("common.showLess") : plural("raw.showRest", rows.length - VISIBLE)}
                    </button>
                  </TD>
                </TR>
              ) : null}
            </TBody>
          </Table>
        )}

      </div>

      {opened ? (
        <DocumentReader
          key={opened}
          kind={slot.kind}
          name={opened}
          onClose={() => setOpened(null)}
        />
      ) : null}
    </Card>
  );
}

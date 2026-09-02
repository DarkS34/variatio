import { Check, FileText, PenLine, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { useT, type Key } from "@/lib/i18n";
import { slotLabel, slotPurpose, staleReasons } from "@/lib/raw";
import type { RawSlot } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCanEdit } from "@/state/auth";

import { DocumentDialog } from "./DocumentDialog";
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
  state,
  reasons,
  failedPages,
  busy,
  canEdit,
  onOpen,
  onRemove,
}: {
  name: string;
  state: DocumentState;
  reasons: string[];
  failedPages: number;
  busy: boolean;
  canEdit: boolean;
  onOpen: () => void;
  onRemove: () => void;
}) {
  const { t, plural } = useT();
  const meta = STATE[state];
  const notes = staleReasons(reasons, t);

  return (
    <li className="border-t border-border first:border-t-0">
      <div className="group flex items-center gap-2 px-2 py-1.5 text-small">
        {busy ? (
          <Spinner className="size-3.5 shrink-0" />
        ) : (
          <FileText aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
        )}
        <span className="min-w-0 flex-1 truncate" title={name}>
          {name}
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          {/* «leído» is a grey tick and the other two states keep their words (2026-09-01,
              explicit user request): what a person scans this column for is the rows that
              still need something, and a word on every finished row is what buries them.
              Grey is `--settled`, which is the palette's own «behind you, resolved». */}
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
        </span>

        <span className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100">
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
            <PenLine />
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
        </span>
      </div>

      {notes.length > 0 ? (
        <p className="px-2 pb-1.5 pl-[30px] text-small text-attention">{notes.join(" · ")}</p>
      ) : null}
      {failedPages > 0 ? (
        <p className="px-2 pb-1.5 pl-[30px] text-small text-destructive">
          {plural("transcribe.failedPages", failedPages)}
        </p>
      ) : null}
    </li>
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


  const rows = useMemo(() => {
    const read = new Map((state.data?.documents ?? []).map((entry) => [entry.name, entry]));
    return slot.files.map((file) => {
      const entry = read.get(file.name);
      return {
        name: file.name,
        state: entry?.state ?? ("pending" as DocumentState),
        reasons: entry?.reasons ?? [],
        failedPages: entry?.failed_pages ?? 0,
      };
    });
  }, [slot.files, state.data]);

  const visible = expanded ? rows : rows.slice(0, VISIBLE);
  // UP TO DATE TINTS THE WHOLE CARD (2026-09-02, explicit user request): the same 8 % of
  // `--attention` the tick's badge used to carry, mixed INTO the card (`oklab`, so the hue
  // does not drift through chroma zero) so the ground stays opaque, with the border at the
  // tint every attention alert uses. Only the finished state — a card still owing something
  // keeps the plain ground its rows are scanned against.
  const upToDate =
    !empty &&
    !running &&
    state.data !== undefined &&
    state.data.pending === 0 &&
    state.data.stale === 0;

  return (
    <Card
      className={cn(
        "flex flex-col transition-colors",
        upToDate &&
          "border-[color-mix(in_oklch,var(--attention)_40%,transparent)] bg-[color-mix(in_oklab,var(--attention)_8%,var(--card))]",
      )}
    >
      <div className="flex flex-col gap-1.5 border-b border-border p-4">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <h2 className="min-w-0 flex-1 truncate text-heading">{slotLabel(slot, t)}</h2>
          {empty ? (
            <Badge variant="attention">{t("common.empty")}</Badge>
          ) : (
            <TranscriptionBadge slot={slot} />
          )}
        </div>

        <p className="w-[90%] text-small text-muted-foreground">{slotPurpose(slot, t)}</p>
      </div>

      <div className={cn("flex min-h-0 flex-1 flex-col gap-3 p-4")}>
        <SlotDropzone slot={slot} extensions={extensions} intake={intake} fill={empty} />

        {empty ? null : running ? <RunningBlock slot={slot} /> : null}

        {empty ? null : state.isLoading ? (
          <Skeleton className="h-24" />
        ) : state.isError ? (
          <Alert tone="danger" title={t("transcribe.unreadable")}>
            <p>{t("transcribe.noResponse", { path: `/api/raw/${slot.kind}/transcription` })}</p>
          </Alert>
        ) : (
          <ul className="rounded-md border border-border">
            {visible.map((row) => (
              <DocumentRow
                key={row.name}
                {...row}
                busy={busy === row.name}
                canEdit={canEdit}
                onOpen={() => setOpened(row.name)}
                onRemove={() => void intake.remove(row.name)}
              />
            ))}
            {rows.length > VISIBLE ? (
              <li className="border-t border-border px-2 py-1.5">
                <button
                  type="button"
                  onClick={() => setExpanded((was) => !was)}
                  className="text-small text-muted-foreground transition-colors hover:text-foreground"
                >
                  {expanded ? t("common.showLess") : plural("raw.showRest", rows.length - VISIBLE)}
                </button>
              </li>
            ) : null}
          </ul>
        )}

      </div>

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

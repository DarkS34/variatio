import { FileText, PenLine, Trash2 } from "lucide-react";
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

/**
 * ONE DOCUMENT, ONE ROW — which is the whole reason this screen exists.
 *
 * The panel used to draw two lists of the same filenames: `SlotFiles`' (name and size) and
 * `DocumentList`'s (pages and transcription state), in two components that were never on
 * screen at the same time, so nobody could see they were the same six names. A document is
 * one thing and it gets one line: what it is called, whether it has been read, and the two
 * operations that act on it.
 *
 * The CAUSE of a «caducado» goes under its own row and not in an aggregate badge: the
 * register's rule is that staleness is a state with a reason or it is not a state.
 */
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
        {/* NEITHER THE SIZE NOR THE PAGE COUNT (2026-09-01, explicit user request).
            «928 KB · 45 pág.» is a fact about a file, and nobody uploading their own
            lecture notes is deciding anything with it. What the row has to answer is
            whether that document has been read, which the badge says on its own. */}
        {/* A document can be transcribed AND have pages the model could not read: «al día»
            is true of the transcription and says nothing about them. Two badges rather
            than one, because the red sentence below used to be the only sign of it and the
            badge column — the one anybody scans — read «settled» on the one row that
            needs a person. */}
        <span className="flex shrink-0 items-center gap-1.5">
          <Badge variant={busy ? "outline" : (meta?.variant ?? "outline")}>
            {busy ? t("transcribe.transcribing") : meta ? t(meta.labelKey) : state}
          </Badge>
          {!busy && failedPages > 0 ? (
            <Badge variant="danger">{plural("transcribe.failedCount", failedPages)}</Badge>
          ) : null}
        </span>

        {/* Repeated per-row chrome is furniture: the two actions appear on hover and on
            focus-within, never only on hover — a control that exists solely under a
            pointer does not exist for a keyboard. */}
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

/**
 * ONE ORIGIN, ONE CARD.
 *
 * The two cards are cells of a stretched grid, so an EMPTY origin's dropzone grows until
 * it matches the height of the stocked one beside it. That is not decoration: an empty
 * slot is the state every new workspace starts in, and there the import is the only thing
 * on the screen worth doing.
 */
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

  // The size lives on the raw listing and the pages on the transcription, so a row is a
  // join of the two by name — and a UNION rather than an intersection, keyed on the raw
  // listing. The two queries do not land together: a file that has just been uploaded is
  // in the listing before the transcription has been re-asked, and keying on the
  // transcription would make it vanish for a second between the upload finishing and the
  // refetch arriving. Unknown to the transcription simply means «not read yet», which is
  // exactly what `pending` says.
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

  return (
    <Card className="flex flex-col">
      {/* THE HEADER IS THE NAME AND ONE STATE (2026-09-01, explicit user request).
          What left it: the «hace falta para» chips, which name two artifacts a teacher has
          no reason to reason about while uploading a PDF; the aggregate «1 archivo · 928
          KB · 45 páginas»; and the per-origin button, because reading the documents is now
          ONE press for the whole screen. What stays is the sentence saying what belongs in
          this box, which is the only thing the person is actually deciding here. */}
      <div className="flex flex-col gap-1.5 border-b border-border p-4">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
          <h2 className="min-w-0 flex-1 truncate text-heading">{slotLabel(slot, t)}</h2>
          {empty ? (
            <Badge variant="attention">{t("common.empty")}</Badge>
          ) : (
            <TranscriptionBadge slot={slot} />
          )}
        </div>

        <p className="max-w-[60ch] text-small text-muted-foreground">{slotPurpose(slot, t)}</p>
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

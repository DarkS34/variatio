import { ChevronRight, UploadCloud } from "lucide-react";
import { useState } from "react";

import { SlotFiles } from "@/components/RawImport";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Alert, Skeleton } from "@/components/ui/misc";
import { bytes } from "@/lib/format";
import type { RawSlot } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useRaw } from "@/state/queries";
import { useT } from "@/lib/i18n";

import {
  TranscriptionAction,
  TranscriptionBadge,
  TranscriptionDetail,
  TranscriptionNote,
} from "./SlotTranscription";
import { useTranscriptionSummary } from "./queries";

const FEEDS: Record<string, string> = {
  exemplars_profile: "Perfil",
  knowledge_graph: "Grafo",
  exemplars_bank: "Banco",
};

/**
 * THE RAW MATERIAL, AS ONE CARD WITH ONE ROW PER ORIGIN.
 *
 * It used to be five blocks: a collapsible header, a grid of two upload cards, a
 * three-paragraph heading about transcription and a grid of two more cards — so the two
 * folders an instance is fed from occupied more of the panel than the chain they feed, and
 * the section auto-expanded into all of it whenever a slot was empty, which is the state
 * every new workspace starts in.
 *
 * One origin is now one row: what it holds, what state its transcription is in, and the
 * one thing there is to press. Everything else — the dropzone, the file list, the running
 * bars, the per-document states — is what the row reveals, and an empty origin opens by
 * itself because there the import IS the next step of the whole screen.
 */
function SlotRow({ slot, extensions }: { slot: RawSlot; extensions: string[] }) {
  const { t, plural } = useT();
  const empty = slot.files.length === 0;
  const [open, setOpen] = useState(false);
  const expanded = open || empty;

  return (
    <div className="border-t border-border first:border-t-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          disabled={empty}
          aria-expanded={expanded}
          className="flex min-w-0 items-center gap-2 text-body font-medium disabled:cursor-default"
        >
          <ChevronRight
            aria-hidden
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform",
              expanded && "rotate-90",
              empty && "invisible",
            )}
          />
          <span className="truncate">{slot.label}</span>
        </button>

        <InfoHint label={t("raw.whatIsThisSlot", { slot: slot.label })}>
          <span className="block">{slot.purpose}</span>
          <span className="mt-1.5 block">
            {t("raw.feedsLabel")}: {slot.feeds.map((artifact) => FEEDS[artifact] ?? artifact).join(", ")}
          </span>
        </InfoHint>

        {empty ? (
          <Badge variant="attention">{t("common.empty")}</Badge>
        ) : (
          <span className="text-small nums text-muted-foreground">
            {plural("dash.fileCount", slot.files.length)} · {bytes(slot.bytes)}
          </span>
        )}

        <TranscriptionBadge slot={slot} />

        <span className="flex-1" />

        {/* Only while it would do something new: once the row is open the dropzone is on
            screen, and a button that scrolls you to what you are already looking at is one
            more control for nothing. */}
        {expanded ? null : (
          <Button size="sm" variant="ghost" onClick={() => setOpen(true)} title={t("raw.openSlot")}>
            <UploadCloud />
            {t("common.import")}
          </Button>
        )}

        <TranscriptionAction slot={slot} />
      </div>

      {/* What changed stays on the row, never behind the disclosure: a badge that says
          «2 caducados» reports the state without the cause, and the cause is the half you
          act on. */}
      <div className="px-4 pb-2 empty:hidden">
        <TranscriptionNote slot={slot} />
      </div>

      {expanded ? (
        <div className="space-y-3 border-t border-dashed border-border px-4 py-3">
          <SlotFiles slot={slot} extensions={extensions} />
          <TranscriptionDetail slot={slot} />
        </div>
      ) : null}
    </div>
  );
}

export function RawSection() {
  const { t, plural } = useT();
  const raw = useRaw();
  const [explain, setExplain] = useState(false);

  const slots = raw.data?.slots ?? [];
  const summary = useTranscriptionSummary(slots);

  if (raw.isLoading) return <Skeleton className="h-40" />;
  if (!raw.data) {
    return (
      <Alert tone="danger" title={t("raw.unreadable")}>
        <p>{t("raw.noApi")}</p>
      </Alert>
    );
  }

  const files = slots.reduce((sum, slot) => sum + slot.files.length, 0);
  const size = slots.reduce((sum, slot) => sum + slot.bytes, 0);

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border px-4 py-3">
        <h2 className="text-heading">{t("dash.rawData")}</h2>
        {files > 0 ? (
          <span className="text-small nums text-muted-foreground">
            {plural("dash.fileCount", files)} · {bytes(size)}
          </span>
        ) : null}
        <span className="flex-1" />
        <button
          type="button"
          onClick={() => setExplain((value) => !value)}
          aria-expanded={explain}
          className="flex items-center gap-1 text-small text-muted-foreground transition-colors hover:text-foreground"
        >
          {t("raw.howItWorks")}
          <ChevronRight
            aria-hidden
            className={cn("size-3.5 transition-transform", explain && "rotate-90")}
          />
        </button>
      </div>

      {explain ? (
        <div className="space-y-2 border-b border-border bg-muted/40 px-4 py-3">
          <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
            {t("transcribe.intro1")}
          </p>
          <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
            {t("transcribe.intro2")}
          </p>
          <p className="max-w-3xl text-small leading-relaxed text-muted-foreground">
            {t("transcribe.intro3")}
          </p>
        </div>
      ) : null}

      {slots.map((slot) => (
        <SlotRow key={slot.kind} slot={slot} extensions={raw.data.supported_extensions} />
      ))}

      {/* One sentence about the whole section, and the one thing a person has to know
          before pressing anything here: this is an accelerator, not a gate. */}
      <p className="border-t border-border px-4 py-2.5 text-small text-muted-foreground">
        {summary.running ? t("transcribe.runningNote") : t("transcribe.notAGate")}
      </p>
    </Card>
  );
}

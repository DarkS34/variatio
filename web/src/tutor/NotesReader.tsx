import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Select } from "@/components/ui/input";
import { LoadError, Skeleton } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";

import { useNotes } from "./queries";
import type { NotesDocument, Place } from "./types";

/**
 * The notes, open where a reply sent the student: one section at a time, formatted.
 *
 * A section and not the whole document, because a reply names a section and a 90-page
 * document scrolled to it would bury it; the list of sections and the two arrows move through
 * the rest. The text is the transcription the tutor itself searches, so what the reader shows
 * is exactly what the reply was written from.
 */
export function NotesReader({ place, onClose }: { place: Place | null; onClose: () => void }) {
  const { t } = useT();
  const notes = useNotes(place?.document ?? null);

  return (
    <Dialog
      open={place !== null}
      onClose={onClose}
      title={t("tutor.notes.title")}
      description={place?.document}
      className="sm:max-w-3xl"
    >
      {notes.isLoading ? <Skeleton className="h-96" /> : null}
      {!notes.isLoading && !notes.data ? (
        <LoadError title={t("tutor.notes.unreadable")} error={notes.error} onRetry={notes.refetch} />
      ) : null}
      {notes.data && place ? (
        <Sections key={`${place.document}|${place.location}`} notes={notes.data} place={place} />
      ) : null}
    </Dialog>
  );
}

function Sections({ notes, place }: { notes: NotesDocument; place: Place }) {
  const { t } = useT();
  const [index, setIndex] = useState(() => sectionOf(notes, place.location));
  const top = useRef<HTMLDivElement>(null);
  const sections = notes.sections;

  // A new section is read from its top, not from where the last one was left.
  useEffect(() => {
    top.current?.scrollIntoView({ block: "start" });
  }, [index]);

  if (sections.length === 0) {
    return <p className="text-muted-foreground">{t("tutor.notes.empty")}</p>;
  }
  const section = sections[Math.min(index, sections.length - 1)];

  return (
    <div ref={top} className="space-y-4">
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="icon"
          aria-label={t("tutor.notes.previous")}
          disabled={index === 0}
          onClick={() => setIndex(index - 1)}
        >
          <ChevronLeft />
        </Button>
        <Select
          aria-label={t("tutor.notes.section")}
          value={index}
          onChange={(event) => setIndex(Number(event.target.value))}
          className="min-w-0 flex-1"
        >
          {sections.map((entry, i) => (
            <option key={`${i}-${entry.location}`} value={i}>
              {entry.location || notes.document}
            </option>
          ))}
        </Select>
        <Button
          variant="outline"
          size="icon"
          aria-label={t("tutor.notes.next")}
          disabled={index >= sections.length - 1}
          onClick={() => setIndex(index + 1)}
        >
          <ChevronRight />
        </Button>
      </div>
      <article className="min-w-0">
        <Markdown>{section.text}</Markdown>
      </article>
    </div>
  );
}

/**
 * The section a place points at: the one with its exact path, else the first one under it
 * (a unit's heading has no text of its own), else the start of the document.
 */
function sectionOf(notes: NotesDocument, location: string): number {
  if (!location) return 0;
  const exact = notes.sections.findIndex((section) => section.location === location);
  if (exact >= 0) return exact;
  const under = notes.sections.findIndex((section) => section.location.startsWith(`${location} > `));
  return under >= 0 ? under : 0;
}

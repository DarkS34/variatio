import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  type RefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Select } from "@/components/ui/input";
import { LoadError, Skeleton } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import {
  type Original,
  originalOf,
  pageAt,
  pageOf,
  sectionAtPage,
  sectionLabel,
  sectionOf,
} from "./notes";
import { useNotes, useNotesPage } from "./queries";
import type { NotesDocument, Place } from "./types";

type View = "original" | "text";

/** Between the bar and the page a jump lands on, in pixels. */
const LANDING_GAP = 12;
/** How far down what is visible the reader's eye is taken to be: the page there is the page read. */
const READING_LINE = 0.25;
/** A page must stay near the screen this long to be asked for, so dragging past it costs nothing. */
const NEAR_DELAY_MS = 150;

/**
 * The notes, open where a reply sent the student, in two views of one window.
 *
 * «Original» is the document as its author laid it out — the PDF's pages, the deck's
 * slides — every page one under another, opened on the page the section starts on and
 * scrolled freely from there: a section does not end where its page does. «Texto» is the
 * transcription the tutor itself searches, one section at a time: what a reply was written
 * from, and the view that can be selected, copied and read aloud. The original leads; a
 * document the server cannot draw has the text alone and no choice to make. The view chosen
 * holds for the visit, so a student who reads the text is not asked again at every place.
 * The window is one size whatever it shows, so changing the view moves nothing but the
 * content.
 */
export function NotesReader({ place, onClose }: { place: Place | null; onClose: () => void }) {
  const { t } = useT();
  const notes = useNotes(place?.document ?? null);
  const [view, setView] = useState<View>("original");
  const original = notes.data ? originalOf(notes.data) : null;

  return (
    <Dialog
      open={place !== null}
      onClose={onClose}
      title={t("tutor.notes.title")}
      description={place?.document}
      actions={
        original ? (
          <Tabs
            items={[
              { value: "original", label: t("tutor.notes.view.original") },
              { value: "text", label: t("tutor.notes.view.text") },
            ]}
            value={view}
            onChange={(next) => setView(next as View)}
          />
        ) : null
      }
      className="h-[92vh] sm:h-[85vh] sm:max-w-4xl"
    >
      {notes.isLoading ? <Skeleton className="h-96" /> : null}
      {!notes.isLoading && !notes.data ? (
        <LoadError title={t("tutor.notes.unreadable")} error={notes.error} onRetry={notes.refetch} />
      ) : null}
      {notes.data && place ? (
        <Reader
          key={`${place.document}|${place.location}`}
          notes={notes.data}
          place={place}
          original={original}
          byPage={original !== null && view === "original"}
        />
      ) : null}
    </Dialog>
  );
}

/**
 * One document, read as its pages (`byPage`) or by section. The section and the page move
 * together, so changing the view never loses the place: scrolling carries the section along,
 * and choosing a section brings its page.
 *
 * The bar stays in sight while the document scrolls under it. Its arrows and its list move
 * by SECTION in both views; in the original the pages are moved through by scrolling, and
 * the line under the bar says which one is being read.
 */
function Reader({
  notes,
  place,
  original,
  byPage,
}: {
  notes: NotesDocument;
  place: Place;
  original: Original | null;
  byPage: boolean;
}) {
  const { t } = useT();
  const sections = notes.sections;
  const pages = original?.pages ?? 1;
  const [index, setIndex] = useState(() => sectionOf(notes, place.location));
  const [page, setPage] = useState(() => pageOf(sections, index, pages));
  const root = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLDivElement>(null);
  const slots = useRef(new Map<number, HTMLElement>());
  // A jump scrolls too, and its scroll must not be read as the student's: the page asked
  // for may not reach the bar (the end of the document), and the section chosen must stay.
  const jumped = useRef(false);
  const standing = useRef({ index, page });
  standing.current = { index, page };

  const register = useCallback((number: number, node: HTMLElement | null) => {
    if (node) slots.current.set(number, node);
    else slots.current.delete(number);
  }, []);

  const showPage = (number: number) => {
    const box = scrollBox(root.current);
    const slot = slots.current.get(number);
    if (!box || !slot || !bar.current) return;
    const before = box.scrollTop;
    box.scrollTop +=
      slot.getBoundingClientRect().top - bar.current.getBoundingClientRect().bottom - LANDING_GAP;
    jumped.current = box.scrollTop !== before;
  };
  const showTop = () => {
    const box = scrollBox(root.current);
    if (box) box.scrollTop = 0;
  };

  // Entering a view lands where the other one stood: on the section's page, or at the top
  // of its text. Before the paint, so the window never shows the wrong place first.
  useLayoutEffect(() => {
    if (byPage) showPage(standing.current.page);
    else showTop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [byPage]);

  // A new section of the text is read from its top, not from where the last one was left.
  useEffect(() => {
    if (!byPage) showTop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);

  useEffect(() => {
    if (!byPage) return;
    const box = scrollBox(root.current);
    if (!box) return;
    let frame = 0;
    const read = () => {
      frame = 0;
      if (jumped.current) {
        jumped.current = false;
        return;
      }
      if (!bar.current) return;
      const floor = bar.current.getBoundingClientRect().bottom;
      const line = floor + (box.getBoundingClientRect().bottom - floor) * READING_LINE;
      const tops = Array.from(
        { length: pages },
        (_, at) => slots.current.get(at + 1)?.getBoundingClientRect().top ?? Infinity,
      );
      const atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 2;
      const next = atEnd ? pages : pageAt(tops, line);
      if (next === standing.current.page) return;
      setPage(next);
      setIndex(sectionAtPage(sections, next, standing.current.index));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(read);
    };
    box.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      box.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [byPage, pages, sections]);

  const goSection = (next: number) => {
    const landing = pageOf(sections, next, pages);
    setIndex(next);
    setPage(landing);
    if (byPage) showPage(landing);
  };

  if (sections.length === 0 && !original) {
    return <p className="text-muted-foreground">{t("tutor.notes.empty")}</p>;
  }
  const section = sections[Math.min(index, sections.length - 1)];

  return (
    <div ref={root}>
      <div
        ref={bar}
        className="sticky -top-3 z-10 -mx-3 -mt-3 space-y-2 bg-popover p-3 sm:-top-4 sm:-mx-4 sm:-mt-4 sm:p-4"
      >
        {sections.length > 0 ? (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              aria-label={t("tutor.notes.previous")}
              disabled={index === 0}
              onClick={() => goSection(index - 1)}
            >
              <ChevronLeft />
            </Button>
            <Select
              aria-label={t("tutor.notes.section")}
              value={index}
              onChange={(event) => goSection(Number(event.target.value))}
              className="min-w-0 flex-1"
            >
              {sections.map((entry, i) => (
                <option key={`${i}-${entry.location}`} value={i}>
                  {sectionLabel(entry, notes)}
                </option>
              ))}
            </Select>
            <Button
              variant="outline"
              size="icon"
              aria-label={t("tutor.notes.next")}
              disabled={index >= sections.length - 1}
              onClick={() => goSection(index + 1)}
            >
              <ChevronRight />
            </Button>
          </div>
        ) : null}
        {byPage ? (
          <p className="text-small text-muted-foreground nums" aria-live="polite">
            {t("tutor.notes.page", { page, pages })}
          </p>
        ) : null}
      </div>
      {byPage && original ? (
        <div className="well space-y-2 p-2 sm:space-y-3 sm:p-3">
          {original.ratios.map((ratio, at) => (
            <PageSlot
              key={at}
              document={notes.document}
              version={original.version}
              number={at + 1}
              ratio={ratio}
              register={register}
            />
          ))}
        </div>
      ) : section ? (
        <article className="mx-auto min-w-0 max-w-3xl">
          <Markdown>{section.text}</Markdown>
        </article>
      ) : null}
    </div>
  );
}

/**
 * One page of the original in the place its shape reserves, drawn once it is near the
 * screen. A sheet of paper is content, like a figure: it stays the colour its author gave it
 * in either theme, inside the well that holds the document.
 */
function PageSlot({
  document,
  version,
  number,
  ratio,
  register,
}: {
  document: string;
  version: string;
  number: number;
  ratio: number;
  register: (number: number, node: HTMLElement | null) => void;
}) {
  const { t } = useT();
  const slot = useRef<HTMLDivElement | null>(null);
  const near = useNear(slot);
  const image = useNotesPage(document, version, number, near);
  const url = useObjectUrl(image.data);
  const attach = useCallback(
    (node: HTMLDivElement | null) => {
      slot.current = node;
      register(number, node);
    },
    [number, register],
  );

  return (
    <div ref={attach} style={{ aspectRatio: `1 / ${ratio}` }} className="overflow-hidden rounded-md">
      {url ? (
        <img src={url} alt={t("tutor.notes.pageAlt", { page: number, document })} className="h-full w-full" />
      ) : image.isError ? (
        <LoadError
          title={t("tutor.notes.pageUnreadable")}
          error={image.error}
          onRetry={image.refetch}
          className="m-2"
        />
      ) : (
        <div className={cn("h-full w-full bg-muted", near && "animate-pulse-soft")} />
      )}
    </div>
  );
}

/** Whether an element has come within a screen of what its scrolling box shows, and stayed. */
function useNear(ref: RefObject<HTMLElement | null>): boolean {
  const [near, setNear] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    let timer = 0;
    const observer = new IntersectionObserver(
      ([entry]) => {
        window.clearTimeout(timer);
        if (entry.isIntersecting) timer = window.setTimeout(() => setNear(true), NEAR_DELAY_MS);
      },
      { root: scrollBox(node), rootMargin: "100% 0px" },
    );
    observer.observe(node);
    return () => {
      window.clearTimeout(timer);
      observer.disconnect();
    };
  }, [ref]);
  return near;
}

/** The box an element scrolls inside: the dialog's body, which the reader does not own. */
function scrollBox(node: HTMLElement | null): HTMLElement | null {
  for (let box = node?.parentElement ?? null; box; box = box.parentElement) {
    const flow = getComputedStyle(box).overflowY;
    if (flow === "auto" || flow === "scroll") return box;
  }
  return null;
}

/** An address for a file held in memory, let go when the file changes or the reader closes. */
function useObjectUrl(blob: Blob | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!blob) {
      setUrl(null);
      return;
    }
    const next = URL.createObjectURL(blob);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [blob]);
  return url;
}

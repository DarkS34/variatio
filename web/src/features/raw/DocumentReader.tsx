import { ChevronLeft, ChevronRight, CircleAlert } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Alert, EmptyState, Skeleton } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { useT } from "@/lib/i18n";
import type { RawKind } from "@/lib/types";
import { cn } from "@/lib/utils";

import { useDocumentPages, usePageActions } from "./queries";
import { OriginalPane } from "./reader/OriginalPane";
import { clampPage, nextToReview, originalOf, pageIn, scrollToPage } from "./reader/sync";
import { type Editing, pageMark, TextPane } from "./reader/TextPane";
import type { DocumentOriginal, DocumentPage } from "./types";

type Pane = "original" | "text";

/** From this width up the two panes stand side by side; under it, one at a time, by a tab. */
const WIDE = "(min-width: 1024px)";

/**
 * One document of a raw slot, read and corrected: the original as its author laid it out
 * beside its transcription, which is what every build reads.
 *
 * Where the transcription holds one page per page of that very file (a PDF, a deck), the two
 * panes go page to page: the page one of them is scrolled to is the page the other shows.
 * Where it does not (a Word file read as one text, pages moved by hand) each scrolls on its
 * own and one sentence says why. A document the server cannot draw has its text alone.
 *
 * It opens to READ: a page is corrected from its pencil, one at a time, and a correction
 * unsaved is asked about before another page opens or the window closes.
 */
export function DocumentReader({
  kind,
  name,
  onClose,
}: {
  kind: RawKind;
  name: string;
  onClose: () => void;
}) {
  const { t } = useT();
  const confirm = useConfirm();
  const listing = useDocumentPages(kind, name);
  const { save, insert, remove } = usePageActions(kind, name);
  const [editing, setEditing] = useState<Editing | null>(null);

  const pages = listing.data?.pages ?? [];
  const original = listing.data ? originalOf(listing.data) : null;
  const open = editing ? (pages.find((page) => page.index === editing.index) ?? null) : null;
  const dirty = editing !== null && open !== null && editing.draft !== open.text;
  const working = save.isPending || insert.isPending || remove.isPending;

  const attemptClose = async () => {
    if (editing && dirty && !(await confirm({ title: t("doc.unsavedClose", { page: editing.index }) }))) {
      return;
    }
    onClose();
  };

  const edit = async (page: DocumentPage) => {
    if (editing?.index === page.index) return;
    if (editing && dirty && !(await confirm({ title: t("doc.unsavedSwitch", { page: editing.index }) }))) {
      return;
    }
    setEditing({ index: page.index, draft: page.text });
  };

  const saveDraft = () => {
    if (!editing) return;
    save.mutate({ index: editing.index, text: editing.draft }, { onSuccess: () => setEditing(null) });
  };

  // A page inserted is a page to write: it opens for correction at once.
  const insertAfter = (after: number) =>
    insert.mutate({ after, text: "" }, { onSuccess: (data) => setEditing({ index: data.index, draft: "" }) });

  const deletePage = async (index: number) => {
    if (!(await confirm({ title: t("doc.confirmDelete", { page: index, name }), tone: "danger" }))) return;
    remove.mutate(index);
  };

  return (
    <Dialog
      open
      onClose={attemptClose}
      title={name}
      description={original ? t("doc.readerLead") : t("doc.readerLeadText")}
      className="h-[92vh] sm:h-[90vh] sm:max-h-[90vh] sm:max-w-[96rem]"
    >
      {listing.isLoading ? (
        <Skeleton className="h-full" />
      ) : !listing.data ? (
        <Alert tone="danger" title={t("doc.unreadable")}>
          <p>{t("doc.unreadableBody", { name })}</p>
        </Alert>
      ) : pages.length === 0 ? (
        <EmptyState title={t("doc.noPages")}>
          <p>{t("doc.notTranscribed")}</p>
        </EmptyState>
      ) : (
        <Reader
          kind={kind}
          name={name}
          pages={pages}
          original={original}
          editing={editing}
          working={working}
          saving={save.isPending}
          onDraft={(draft) => setEditing((now) => (now ? { ...now, draft } : now))}
          onEdit={edit}
          onCancel={() => setEditing(null)}
          onSave={saveDraft}
          onInsert={insertAfter}
          onDelete={deletePage}
        />
      )}
    </Dialog>
  );
}

/**
 * The two panes and the bar over them. Each pane records the page it stands on, and the bar
 * moves one of them (`lead`), the other going with it where the two pair.
 */
function Reader({
  kind,
  name,
  pages,
  original,
  editing,
  working,
  saving,
  onDraft,
  onEdit,
  onCancel,
  onSave,
  onInsert,
  onDelete,
}: {
  kind: RawKind;
  name: string;
  pages: DocumentPage[];
  original: DocumentOriginal | null;
  editing: Editing | null;
  working: boolean;
  saving: boolean;
  onDraft: (text: string) => void;
  onEdit: (page: DocumentPage) => void;
  onCancel: () => void;
  onSave: () => void;
  onInsert: (after: number) => void;
  onDelete: (index: number) => void;
}) {
  const { t } = useT();
  const wide = useWide();
  const [view, setView] = useState<Pane>("original");
  const [typed, setTyped] = useState<string | null>(null);
  const [standing, setStanding] = useState<Record<Pane, number>>({ original: 1, text: 1 });

  const root = useRef<HTMLDivElement>(null);
  const originalBox = useRef<HTMLDivElement>(null);
  const textBox = useRef<HTMLDivElement>(null);
  const slots = useRef<Record<Pane, Map<number, HTMLElement>>>({ original: new Map(), text: new Map() });
  const at = useRef<Record<Pane, number>>({ original: 1, text: 1 });
  // A jump scrolls the pane too, and its scroll must not be read as the reader's.
  const jumped = useRef<Record<Pane, boolean>>({ original: false, text: false });
  const frames = useRef<Record<Pane, number>>({ original: 0, text: 0 });

  const paired = original?.paired ?? false;
  const shown = (pane: Pane) =>
    pane === "text" ? wide || !original || view === "text" : original !== null && (wide || view === "original");
  const count = (pane: Pane) => (pane === "text" ? pages.length : (original?.pages ?? 0));
  // What the bar moves: the pane in sight on a narrow screen; side by side, the transcription
  // — the original going with it where the two pair — unless the transcription is one page
  // (a Word file read as one text), where only the original has pages to turn.
  const lead: Pane =
    original === null ? "text" : !wide ? view : !paired && pages.length === 1 ? "original" : "text";
  const live = useRef({ paired, shown, count });
  live.current = { paired, shown, count };

  const boxOf = useCallback(
    (pane: Pane) => (pane === "text" ? textBox.current : originalBox.current),
    [],
  );
  const registerOriginal = useCallback((number: number, node: HTMLElement | null) => {
    if (node) slots.current.original.set(number, node);
    else slots.current.original.delete(number);
  }, []);
  const registerText = useCallback((number: number, node: HTMLElement | null) => {
    if (node) slots.current.text.set(number, node);
    else slots.current.text.delete(number);
  }, []);

  const stand = useCallback((pane: Pane, number: number) => {
    at.current[pane] = number;
    setStanding((now) => (now[pane] === number ? now : { ...now, [pane]: number }));
  }, []);

  const bring = useCallback(
    (pane: Pane, number: number) => {
      if (scrollToPage(boxOf(pane), slots.current[pane], number)) jumped.current[pane] = true;
      stand(pane, number);
    },
    [boxOf, stand],
  );

  // Where the two pair, the other pane follows: brought there if in sight, else told where
  // to land when it comes into sight.
  const follow = useCallback(
    (pane: Pane, number: number) => {
      if (!live.current.paired) return;
      const other: Pane = pane === "text" ? "original" : "text";
      if (live.current.shown(other)) bring(other, number);
      else stand(other, number);
    },
    [bring, stand],
  );

  const read = useCallback(
    (pane: Pane) => {
      if (jumped.current[pane]) {
        jumped.current[pane] = false;
        return;
      }
      const box = boxOf(pane);
      if (!box) return;
      const number = pageIn(box, slots.current[pane], live.current.count(pane));
      if (number === at.current[pane]) return;
      stand(pane, number);
      follow(pane, number);
    },
    [boxOf, follow, stand],
  );

  const onScroll = (pane: Pane) => () => {
    if (frames.current[pane]) return;
    frames.current[pane] = requestAnimationFrame(() => {
      frames.current[pane] = 0;
      read(pane);
    });
  };
  useEffect(() => {
    const pending = frames.current;
    return () => {
      cancelAnimationFrame(pending.original);
      cancelAnimationFrame(pending.text);
    };
  }, []);

  // A pane coming into sight — a tab chosen, the window widened — lands where it stands.
  useLayoutEffect(() => {
    for (const pane of ["original", "text"] as const) {
      if (live.current.shown(pane)) bring(pane, at.current[pane]);
    }
  }, [view, wide, bring]);

  const goTo = (number: number) => {
    const page = clampPage(number, count(lead));
    bring(lead, page);
    follow(lead, page);
  };

  const needs = pages.map((page) => pageMark(page) !== "ok");
  const review = needs.filter(Boolean).length;
  const reviewNext = () => {
    const page = nextToReview(needs, at.current.text);
    if (page === null) return;
    if (shown("text")) {
      bring("text", page);
    } else {
      stand("text", page);
      setView("text");
    }
    follow("text", page);
  };

  const goToRef = useRef(goTo);
  goToRef.current = goTo;
  const leadRef = useRef(lead);
  leadRef.current = lead;

  const commit = () => {
    if (typed === null) return;
    const number = Number.parseInt(typed, 10);
    if (!Number.isNaN(number)) goTo(number);
    setTyped(null);
  };

  // The arrows and the page keys turn the page wherever the focus is in the window, but
  // never inside a field, a tab strip, or a question asked over the window.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const panel = root.current?.closest('[role="dialog"]');
      if (!target || !panel?.contains(target) || event.defaultPrevented) return;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      if (target.closest('input, textarea, select, [contenteditable="true"], [role="tablist"]')) return;
      const step =
        event.key === "ArrowRight" || event.key === "PageDown"
          ? 1
          : event.key === "ArrowLeft" || event.key === "PageUp"
            ? -1
            : 0;
      if (!step) return;
      event.preventDefault();
      goToRef.current(at.current[leadRef.current] + step);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const unpaired =
    original === null || paired
      ? null
      : original.unpaired === "moved"
        ? t("doc.unpaired.moved")
        : original.unpaired === "source"
          ? t("doc.unpaired.source")
          : pages.length === 1
            ? t("doc.unpaired.single")
            : t("doc.unpaired.count", { text: pages.length, original: original.pages });

  const caption = "text-micro font-condensed uppercase text-muted-foreground nums";
  const both = original !== null && wide;

  return (
    <div ref={root} className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {original && !wide ? (
          <Tabs
            items={[
              { value: "original", label: t("doc.view.original") },
              { value: "text", label: t("doc.view.text") },
            ]}
            value={view}
            onChange={(next) => setView(next as Pane)}
          />
        ) : null}
        <nav aria-label={t("doc.pages")} className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="icon"
            aria-label={t("doc.previousPage")}
            disabled={standing[lead] <= 1}
            onClick={() => goTo(at.current[lead] - 1)}
          >
            <ChevronLeft />
          </Button>
          <span className="flex items-center gap-1.5 text-small text-muted-foreground nums">
            <span>{t("doc.pageBefore")}</span>
            <Input
              aria-label={t("doc.pageInput")}
              inputMode="numeric"
              value={typed ?? String(standing[lead])}
              onChange={(event) => setTyped(event.target.value.replace(/\D/g, ""))}
              onFocus={(event) => event.target.select()}
              onKeyDown={(event) => {
                if (event.key === "Enter") commit();
              }}
              onBlur={commit}
              className="w-14 text-center nums"
            />
            <span>{t("doc.pageAfter", { total: count(lead) })}</span>
          </span>
          <Button
            variant="outline"
            size="icon"
            aria-label={t("doc.nextPage")}
            disabled={standing[lead] >= count(lead)}
            onClick={() => goTo(at.current[lead] + 1)}
          >
            <ChevronRight />
          </Button>
        </nav>
        {review > 0 ? (
          <Button variant="outline" className="ml-auto" title={t("doc.toReviewNext")} onClick={reviewNext}>
            <CircleAlert />
            {t("doc.toReview", { n: review })}
          </Button>
        ) : null}
      </div>
      {unpaired ? <p className="text-small text-muted-foreground">{unpaired}</p> : null}

      <div
        className={cn(
          "grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)] gap-4",
          both ? "grid-cols-2" : "grid-cols-1",
        )}
      >
        {original ? (
          <div className={cn("flex min-h-0 flex-col gap-2", !shown("original") && "hidden")}>
            {both ? (
              <p className={caption}>
                {paired || lead === "original"
                  ? t("doc.view.original")
                  : t("doc.originalAt", { page: standing.original, total: original.pages })}
              </p>
            ) : null}
            <OriginalPane
              kind={kind}
              name={name}
              original={original}
              register={registerOriginal}
              paneRef={originalBox}
              onScroll={onScroll("original")}
              className="flex-1"
            />
          </div>
        ) : null}
        <div
          className={cn(
            "flex min-h-0 flex-col gap-2",
            !shown("text") && "hidden",
            original === null && "mx-auto w-full max-w-3xl",
          )}
        >
          {both ? (
            <p className={caption}>
              {paired || lead === "text" || pages.length === 1
                ? t("doc.view.text")
                : t("doc.textAt", { page: standing.text, total: pages.length })}
            </p>
          ) : null}
          <TextPane
            name={name}
            pages={pages}
            register={registerText}
            paneRef={textBox}
            onScroll={onScroll("text")}
            editing={editing}
            working={working}
            saving={saving}
            onDraft={onDraft}
            onEdit={onEdit}
            onCancel={onCancel}
            onSave={onSave}
            onInsert={onInsert}
            onDelete={onDelete}
            className="flex-1"
          />
        </div>
      </div>
    </div>
  );
}

/** Whether the window is wide enough for the two panes side by side, kept current. */
function useWide(): boolean {
  const [wide, setWide] = useState(
    () => typeof window !== "undefined" && window.matchMedia(WIDE).matches,
  );
  useEffect(() => {
    const query = window.matchMedia(WIDE);
    const update = () => setWide(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return wide;
}

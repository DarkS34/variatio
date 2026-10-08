import {
  type RefObject,
  type UIEventHandler,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { LoadError } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";
import type { RawKind } from "@/lib/types";
import { cn } from "@/lib/utils";

import { useOriginalPage } from "../queries";
import type { DocumentOriginal } from "../types";
import { NEAR_DELAY_MS } from "./sync";

/**
 * The document as its author laid it out — the PDF's pages, the deck's slides, the Word
 * document exported — every page one under another, each in the place its shape reserves
 * and drawn once it comes near the screen, so scrolling never moves what is already there.
 */
export function OriginalPane({
  kind,
  name,
  original,
  register,
  paneRef,
  onScroll,
  className,
}: {
  kind: RawKind;
  name: string;
  original: DocumentOriginal;
  register: (number: number, node: HTMLElement | null) => void;
  paneRef: RefObject<HTMLDivElement | null>;
  onScroll: UIEventHandler<HTMLDivElement>;
  className?: string;
}) {
  const { t } = useT();
  return (
    <div
      ref={paneRef}
      onScroll={onScroll}
      role="region"
      aria-label={t("doc.view.original")}
      // Focusable, so the keyboard can scroll it once it is chosen.
      tabIndex={0}
      className={cn(
        "well thin-scroll min-h-0 space-y-2 overflow-y-auto p-2 sm:space-y-3 sm:p-3",
        className,
      )}
    >
      {original.ratios.map((ratio, at) => (
        <PageSlot
          key={at}
          kind={kind}
          name={name}
          version={original.version}
          number={at + 1}
          ratio={ratio}
          register={register}
        />
      ))}
    </div>
  );
}

/**
 * One page of the original. A sheet of paper is content, like a figure: it keeps the colour
 * its author gave it in either theme, inside the well that holds the document.
 */
function PageSlot({
  kind,
  name,
  version,
  number,
  ratio,
  register,
}: {
  kind: RawKind;
  name: string;
  version: string;
  number: number;
  ratio: number;
  register: (number: number, node: HTMLElement | null) => void;
}) {
  const { t } = useT();
  const slot = useRef<HTMLDivElement | null>(null);
  const near = useNear(slot);
  const image = useOriginalPage(kind, name, version, number, near);
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
        <img src={url} alt={t("doc.pageAlt", { page: number, name })} className="h-full w-full" />
      ) : image.isError ? (
        <LoadError
          title={t("doc.pageUnreadable")}
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

/** The box an element scrolls inside: the pane that holds it. */
function scrollBox(node: HTMLElement | null): HTMLElement | null {
  for (let box = node?.parentElement ?? null; box; box = box.parentElement) {
    const flow = getComputedStyle(box).overflowY;
    if (flow === "auto" || flow === "scroll") return box;
  }
  return null;
}

/** An address for a file held in memory, let go when the file changes or the pane closes. */
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

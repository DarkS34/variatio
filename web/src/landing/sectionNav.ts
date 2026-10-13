import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";

/** The landing's header, in pixels: `h-16`. A section's head comes to rest under it. */
export const HEADER_PX = 64;

/**
 * How far under the header a section's head comes to rest, in pixels. Its sum with
 * `HEADER_PX` is the head's `scroll-mt-[5.5rem]` (88 px): change the three together.
 */
export const REST_PX = 24;

/**
 * Which section the reader is in: the last one whose top has passed the reading line, and
 * the last of all once the page cannot scroll further — a short last section never
 * reaches the line, and the reader at the foot of the page is in it.
 */
export function sectionAt(
  tops: (number | null)[],
  ids: string[],
  line: number,
  atBottom: boolean,
): string | null {
  if (atBottom && ids.length) return ids[ids.length - 1];
  let current: string | null = null;
  ids.forEach((id, index) => {
    const top = tops[index];
    if (top !== null && top <= line) current = id;
  });
  return current;
}

/** The element a link to a section scrolls to: its head, not its top rule. */
export function headOf(id: string): HTMLElement | null {
  return document.getElementById(`${id}-head`);
}

function stillMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/**
 * The header's links: where the reader is, and the move to another section.
 *
 * Read off the scroll, once a frame, and HELD while a move of the header is under way: a
 * smooth scroll crosses every section between, and the mark followed it through all of them
 * before settling. It is released when the scroll ends (or after a second, for a move that
 * did not scroll at all). A page opened on an anchor (`/#demo`) goes there once laid out.
 */
export function useSectionNav(ids: string[]) {
  const [active, setActive] = useState<string | null>(null);
  const held = useRef(false);
  const key = ids.join(" ");

  useEffect(() => {
    const list = key.split(" ");
    let frame = 0;
    const read = () => {
      frame = 0;
      if (held.current) return;
      const tops = list.map((id) => document.getElementById(id)?.getBoundingClientRect().top ?? null);
      const page = document.documentElement;
      const atBottom = window.innerHeight + window.scrollY >= page.scrollHeight - 2;
      setActive(sectionAt(tops, list, HEADER_PX + window.innerHeight * 0.3, atBottom));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(read);
    };
    read();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);

    // Again once the type has loaded: a face arriving late moves every head down the page.
    const opened = decodeURIComponent(window.location.hash.slice(1));
    if (list.includes(opened)) {
      const arrive = () => headOf(opened)?.scrollIntoView({ block: "start" });
      requestAnimationFrame(arrive);
      void document.fonts?.ready.then(() => requestAnimationFrame(arrive));
    }

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [key]);

  const go = useCallback((event: MouseEvent, id: string | null) => {
    event.preventDefault();
    const behavior: ScrollBehavior = stillMotion() ? "auto" : "smooth";
    const { pathname, search } = window.location;

    held.current = true;
    setActive(id);
    let timer = 0;
    const release = () => {
      held.current = false;
      window.removeEventListener("scrollend", release);
      window.clearTimeout(timer);
    };
    window.addEventListener("scrollend", release);
    timer = window.setTimeout(release, 1200);

    if (id === null) {
      window.scrollTo({ top: 0, behavior });
      window.history.replaceState(window.history.state, "", `${pathname}${search}`);
      return;
    }
    headOf(id)?.scrollIntoView({ behavior, block: "start" });
    window.history.replaceState(window.history.state, "", `#${id}`);
  }, []);

  return { active, go };
}

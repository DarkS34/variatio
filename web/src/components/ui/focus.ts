import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * WHO TO GIVE THE FOCUS BACK TO — a short history, and not the one element that had it.
 *
 * Asking `document.activeElement` when a panel opens is a beat late: a panel that
 * autofocuses its own search box has already taken the focus by the time an effect runs.
 * And a single remembered slot is not enough either, because React applies `autoFocus`
 * while it is still mutating the DOM and only attaches refs afterwards — so at the instant
 * the search box announces itself the panel's own ref is still `null`, and any «is it
 * inside the panel?» test answers no. The list survives that: by the time it is READ the
 * ref exists, and the answer is the most recent focus that is outside the panel and still
 * on the page.
 */
const RECENT: HTMLElement[] = [];

if (typeof document !== "undefined") {
  document.addEventListener(
    "focusin",
    (event) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      RECENT.push(target);
      if (RECENT.length > 8) RECENT.shift();
    },
    true,
  );
}

function lastFocusOutside(panel: HTMLElement | null): HTMLElement | null {
  for (let i = RECENT.length - 1; i >= 0; i -= 1) {
    const candidate = RECENT[i];
    if (document.contains(candidate) && !panel?.contains(candidate)) return candidate;
  }
  return null;
}

/**
 * What makes a modal a modal, in one place: the focus goes in, stays in, and comes back.
 *
 * It lives here rather than inside `dialog.tsx` because there are two panels that are modal
 * — the dialog and the full-screen concept selector — and only the first had any of this.
 * Closing the selector left the focus on `<body>`, so anyone working by keyboard came out
 * of it at the top of the document and had to Tab back through the header, the workspace
 * switcher and every earlier step of the form to get back to where they had been.
 *
 * `onEscape` is held in a ref and NOT in the dependency list on purpose: callers pass an
 * inline arrow, so depending on it re-runs the effect on every render — and each re-run
 * restores the focus to the opener and then pulls it back inside, which is a flicker in the
 * one place a keyboard user cannot afford one.
 */
export function useModalFocus(
  open: boolean,
  panel: RefObject<HTMLElement | null>,
  onEscape?: () => void,
) {
  const escape = useRef(onEscape);
  escape.current = onEscape;

  useEffect(() => {
    if (!open) return;

    const previous = lastFocusOutside(panel.current);

    const focusables = () =>
      Array.from(panel.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter(
        (element) => element.offsetParent !== null,
      );

    // Not if something inside already has it: a panel that autofocuses its search box knows
    // better than "the first control" which one the person came here to use.
    if (!panel.current?.contains(document.activeElement)) {
      (focusables()[0] ?? panel.current)?.focus();
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && escape.current) {
        escape.current();
        return;
      }
      if (event.key !== "Tab") return;

      const items = focusables();
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      const outside = !panel.current?.contains(active);

      // The loop is closed by hand at both ends. A modal you can Tab out of isolates
      // nothing: you still reach the content behind the scrim, which is precisely what the
      // scrim claims is unavailable.
      if (event.shiftKey && (active === first || outside)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || outside)) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKey);
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      // Only while it is still on the page: focusing a node the render has removed lands on
      // `<body>`, which is the very thing this exists to avoid.
      if (previous && document.contains(previous)) previous.focus?.();
    };
  }, [open, panel]);
}

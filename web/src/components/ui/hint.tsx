import { Info } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

const WIDTH = 288;

/**
 * The explanation, one hover away.
 *
 * Every screen here has something worth explaining once and never again. Left as a
 * paragraph it is read once and then becomes furniture around the controls that
 * matter, so it lives behind an (i) instead: hover, focus or tap.
 *
 * The panel is fixed against the button's own rect and rendered at the document root,
 * so it survives the scrolling, clipping and blurred containers these hints sit in.
 */
export function InfoHint({
  children,
  className,
  label,
}: {
  children: ReactNode;
  className?: string;
  /** What the trigger announces. Defaults to the generic "more information". */
  label?: string;
}) {
  const { t } = useT();
  const trigger = label ?? t("ui.moreInfo");
  const ref = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);

  // OPENED BY A CLICK MEANS IT STAYS OPEN, AND THAT IS WHAT MAKES IT WORK ON A TOUCH SCREEN.
  // A tap is not just a click: the browser synthesises `mouseover`, `mouseenter`, `focus`
  // and — once the finger is gone — the matching leave, so `onMouseLeave` closed the panel a
  // few hundred milliseconds after the tap opened it. Measured on a tablet viewport: the
  // panel appears at 87 ms and is gone before 800, in every (i) of the app, which is why
  // `onClick` had been there for touch since the beginning without ever serving it.
  //
  // Pinned, only a deliberate dismissal closes it: a pointer press somewhere else, or
  // leaving the trigger with the keyboard.
  const pinned = useRef(false);

  const show = (pin = false) => {
    if (pin) pinned.current = true;
    setRect(ref.current?.getBoundingClientRect() ?? null);
    setOpen(true);
  };
  const hide = () => {
    if (pinned.current) return;
    setOpen(false);
  };
  const dismiss = () => {
    pinned.current = false;
    setOpen(false);
  };

  // Fixed coordinates go stale as soon as anything scrolls, and something usually is:
  // these panels sit next to a token stream that scrolls itself. Follow the anchor
  // instead of closing, or a hint would be unreadable during a run.
  useEffect(() => {
    if (!open) return;
    const track = () => setRect(ref.current?.getBoundingClientRect() ?? null);
    // Touch has no hover to leave with, so a press anywhere else dismisses it — and that is
    // the one thing that also unpins.
    const away = (event: Event) => {
      if (!ref.current?.contains(event.target as Node)) dismiss();
    };
    window.addEventListener("scroll", track, true);
    window.addEventListener("resize", track);
    document.addEventListener("pointerdown", away);
    return () => {
      window.removeEventListener("scroll", track, true);
      window.removeEventListener("resize", track);
      document.removeEventListener("pointerdown", away);
    };
  }, [open]);

  const left = rect ? Math.max(8, Math.min(rect.left, window.innerWidth - WIDTH - 8)) : 0;
  const below = rect ? rect.bottom + 6 : 0;
  const above = rect ? rect.top - 6 : 0;
  const flip = rect ? rect.bottom > window.innerHeight - 200 : false;

  return (
    <>
      <button
        ref={ref}
        type="button"
        aria-label={trigger}
        onMouseEnter={() => show()}
        onMouseLeave={hide}
        onFocus={() => show()}
        onBlur={dismiss}
        // The (i) sits inside rows and cards that are themselves clickable, and a hint that
        // ALSO does what its surroundings do is worse than no hint: on a touch screen this
        // click is the only way to read one, so it must not be the thing that navigates.
        //
        // It SHOWS and never toggles. Toggling reads well on paper and fails with a mouse:
        // the pointer has already hovered by the time the click lands, so the second half of
        // the toggle would put away the very panel the click was asking for. Dismissing is
        // what `away` is for — leaving with the pointer, or tapping anywhere else.
        onClick={(event) => {
          event.stopPropagation();
          show(true);
        }}
        className={cn(
          // `pointer-events-auto` because gated screens disable their whole content
          // area, and a section you cannot use yet is exactly when its explanation
          // is worth reading.
          "pointer-events-auto relative inline-flex size-4 shrink-0 items-center justify-center rounded-full text-muted-foreground/70 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          // THE TARGET IS 24 px; THE DRAWING STAYS AT 16. WCAG 2.2 AA (2.5.8) asks for
          // 24×24 and none of its exceptions apply here — an (i) is not inline in a
          // sentence and has no larger equivalent elsewhere. Growing the box instead
          // would move every row this sits in: there are 33 of them, in headers, table
          // rows and form steps that are already tuned. A pseudo-element inherits the
          // button's own hit testing, so `-inset-1` buys the missing 4 px on each side
          // and changes nothing that is painted.
          "before:absolute before:-inset-1 before:content-['']",
          className,
        )}
      >
        <Info className="size-3.5" />
      </button>
      {open && rect
        ? createPortal(
            <div
              role="tooltip"
              className="animate-fade-in pointer-events-none fixed z-50 rounded-md border border-border bg-popover p-2.5 text-small font-normal leading-relaxed text-muted-foreground shadow-raised"
              style={{
                width: WIDTH,
                left,
                top: flip ? undefined : below,
                bottom: flip ? window.innerHeight - above : undefined,
              }}
            >
              {children}
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

import { Info } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

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
  label = "Más información",
}: {
  children: ReactNode;
  className?: string;
  label?: string;
}) {
  const ref = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);

  const show = () => {
    setRect(ref.current?.getBoundingClientRect() ?? null);
    setOpen(true);
  };
  const hide = () => setOpen(false);

  // Fixed coordinates go stale as soon as anything scrolls, and something usually is:
  // these panels sit next to a token stream that scrolls itself. Follow the anchor
  // instead of closing, or a hint would be unreadable during a run.
  useEffect(() => {
    if (!open) return;
    const track = () => setRect(ref.current?.getBoundingClientRect() ?? null);
    // Touch has no hover to leave with, so a tap anywhere else dismisses it.
    const away = (event: Event) => {
      if (!ref.current?.contains(event.target as Node)) hide();
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
        aria-label={label}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={show}
        className={cn(
          // `pointer-events-auto` because gated screens disable their whole content
          // area, and a section you cannot use yet is exactly when its explanation
          // is worth reading.
          "pointer-events-auto inline-flex size-4 shrink-0 items-center justify-center rounded-full text-muted-foreground/70 transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
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

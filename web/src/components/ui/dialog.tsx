import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";
import { Button } from "./button";

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;

    // Who held the focus BEFORE opening. Without this, closing a dialog leaves the focus
    // on <body> and the next Tab starts again from the top of the page, which for anyone
    // navigating by keyboard means losing the place they were working in.
    const opener = document.activeElement as HTMLElement | null;

    const focusables = () =>
      Array.from(
        panel.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      ).filter((el) => el.offsetParent !== null);

    // The first control, not the panel: opening a dialog and having to Tab into it is
    // exactly what makes a modal not feel modal.
    (focusables()[0] ?? panel.current)?.focus();

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
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

      // The loop is closed by hand at both ends. A modal you can Tab out of isolates
      // nothing: you still reach the content behind the scrim, which is precisely what the
      // scrim claims is unavailable.
      if (event.shiftKey && (active === first || !panel.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
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
      opener?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={onClose} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          "relative z-10 flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg border border-border bg-card shadow-overlay animate-fade-in",
          className,
        )}
      >
        <header className="flex items-start justify-between gap-4 border-b border-border p-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-title">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-small text-muted-foreground">{description}</p>
            ) : null}
          </div>
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Cerrar">
            <X />
          </Button>
        </header>
        <div className="thin-scroll min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
        {footer ? (
          <footer className="flex items-center justify-end gap-2 border-t border-border p-4">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}

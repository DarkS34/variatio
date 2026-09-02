import { X } from "lucide-react";
import { useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";
import { Button } from "./button";
import { useModalFocus } from "./focus";
import { useT } from "@/lib/i18n";

export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  actions,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** Controls drawn between the title and the close button, for a dialog that pages
   *  through several things (the evaluation's reading view). */
  actions?: ReactNode;
  className?: string;
}) {
  const { t } = useT();
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useModalFocus(open, panel, onClose);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-black/50 animate-fade-in" onClick={onClose} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cn(
          // On a phone it is a sheet off the bottom edge and not a card floating in the
          // middle: with 16 px of margin either side there is nothing to float over, and
          // the bottom is where the thumb already is. `max-h` leaves the top of the screen
          // visible so it still reads as something laid ON the page.
          "relative z-10 flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-lg border border-border bg-card shadow-overlay animate-fade-in sm:max-h-[85vh] sm:max-w-2xl sm:rounded-lg",
          className,
        )}
      >
        <header className="flex items-start justify-between gap-3 border-b border-border p-3 sm:gap-4 sm:p-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-title">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-small text-muted-foreground">{description}</p>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            {actions}
            <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label={t("common.close")}>
              <X />
            </Button>
          </div>
        </header>
        <div className="thin-scroll min-h-0 flex-1 overflow-y-auto p-3 sm:p-4">{children}</div>
        {footer ? (
          <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-border p-3 sm:p-4">
            {footer}
          </footer>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}

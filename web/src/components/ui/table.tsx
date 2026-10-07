import type {
  HTMLAttributes,
  ReactNode,
  TdHTMLAttributes,
  ThHTMLAttributes,
} from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Align = "text" | "num";

// Horizontal scrolling lives HERE, in the table's own container, and never in the body of
// the page. It is the one concession this redesign makes to a narrow width: there are no
// mobile layouts, but a table that pushes the scrollbar onto <body> breaks a small desktop
// too.
//
// A TABLE LIES FLAT ON ITS BLOCK, and its text starts where the block's title does: the
// container reaches 12 px into the block's padding on each side, exactly a cell's own
// padding, so the first column's words sit on the block's content edge (user's request,
// 2026-10-07: the text of the tables stood 12, 20, 28 or 32 px from the edge, one per screen).
// Every table sits in a block with the block's padding; none gets a frame or a well of its own.
export function Table({
  minWidth = "36rem",
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableElement> & { minWidth?: string }) {
  return (
    <div className="thin-scroll -mx-3 overflow-x-auto">
      <table
        style={{ minWidth }}
        className={cn("w-full border-collapse text-small", className)}
        {...props}
      >
        {children}
      </table>
    </div>
  );
}

export function THead({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn("sticky top-0 z-10 bg-card rule-inset-head", className)}
      {...props}
    />
  );
}

// A row `joined` to the one under it — the controls it unfolds, a note about it — draws no
// rule of its own, so the two read as one entry. An attribute and not a class: the body's
// rule is a descendant selector that outranks any class set on the row.
export function TBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody
      className={cn("[&>tr:not([data-joined]):not(:last-child)]:rule-inset-b", className)}
      {...props}
    />
  );
}

export function TR({
  selected,
  onSelect,
  joined,
  className,
  ...props
}: HTMLAttributes<HTMLTableRowElement> & { selected?: boolean; onSelect?: () => void; joined?: boolean }) {
  return (
    <tr
      data-joined={joined ? "" : undefined}
      onClick={onSelect}
      // A row that answers the mouse and not the keyboard is a row half the people cannot
      // use. The role and the tabIndex only appear when it genuinely selects something;
      // adding them always would turn every read-only row into a stop in the tab order.
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={
        onSelect
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect();
              }
            }
          : undefined
      }
      aria-selected={onSelect ? selected : undefined}
      className={cn(
        "transition-colors",
        onSelect &&
          "cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        selected && "bg-primary/[0.09]",
        className,
      )}
      {...props}
    />
  );
}

export function TH({
  align = "text",
  className,
  ...props
}: Omit<ThHTMLAttributes<HTMLTableCellElement>, "align"> & { align?: Align }) {
  return (
    <th
      scope="col"
      className={cn(
        "px-3 py-2 text-micro font-condensed uppercase text-muted-foreground",
        align === "num" ? "text-right" : "text-left",
        className,
      )}
      {...props}
    />
  );
}

export function TD({
  align = "text",
  className,
  ...props
}: Omit<TdHTMLAttributes<HTMLTableCellElement>, "align"> & { align?: Align }) {
  return (
    <td
      className={cn(
        "px-3 py-2 align-middle",
        // Alignment is not a per-cell preference: a figure is compared down a column, and
        // for that it has to sit on the right with fixed-width digits. Making it a
        // parameter with two values, rather than a loose class, is what stops the seventh
        // table doing it its own way again.
        align === "num" ? "text-right nums" : "text-left",
        className,
      )}
      {...props}
    />
  );
}

export function TableEmpty({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-3 py-10 text-center text-small text-muted-foreground">
        {children}
      </td>
    </tr>
  );
}

/**
 * The gestures at a row's end: shown on hover or focus, keeping their room when hidden so the
 * columns never move. `always` holds the list's own gesture — copying a link, where copying is
 * what the list is for — in sight.
 */
export function RowGestures({
  children,
  always,
  className,
}: {
  children?: ReactNode;
  always?: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("flex items-center justify-end gap-0.5", className)}>
      <span className="flex items-center gap-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100">
        {children}
      </span>
      {always}
    </span>
  );
}

/** One gesture of a row: a small icon named for a screen reader and, on hover, for the eye. */
export function RowAction({
  label,
  title,
  icon,
  onClick,
  disabled,
  danger,
}: {
  label: string;
  title: string;
  icon: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <Button
      size="icon-sm"
      variant="ghost"
      aria-label={label}
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={danger ? "hover:text-destructive" : undefined}
    >
      {icon}
    </Button>
  );
}

/**
 * The head of a table while rows are ticked: how many, and the gestures over them, in place of
 * the captions and on the same line, so ticking moves nothing. Written as body text, not as a
 * caption: it is a sentence and its buttons, which keep the 28 px of a row's gestures.
 */
export function TableBulk({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <th colSpan={colSpan} scope="colgroup" className="px-3 py-2 text-left font-normal">
      <span className="flex items-center gap-2 text-small text-foreground">{children}</span>
    </th>
  );
}

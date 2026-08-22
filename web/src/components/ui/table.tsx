import type {
  HTMLAttributes,
  ReactNode,
  TdHTMLAttributes,
  ThHTMLAttributes,
} from "react";

import { cn } from "@/lib/utils";

type Align = "text" | "num";

// Horizontal scrolling lives HERE, in the table's own container, and never in the body of
// the page. It is the one concession this redesign makes to a narrow width: there are no
// mobile layouts, but a table that pushes the scrollbar onto <body> breaks a small desktop
// too.
export function Table({
  minWidth = "36rem",
  className,
  children,
  ...props
}: HTMLAttributes<HTMLTableElement> & { minWidth?: string }) {
  return (
    <div className="thin-scroll w-full overflow-x-auto">
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
      className={cn("sticky top-0 z-10 bg-card [&_th]:border-b [&_th]:border-border", className)}
      {...props}
    />
  );
}

export function TBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("[&_tr]:border-b [&_tr]:border-border/60", className)} {...props} />;
}

export function TR({
  selected,
  onSelect,
  className,
  ...props
}: HTMLAttributes<HTMLTableRowElement> & { selected?: boolean; onSelect?: () => void }) {
  return (
    <tr
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

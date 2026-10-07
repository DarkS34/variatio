import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * THE ONE LIST OF THE PANEL: every tab is the list of its sections beside the section open.
 *
 * The panel had three ways to say «this tab has parts»: a board of cells over «Motor», a
 * column of stages beside «Configuración», and nothing at all in the two functions' tabs,
 * which stacked who may use the function, its reading and its settings down one page. One
 * list replaces the three, and it is also the tab's summary: each row carries, under its
 * name, the state of what it opens — a part of the engine in a word, how many accounts, who
 * may use a function — so no row of tiles has to repeat it above.
 *
 * A row is a small thing inside a block: the one open is the sunk tint, never a relief.
 * Every row is the same two lines — a name and one line of state — so the list reads as a
 * list on every tab, whatever it lists.
 * Below `lg` the list lies down and scrolls sideways over the section.
 *
 * A list of two kinds of section (the subject's own parts, then one per unit) names the
 * second kind with a caption over its first row (`group`); a row of another weight — the one
 * that ends a course among the ones that run it — is ruled off from those above (`separated`),
 * across the list when it stands and down it when it lies. A list taller than the window
 * scrolls inside itself: pinned whole, its last rows were out of reach beside a long section.
 */
export interface SectionEntry {
  key: string;
  label: string;
  /** One line under the name: what the section holds, or the state it is in. */
  detail?: ReactNode;
  /** What a pointer left on the row reads: the state at more length than one line holds. */
  title?: string;
  /** What leads the row: a stage's number, an icon, the square of a part's state. */
  mark?: ReactNode;
  /** Changes made in the section and not saved yet. */
  pending?: number;
  /** A caption over the row, where the rows from this one on are another kind of section. */
  group?: string;
  /** A rule before the row, setting it apart from the rows above it (as `Tabs` does). */
  separated?: boolean;
}

export function Sections({
  label,
  items,
  value,
  onChange,
  before,
  after,
  children,
}: {
  /** The list's name for a screen reader. */
  label: string;
  items: SectionEntry[];
  /** The section open, or null when what is drawn is none of them (a search). */
  value: string | null;
  onChange: (key: string) => void;
  /** Over the list: a search across the sections. */
  before?: ReactNode;
  /** Under the list: what concerns the tab whole. */
  after?: ReactNode;
  children: ReactNode;
}) {
  const { plural } = useT();
  return (
    <div className="grid items-start gap-7 lg:grid-cols-[17rem_minmax(0,1fr)]">
      {/* Cleared of the sticky header, which takes a second row of navigation below `xl`. */}
      <div className="min-w-0 space-y-3 lg:sticky lg:top-40 xl:top-24">
        {before}
        <nav
          aria-label={label}
          className="surface p-2 lg:max-h-[calc(100dvh-11.5rem)] lg:overflow-y-auto xl:max-h-[calc(100dvh-7.5rem)]"
        >
          <ul className="flex gap-1 overflow-x-auto [scrollbar-width:none] lg:flex-col lg:overflow-visible [&::-webkit-scrollbar]:hidden">
            {items.map((item) => {
              const current = item.key === value;
              return (
                <li key={item.key} className="flex shrink-0 lg:block lg:shrink">
                  {item.separated ? (
                    <span
                      aria-hidden
                      className="mx-1 my-2 w-px shrink-0 self-stretch bg-border lg:mx-3 lg:my-1 lg:block lg:h-px lg:w-auto"
                    />
                  ) : null}
                  {item.group ? (
                    <p className="hidden px-3 pb-1 pt-3 text-micro font-condensed uppercase text-muted-foreground lg:block">
                      {item.group}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    data-section={item.key}
                    title={item.title}
                    aria-current={current ? "true" : undefined}
                    onClick={() => onChange(item.key)}
                    className={cn(
                      "flex w-full items-start gap-2.5 rounded-inner px-3 py-2.5 text-left transition-colors",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                      current ? "bg-sunk" : "hover:bg-accent",
                    )}
                  >
                    {item.mark ? (
                      <span
                        aria-hidden
                        className={cn(
                          "flex h-6 w-5 shrink-0 items-center justify-center",
                          current ? "text-foreground" : "text-muted-foreground",
                        )}
                      >
                        {item.mark}
                      </span>
                    ) : null}
                    <span className="min-w-0 flex-1">
                      <span
                        className={cn(
                          "block whitespace-nowrap text-body font-medium lg:truncate",
                          current ? "text-foreground" : "text-muted-foreground",
                        )}
                      >
                        {item.label}
                      </span>
                      {item.detail ? (
                        <span className="block whitespace-nowrap text-small text-muted-foreground lg:truncate">
                          {item.detail}
                        </span>
                      ) : null}
                    </span>
                    {item.pending ? (
                      <Badge
                        variant="attention"
                        className="mt-0.5 shrink-0"
                        title={plural("admin.sections.unsaved", item.pending)}
                      >
                        {item.pending}
                        <span className="sr-only">
                          {plural("admin.sections.unsaved", item.pending)}
                        </span>
                      </Badge>
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
        {after}
      </div>

      <div className="min-w-0 space-y-7">{children}</div>
    </div>
  );
}

/**
 * What opens every section: its name, one sentence of what it is, and the one action that
 * concerns the section whole, on the name's line.
 */
export function SectionHeader({
  title,
  hint,
  description,
  action,
  id,
}: {
  title: ReactNode;
  /** An (i) beside the name, for what the description does not say. */
  hint?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  id?: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id={id} className="font-display font-expanded text-title">
            {title}
          </h2>
          {hint}
        </div>
        {description ? (
          <p className="max-w-3xl text-small text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action ? <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div> : null}
    </div>
  );
}

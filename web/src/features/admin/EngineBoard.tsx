import { Badge } from "@/components/ui/badge";
import type { BoardCell, CellTone, ScreenKey } from "@/features/admin/engineState";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * THE BOARD: the engine's parts side by side, each with its state, and the door to each.
 *
 * The tab used to be one page three screens long, and the only way to learn whether the
 * quota was holding a build back was to scroll past the GPU to find out. The board answers
 * that for every part at once — the queue, the machine, the quota, the process — and the
 * part somebody then wants to look at is one press away instead of two thousand pixels.
 *
 * A cell's square is the mark's own vocabulary and introduces nothing: solid grey for what
 * needs nobody, solid ultramarine for the one that needs the administrator, an outline for
 * what is not there yet, the ink while it is working and red when calls are failing. The
 * word beside it says the same thing, so the colour is never the only channel.
 */

const MARK: Record<CellTone, string> = {
  ok: "bg-settled",
  live: "bg-primary animate-pulse-soft",
  act: "bg-attention",
  down: "bg-destructive",
  off: "border-[1.5px] border-muted-foreground",
};

const STATE_TEXT: Record<CellTone, string> = {
  ok: "text-foreground",
  live: "text-foreground",
  act: "text-attention",
  down: "text-destructive",
  off: "text-muted-foreground",
};

const COLUMNS: Record<number, string> = {
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-3",
  4: "sm:grid-cols-2 lg:grid-cols-4",
};

export function EngineBoard({
  cells,
  value,
  onChange,
}: {
  cells: BoardCell[];
  value: ScreenKey;
  onChange: (next: ScreenKey) => void;
}) {
  const { t, plural } = useT();
  const move = (delta: number) => {
    const index = cells.findIndex((cell) => cell.key === value);
    if (index < 0) return;
    const next = cells[(index + delta + cells.length) % cells.length].key;
    onChange(next);
    document.getElementById(tabId(next))?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={t("eng.board.label")}
      // One pixel of `--border` showing between the cells IS the grid: no cell draws a rule
      // of its own, so two, three or four of them wrap without a doubled or a missing line.
      className={cn("grid gap-px border border-border bg-border", COLUMNS[cells.length])}
      onKeyDown={(event) => {
        if (event.key === "ArrowRight") {
          event.preventDefault();
          move(1);
        } else if (event.key === "ArrowLeft") {
          event.preventDefault();
          move(-1);
        }
      }}
    >
      {cells.map((cell) => {
        const selected = cell.key === value;
        return (
          <button
            key={cell.key}
            id={tabId(cell.key)}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelId(cell.key)}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(cell.key)}
            className={cn(
              "relative flex min-w-0 flex-col gap-1 px-4 pb-3.5 pt-4 text-left transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
              selected ? "bg-card" : "bg-background hover:bg-card",
            )}
          >
            {selected ? (
              <span aria-hidden className="absolute inset-x-0 top-0 h-[3px] bg-primary" />
            ) : null}
            <span className="flex min-h-6 items-center gap-2">
              <span aria-hidden className={cn("size-2.5 shrink-0", MARK[cell.tone])} />
              <span
                className={cn(
                  "text-micro font-condensed uppercase",
                  selected ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {cell.label}
              </span>
              {cell.pending > 0 ? (
                <Badge variant="attention" className="ml-auto">
                  {plural("eng.board.unsaved", cell.pending)}
                </Badge>
              ) : null}
            </span>
            <span
              className={cn(
                "block truncate font-expanded text-heading first-letter:uppercase",
                STATE_TEXT[cell.tone],
              )}
            >
              {cell.state}
            </span>
            <span className="block truncate text-small text-muted-foreground">
              {cell.detail}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function tabId(key: ScreenKey): string {
  return `engine-tab-${key}`;
}

export function panelId(key: ScreenKey): string {
  return `engine-panel-${key}`;
}

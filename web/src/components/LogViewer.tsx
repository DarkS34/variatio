import { ArrowDownToLine, Copy, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { clock } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { LogLine } from "@/state/runStore";
import { useT } from "@/lib/i18n";

/**
 * The raw console, with the two controls that make thousands of lines usable: a level
 * floor and a text filter. Everything the pipeline logs ends up here — this is the
 * view you open when the summary above is not enough.
 */

const LEVELS = ["DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR"] as const;

const ORDER: Record<string, number> = {
  TRACE: 0,
  DEBUG: 1,
  INFO: 2,
  SUCCESS: 3,
  WARNING: 4,
  ERROR: 5,
  CRITICAL: 6,
};

const LEVEL_COLOUR: Record<string, string> = {
  DEBUG: "text-muted-foreground",
  INFO: "text-foreground",
  SUCCESS: "text-settled",
  WARNING: "text-attention",
  ERROR: "text-destructive",
  CRITICAL: "text-destructive",
};

const RENDER_LIMIT = 800;

export function LogViewer({
  logs,
  height = "20rem",
  onClear,
}: {
  logs: LogLine[];
  height?: string;
  onClear?: () => void;
}) {
  const { t, plural } = useT();
  const [floor, setFloor] = useState("DEBUG");
  const [needle, setNeedle] = useState("");
  const [follow, setFollow] = useState(true);
  const pane = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const min = ORDER[floor] ?? 0;
    const text = needle.trim().toLowerCase();
    return logs.filter(
      (line) =>
        (ORDER[line.level] ?? 2) >= min &&
        (!text ||
          line.message.toLowerCase().includes(text) ||
          line.module.toLowerCase().includes(text)),
    );
  }, [logs, floor, needle]);

  useEffect(() => {
    if (!follow) return;
    pane.current?.scrollTo({ top: pane.current.scrollHeight });
  }, [filtered.length, follow]);

  // Only the tail is rendered: a build emits tens of thousands of lines and the whole
  // history is already on disk in the run's JSONL.
  const visible = filtered.slice(-RENDER_LIMIT);

  const copy = () => {
    const text = filtered
      .map((line) => `${clock(line.ts)} ${line.level} ${line.module} ${line.message}`)
      .join("\n");
    navigator.clipboard?.writeText(text);
  };

  return (
    <div className="flex min-h-0 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-44 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
          <Input
            aria-label={t("log.filter")}
            value={needle}
            onChange={(event) => setNeedle(event.target.value)}
            placeholder={t("log.filter.placeholder")}
            className="h-8 pl-8 text-small"
          />
        </div>

        <div className="flex items-center gap-1">
          {LEVELS.map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => setFloor(level)}
              title={t("log.showFrom", { level })}
              className={cn(
                "rounded-full border px-2 py-0.5 text-micro transition-colors",
                floor === level
                  ? "border-primary text-primary"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              {level}
            </button>
          ))}
        </div>

        <Badge variant="outline">{filtered.length}</Badge>

        <Button
          size="icon-sm"
          variant={follow ? "secondary" : "ghost"}
          onClick={() => setFollow((value) => !value)}
          title={follow ? t("log.following") : t("log.follow")}
          aria-label={t("log.follow")}
        >
          <ArrowDownToLine />
        </Button>
        <Button size="icon-sm" variant="ghost" onClick={copy} title={t("action.copy")} aria-label={t("action.copy")}>
          <Copy />
        </Button>
        {onClear ? (
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={onClear}
            title={t("log.clearView")}
            aria-label={t("log.clear")}
          >
            <Trash2 />
          </Button>
        ) : null}
      </div>

      {filtered.length === 0 ? (
        <p className="rounded-md border border-dashed border-border p-4 text-center text-small text-muted-foreground">
          {logs.length === 0
            ? t("log.empty")
            : t("log.noMatch")}
        </p>
      ) : (
        <div
          ref={pane}
          onScroll={() => {
            const el = pane.current;
            if (el) setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
          }}
          className="thin-scroll overflow-auto rounded-md border border-border bg-muted/30 p-2 font-mono text-micro leading-relaxed"
          style={{ height }}
        >
          {filtered.length > visible.length ? (
            <p className="pb-1 text-muted-foreground">
              {plural("log.omitted", filtered.length - visible.length)}
            </p>
          ) : null}
          {visible.map((line) => (
            <div key={line.seq} className="flex gap-2">
              <span className="shrink-0 text-muted-foreground">{clock(line.ts)}</span>
              <span className={cn("w-16 shrink-0", LEVEL_COLOUR[line.level] ?? "")}>
                {line.level}
              </span>
              <span className="hidden shrink-0 text-muted-foreground sm:inline">{line.module}</span>
              <span className="min-w-0 whitespace-pre-wrap break-words">{line.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

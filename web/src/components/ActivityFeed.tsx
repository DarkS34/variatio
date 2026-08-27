import { clock } from "@/lib/format";
import { describeEvent, type ActivityLine, type ActivityTone } from "@/lib/explain";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

/** The run narrated in order: what was decided, what was retried, what came out. */

const TONE: Record<ActivityTone, string> = {
  info: "text-muted-foreground",
  good: "text-settled",
  warn: "text-attention",
  bad: "text-destructive",
};

const DOT: Record<ActivityTone, string> = {
  info: "bg-muted-foreground/50",
  good: "bg-settled",
  warn: "bg-attention",
  bad: "bg-destructive",
};

export function ActivityFeed({
  lines,
  className,
  limit = 200,
}: {
  lines: ActivityLine[];
  className?: string;
  limit?: number;
}) {
  const tr = useT();

  if (lines.length === 0) {
    return (
      <p className={cn("text-small text-muted-foreground", className)}>{tr.t("activity.empty")}</p>
    );
  }

  const visible = lines
    .slice(-limit)
    .map((line) => ({ ...line, described: describeEvent(line.event, tr) }))
    .filter((line) => line.described !== null);

  return (
    <ol className={cn("space-y-1", className)}>
      {visible.map((line) => (
        <li key={line.seq} className="flex items-start gap-2 text-small">
          <span className="shrink-0 nums text-muted-foreground">{clock(line.ts)}</span>
          <span
            className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", DOT[line.described!.tone])}
          />
          <span className={cn("min-w-0 flex-1 break-words", TONE[line.described!.tone])}>
            {line.described!.text}
          </span>
        </li>
      ))}
    </ol>
  );
}

import { ChevronRight, Terminal } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Badge } from "@/components/ui/badge";
import { clock } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { LogLine, RunView } from "@/state/runStore";

function Section({
  title,
  count,
  children,
  defaultOpen = false,
}: {
  title: string;
  count?: number;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium"
      >
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        {title}
        {count !== undefined ? (
          <Badge variant="outline" className="ml-auto">
            {count}
          </Badge>
        ) : null}
      </button>
      {open ? <div className="border-t border-border p-3">{children}</div> : null}
    </div>
  );
}

const LEVEL_COLOUR: Record<string, string> = {
  DEBUG: "text-muted-foreground",
  INFO: "text-foreground",
  SUCCESS: "text-[var(--success)]",
  WARNING: "text-[var(--warning)]",
  ERROR: "text-destructive",
  CRITICAL: "text-destructive",
};

function LogConsole({ logs }: { logs: LogLine[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [logs.length]);

  if (logs.length === 0) {
    return <p className="text-xs text-muted-foreground">Sin registros.</p>;
  }

  // Only the tail is rendered: a build emits thousands of lines and the earlier ones
  // are already in the run's JSONL on disk.
  const visible = logs.slice(-400);
  return (
    <div ref={ref} className="thin-scroll max-h-64 overflow-auto font-mono text-[11px] leading-relaxed">
      {visible.map((line) => (
        <div key={line.seq} className="flex gap-2">
          <span className="shrink-0 text-muted-foreground">{clock(line.ts)}</span>
          <span className={cn("w-16 shrink-0", LEVEL_COLOUR[line.level] ?? "")}>{line.level}</span>
          <span className="shrink-0 text-muted-foreground">{line.module}</span>
          <span className="min-w-0 whitespace-pre-wrap break-words">{line.message}</span>
        </div>
      ))}
    </div>
  );
}

export function TechnicalDetails({ run }: { run: RunView }) {
  return (
    <div className="space-y-2">
      {run.retrieval ? (
        <Section title="Recuperación de conceptos" count={run.retrieval.candidates.length}>
          <p className="mb-2 truncate text-xs text-muted-foreground">{run.retrieval.query}</p>
          {run.retrieval.candidates.length === 0 ? (
            <p className="text-xs text-[var(--warning)]">
              Ningún candidato superó el umbral de similitud.
            </p>
          ) : (
            <ul className="space-y-1">
              {run.retrieval.candidates.map(([name, score]) => (
                <li key={name} className="flex items-center gap-2 text-xs">
                  <span className="w-14 shrink-0 tabular-nums text-muted-foreground">
                    {score.toFixed(3)}
                  </span>
                  <div className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-muted">
                    <div className="h-full bg-primary" style={{ width: `${Math.min(100, score * 100)}%` }} />
                  </div>
                  <span className="min-w-0 truncate">{name}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      ) : null}

      {run.fewShot.length > 0 ? (
        <Section title="Ejemplos few-shot usados" count={run.fewShot.length}>
          <div className="flex flex-wrap gap-1">
            {run.fewShot.map((id) => (
              <Badge key={id} variant="secondary">
                {id}
              </Badge>
            ))}
          </div>
        </Section>
      ) : null}

      {run.repairs.length > 0 ? (
        <Section title="Reparaciones de JSON" count={run.repairs.length}>
          <ul className="space-y-1.5">
            {run.repairs.map((repair, index) => (
              <li key={index} className="text-xs">
                <span className="text-[var(--warning)]">
                  intento {repair.attempt}/{repair.max_attempts}
                </span>{" "}
                <span className="text-muted-foreground">({repair.where})</span>
                <p className="font-mono text-[11px] text-muted-foreground">{repair.error}</p>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {run.prompt ? (
        <Section title="Prompt enviado al modelo">
          <CodeBlock code={run.prompt} language="text" maxHeight="18rem" />
        </Section>
      ) : null}

      <Section title="Consola" count={run.logs.length}>
        <div className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Terminal className="size-3.5" />
          Salida cruda del pipeline
        </div>
        <LogConsole logs={run.logs} />
      </Section>
    </div>
  );
}

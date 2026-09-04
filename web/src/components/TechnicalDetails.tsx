import { ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { RunView } from "@/state/runStore";
import { useT } from "@/lib/i18n";

function Section({
  title,
  count,
  children,
  icon,
  defaultOpen = false,
}: {
  title: string;
  count?: number;
  children: ReactNode;
  icon?: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-small font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        {icon}
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

export function TechnicalDetails({ run }: { run: RunView }) {
  const { t } = useT();
  return (
    <div className="space-y-2">
      {run.retrieval ? (
        <Section title={t("technical.retrieval")} count={run.retrieval.candidates.length}>
          <p className="mb-2 truncate text-small text-muted-foreground">{run.retrieval.query}</p>
          {run.retrieval.candidates.length === 0 ? (
            <p className="text-small text-attention">
              {t("technical.noCandidates")}
            </p>
          ) : (
            <ul className="space-y-1">
              {run.retrieval.candidates.map(([name, score]) => (
                <li key={name} className="flex items-center gap-2 text-small">
                  <span className="w-14 shrink-0 nums text-muted-foreground">
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

      {run.repairs.length > 0 ? (
        <Section title={t("technical.repairs")} count={run.repairs.length}>
          <ul className="space-y-1.5">
            {run.repairs.map((repair, index) => (
              <li key={index} className="text-small">
                <span className="text-attention">
                  {t("technical.attempt", { n: repair.attempt, max: repair.max_attempts })}
                </span>{" "}
                <span className="text-muted-foreground">({repair.where})</span>
                <p className="font-mono text-small text-muted-foreground">{repair.error}</p>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {run.prompt ? (
        <Section title={t("technical.prompt")}>
          <CodeBlock code={run.prompt} language="text" maxHeight="18rem" />
        </Section>
      ) : null}
    </div>
  );
}

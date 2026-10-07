import { useId } from "react";

import { sayFindings } from "@/lib/activity";
import { useT } from "@/lib/i18n";
import type { ActivityFinding } from "@/lib/types";
import { cn } from "@/lib/utils";

/** One key figure of the week: what it counts, its value, and one line that sets it in context. */
export interface WeekFigure {
  key: string;
  label: string;
  value: string;
  note?: string | null;
}

/**
 * «Lo importante»: the week of one page in a glance — its key figures in a row, then what a
 * teacher should read first, at most five sentences, each led by the figure that backs it.
 *
 * The server ranks and types the sentences (`server/activity.py`), each of one page; the
 * words are composed here (`lib/activity.sayFindings`). The first one a teacher can act on is
 * the screen's one `--attention`; the rest are ink. With nothing to point out, one sentence
 * says so.
 */
export function Findings({ findings, figures }: { findings: ActivityFinding[]; figures: WeekFigure[] }) {
  const tr = useT();
  const id = useId();
  const views = sayFindings(findings, tr);
  // A rule parts the figures from the sentences; with no figures there is nothing to part.
  const ruled = figures.length > 0;
  return (
    <section aria-labelledby={id} className="surface space-y-4 p-5">
      <h3 id={id} className="text-heading">
        {tr.t("activity.important")}
      </h3>
      {figures.length > 0 ? (
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-3">
          {figures.map((figure) => (
            <div key={figure.key} className="min-w-0 space-y-0.5">
              <dt className="text-micro font-condensed uppercase text-muted-foreground">{figure.label}</dt>
              <dd className="nums font-display font-expanded text-title">{figure.value}</dd>
              {figure.note ? <dd className="text-small text-muted-foreground">{figure.note}</dd> : null}
            </div>
          ))}
        </dl>
      ) : null}
      {views.length === 0 ? (
        <p className={cn("text-body text-muted-foreground", ruled && "border-t border-border pt-3.5")}>
          {tr.t("activity.nothing")}
        </p>
      ) : (
        <ul className={cn("rows", ruled && "border-t border-border pt-3.5")}>
          {views.map((view, index) => (
            <li key={index} className="flex items-baseline gap-4">
              <span
                className={cn(
                  "nums w-14 shrink-0 text-right font-display font-expanded text-title",
                  view.act ? "text-attention" : "text-foreground",
                )}
                aria-hidden
              >
                {view.figure}
              </span>
              <span className="text-body">{view.text}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

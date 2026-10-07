import { useId } from "react";

import { sayFindings } from "@/lib/activity";
import { useT } from "@/lib/i18n";
import type { ActivityFinding } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * «Lo importante»: what a teacher should read first about the week, at most five sentences,
 * each led by the figure that backs it.
 *
 * The server ranks and types them (`server/activity.py`); the words are composed here
 * (`lib/activity.sayFindings`). The first one a teacher can act on is the screen's one
 * `--attention`; the rest are ink. With nothing to point out, one sentence says so.
 */
export function Findings({ findings }: { findings: ActivityFinding[] }) {
  const tr = useT();
  const id = useId();
  const views = sayFindings(findings, tr);
  return (
    <section aria-labelledby={id} className="surface space-y-3 p-5">
      <h3 id={id} className="text-heading">
        {tr.t("activity.important")}
      </h3>
      {views.length === 0 ? (
        <p className="text-body text-muted-foreground">{tr.t("activity.nothing")}</p>
      ) : (
        <ul className="rows">
          {views.map((view, index) => (
            <li key={index} className="flex items-baseline gap-4 py-3">
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

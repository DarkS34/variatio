import { Tags } from "lucide-react";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { RunView } from "@/state/runStore";
import { FeedRow, SlidingList, useSlidingWindow, VISIBLE } from "./LiveWindow";
import { useT } from "@/lib/i18n";

/**
 * The same window, fed by the tagger instead of by the extractor.
 *
 * Here it cannot be the file: re-tagging rewrites labels on items that were already there,
 * so `order=recent` returns the very same eight rows from beginning to end and nothing would
 * ever slide. What moves is the ORDER THE TAGGER WORKS IN, and only the event stream knows
 * it — one `item.tagged` per decision, newest on top, which is the same reading as the
 * build's feed. The buffer is the run's own, so a browser reloaded mid-run replays it.
 */
export function TagLive({ run }: { run: RunView | null }) {
  const { t } = useT();
  const tagged = run?.tagged;
  const latest = useMemo(() => tagged?.slice(0, VISIBLE), [tagged]);
  const rows = useSlidingWindow(latest);

  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <div className="flex items-baseline justify-between gap-3">
          <h4 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
            {t("bank.tagLive.title")}
          </h4>
          {run && run.taggedCount > 0 ? (
            <span className="text-small nums text-muted-foreground">
              {run.taggedCount} decidido(s)
            </span>
          ) : null}
        </div>

        {rows.length === 0 ? (
          <p className="text-body text-muted-foreground">
            {t("bank.tagLive.empty")}
          </p>
        ) : (
          <SlidingList rows={rows}>
            {(item) => (
              <FeedRow id={item.id} text={item.text}>
                {item.concepts.length === 0 ? (
                  <span className="flex items-center gap-1 text-small text-[var(--attention)]">
                    <Tags className="size-3" />
                    {t("bank.noConcept")}
                  </span>
                ) : (
                  item.concepts.map((concept) => (
                    <Badge
                      key={concept}
                      variant={concept === item.primary_concept ? "default" : "secondary"}
                    >
                      {concept}
                    </Badge>
                  ))
                )}
              </FeedRow>
            )}
          </SlidingList>
        )}
      </CardContent>
    </Card>
  );
}

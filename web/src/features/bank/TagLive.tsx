import { Tags } from "lucide-react";
import { useMemo } from "react";

import { ConceptBadge } from "@/components/ui/concept-chip";
import { Card, CardContent } from "@/components/ui/card";
import type { RunView } from "@/state/runStore";
import { FeedRow, SlidingList, useSlidingWindow, VISIBLE } from "./LiveWindow";
import { useT } from "@/lib/i18n";

/**
 * The same window, fed by the tagger instead of by the extractor.
 *
 * Here it cannot be the file: re-tagging rewrites labels on items that were already there,
 * so `order=recent` returns the very same ten rows from beginning to end and nothing would
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
                  /* The primary one FIRST and filled, like the bank's own row: this feed
                     says what the tagger is deciding, and which concept an exercise
                     PRACTISES is the decision — drawn in the raw order and in a tone, it
                     was neither first nor visible. */
                  [...item.concepts]
                    .sort(
                      (a, b) =>
                        Number(b === item.primary_concept) - Number(a === item.primary_concept),
                    )
                    .map((concept) => (
                      <ConceptBadge key={concept} primary={concept === item.primary_concept}>
                        {concept}
                      </ConceptBadge>
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

import { useQuery } from "@tanstack/react-query";
import { Tags } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { fieldText } from "@/lib/fields";
import type { BankItem, BankItemType } from "@/lib/types";
import { FeedRow, SlidingList, useSlidingWindow, VISIBLE } from "./LiveWindow";
import { useT } from "@/lib/i18n";

/**
 * What the builder has written so far, while it writes it.
 *
 * A stage's screen empties during a rebuild, and rightly so: what is on it is about to stop
 * being what one is looking at. This is not that — it is not the previous bank, it is the
 * one coming out — which is why it lives under the progress bar and is read-only: there is
 * nothing to edit in a file that is still being written.
 *
 * It is asked over REST and not through the event stream on purpose: a long build overruns
 * the event buffer, so a browser reloaded halfway would be left with nothing; the file, on
 * the other hand, is always there. And it comes sorted by id descending, which is the
 * extraction order reversed: the last thing written, on top.
 *
 * What that costs is the movement, and `useSlidingWindow` is what pays it back: a document
 * is written in ONE go, so every poll that lands one brings a whole burst, and the window
 * lets it in a row at a time. The feed therefore trails the file by a tick per row while it
 * catches up; the count in the corner is read from the file itself and does not.
 */
export function BankLive() {
  const { t } = useT();
  const query = useQuery({
    queryKey: ["bank", "live"],
    queryFn: () => api.bank({ order: "recent", page: 1, page_size: VISIBLE }),
    refetchInterval: 3_000,
    retry: false,
  });

  const listing = query.data;
  const rows = useSlidingWindow(listing?.items);

  const primaryFieldOf = (item: BankItem): string => {
    const types: BankItemType[] = listing?.item_types ?? [];
    if (types.length === 0) return "statement";
    const declared = item.item_type ? types.find((t) => t.key === item.item_type) : undefined;
    return (declared ?? types[0]).primary_field;
  };

  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <div className="flex items-baseline justify-between gap-3">
          <h4 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
            {t("bank.live.title")}
          </h4>
          {listing ? (
            <span className="text-small nums text-muted-foreground">
              {listing.totals.tagged}/{listing.totals.items} {t("bank.live.tagged")}
            </span>
          ) : null}
        </div>

        {rows.length === 0 ? (
          <p className="text-body text-muted-foreground">
            {t("bank.live.empty")}
          </p>
        ) : (
          <SlidingList rows={rows}>
            {(item) => {
              const concepts = item.concepts ?? [];
              return (
                <FeedRow id={item.id} text={fieldText(item[primaryFieldOf(item)])}>
                  {concepts.length === 0 ? (
                    <span className="flex items-center gap-1 text-small text-muted-foreground">
                      <Tags className="size-3" />
                      etiquetando…
                    </span>
                  ) : (
                    concepts.map((concept) => (
                      <Badge
                        key={concept}
                        variant={concept === item.primary_concept ? "default" : "secondary"}
                      >
                        {concept}
                      </Badge>
                    ))
                  )}
                </FeedRow>
              );
            }}
          </SlidingList>
        )}
      </CardContent>
    </Card>
  );
}

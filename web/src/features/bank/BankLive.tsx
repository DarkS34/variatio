import { useQuery } from "@tanstack/react-query";
import { Tags } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { truncate } from "@/lib/format";
import type { BankItem, BankItemType } from "@/lib/types";

const VISIBLE = 8;

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
 */
export function BankLive() {
  const query = useQuery({
    queryKey: ["bank", "live"],
    queryFn: () => api.bank({ order: "recent", page: 1, page_size: VISIBLE }),
    refetchInterval: 3_000,
    retry: false,
  });

  const listing = query.data;
  const items = listing?.items ?? [];

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
            Ítems que van saliendo
          </h4>
          {listing ? (
            <span className="text-small nums text-muted-foreground">
              {listing.totals.tagged}/{listing.totals.items} etiquetados
            </span>
          ) : null}
        </div>

        {items.length === 0 ? (
          <p className="text-body text-muted-foreground">
            Todavía no ha salido ningún ítem. Aparecerán aquí en cuanto el primer documento
            termine de extraerse.
          </p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => {
              const text = String(item[primaryFieldOf(item)] ?? "");
              const concepts = item.concepts ?? [];
              return (
                <li key={item.id} className="rounded-lg border border-border p-2.5">
                  <div className="flex items-baseline gap-2">
                    <code className="shrink-0 font-mono text-small text-muted-foreground">
                      {item.id}
                    </code>
                    <p className="min-w-0 flex-1 text-body">{truncate(text, 180)}</p>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1">
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
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

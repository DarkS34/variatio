import { ArrowRight, Inbox } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/misc";
import { when } from "@/lib/format";
import { cn } from "@/lib/utils";

import type { QueueItem } from "./types";
import { useT } from "@/lib/i18n";

/**
 * What somebody handed this evaluator, and the screen the tab opens on.
 *
 * The queue exists because the evaluator used to have to be an OPERATOR before being an
 * evaluator: pick concepts out of the graph, a modality, a curriculum, then wait minutes
 * on a GPU. For seven teachers with no stake in the system that is where the effort went.
 * Here there is nothing to configure and nothing to wait for.
 *
 * Who assigned each session is recorded and the administration panel reads it; it is
 * deliberately not on this screen, where it would invite reading the judgement as owed to
 * a person rather than to the study.
 */

/** A meter, and deliberately NOT the rail: a queue is a pile of independent judgements,
 *  and the rail means "a sequence whose steps depend on each other". */
function Meter({ items }: { items: QueueItem[] }) {
  const { t } = useT();
  return (
    <div className="flex h-1.5 gap-[3px]" role="img"
         aria-label={t("queue.progressLabel", {
        decided: items.filter((item) => item.decided || item.declined).length,
        total: items.length,
      })}>
      {items.map((item, index) => {
        const done = item.decided || item.declined;
        const next = !done && items.slice(0, index).every((earlier) => earlier.decided || earlier.declined);
        return (
          <span
            key={item.id}
            className={cn("flex-1", done ? "bg-settled" : next ? "bg-primary" : "bg-accent")}
          />
        );
      })}
    </div>
  );
}

function Concepts({ names }: { names: string[] }) {
  const { t } = useT();
  return <>{names.join(", ") || t("queue.noConcepts")}</>;
}

export function QueueTab({
  items,
  pending,
  typeLabel,
  onOpen,
}: {
  items: QueueItem[];
  pending: number;
  typeLabel: (key: string) => string;
  onOpen: (id: string) => void;
}) {
  const { t } = useT();
  if (items.length === 0) {
    return (
      // Not an error and not something to fix: it is the ordinary state until somebody
      // hands this account a set, so there is no action to offer here.
      <EmptyState icon={<Inbox />} title={t("queue.none")}>
        <p>{t("queue.noneBody")}</p>
      </EmptyState>
    );
  }

  const [next, ...rest] = items.filter((item) => !item.decided && !item.declined);
  const done = items.filter((item) => item.decided || item.declined);

  return (
    <div className="space-y-5">
      <Meter items={items} />

      {/* THE NEXT ONE. The ink border marks which card is live; the one "act here" colour
          is spent once, on its button, because that is the only thing here to actually do —
          everything else on this screen is a record. */}
      {next ? (
        <div className="flex flex-wrap items-center gap-6 border border-primary bg-card p-5 shadow-sm">
          <div className="min-w-56 flex-1">
            <p className="text-micro font-condensed text-muted-foreground uppercase">{t("queue.next")}</p>
            <h2 className="mt-1.5 text-title">
              <Concepts names={next.concepts} />
            </h2>
            <div className="mt-2.5 flex flex-wrap items-center gap-2.5">
              <span className="border border-border px-2 py-0.5 text-small">
                {typeLabel(next.item_type)}
              </span>
              <span className="text-small text-muted-foreground">
                {when(new Date(next.created_at * 1000).toISOString())}
              </span>
            </div>
          </div>
          <Button variant="attention" onClick={() => onOpen(next.id)}>
            {t("queue.open")}
            <ArrowRight />
          </Button>
        </div>
      ) : null}

      {rest.length > 0 ? (
        <div className="border border-border bg-card shadow-sm">
          <div className="border-b border-border bg-muted px-4 py-2.5">
            <p className="text-micro font-condensed text-muted-foreground uppercase">
              {t("queue.pendingMore", { n: rest.length })}
            </p>
          </div>
          {rest.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onOpen(item.id)}
              className="flex w-full items-center gap-3.5 border-b border-border px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-accent/40"
            >
              <span className="size-4 shrink-0 border border-input" />
              <span className="flex-1 truncate text-body font-medium">
                <Concepts names={item.concepts} />
              </span>
              <span className="shrink-0 border border-border px-2 py-0.5 text-small">
                {typeLabel(item.item_type)}
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {done.length > 0 ? (
        <div className="border border-border bg-card shadow-sm">
          <div className="border-b border-border bg-muted px-4 py-2.5">
            <p className="text-micro font-condensed text-muted-foreground uppercase">
              {t("queue.alreadyJudged", { n: done.length })}
            </p>
          </div>
          {done.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onOpen(item.id)}
              className="flex w-full items-center gap-3.5 border-b border-border px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-accent/40"
            >
              {/* A decline is NOT drawn in --destructive. Red is this palette's correction
                  colour, and «no tengo criterio» is a fact about which subject this panel
                  can judge — not a mistake by whoever said it. */}
              <span
                className={cn(
                  "size-4 shrink-0 border",
                  item.declined ? "border-dashed border-settled" : "border-settled bg-settled",
                )}
              />
              <span className="flex-1 truncate text-body text-muted-foreground">
                <Concepts names={item.concepts} />
              </span>
              <span className="shrink-0 text-micro font-condensed text-settled uppercase">
                {item.declined ? t("queue.declined") : t("queue.judged")}
              </span>
            </button>
          ))}
        </div>
      ) : null}

      {pending === 0 ? (
        <p className="text-center text-small text-muted-foreground">
          {t("queue.allDone")}
        </p>
      ) : null}
    </div>
  );
}

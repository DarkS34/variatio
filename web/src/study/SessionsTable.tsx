import { Trash2 } from "lucide-react";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox, EmptyState } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { when } from "@/lib/format";

import { ARM_META, letterFor } from "./arms";
import { useDeleteOwnEvaluations } from "./queries";
import type { EvaluationSummary } from "./types";
import { useSelection } from "./useSelection";
import { useT } from "@/lib/i18n";

/**
 * Your own comparisons, so you can reopen one you left undecided.
 *
 * What this table used to carry and deliberately no longer does: the study's aggregates —
 * preferences against chance, reliability per arm, the rubric, the effect of reasoning —
 * and the CSV export. Both moved to the administration panel in phase 3.
 *
 * The reason is not tidiness. Showing an evaluator the running score of the thing they
 * are about to judge is an invitation to even it out, and it is the same argument that
 * makes the comparison blind in the first place: a judgement is only worth recording if
 * nothing on screen told the person which way it was going.
 */
export function SessionsTable({
  sessions,
  total,
  onOpen,
  onDeleted,
}: {
  sessions: EvaluationSummary[];
  total: number;
  onOpen: (id: string) => void;
  onDeleted?: (ids: string[]) => void;
}) {
  const { plural } = useT();
  const { t } = useT();
  const toast = useToast();
  const remove = useDeleteOwnEvaluations();
  const ids = useMemo(() => sessions.map((session) => session.id), [sessions]);
  const selection = useSelection(ids);

  const confirmDelete = () => {
    const chosen = [...selection.selected];
    const decided = sessions.filter(
      (session) => selection.selected.has(session.id) && session.chosen_at !== null,
    ).length;
    const message =
      plural("sessions.confirmHead", chosen.length) +
      (decided ? t("sessions.confirmDecided", { n: decided }) : "") +
      t("sessions.confirmTail");
    if (!window.confirm(message)) return;
    remove.mutate(chosen, {
      onSuccess: ({ deleted }) => {
        selection.clear();
        onDeleted?.(deleted);
        toast({
          title: t("sessions.deleted"),
          description: plural("sessions.deletedCount", deleted.length),
          tone: "attention",
        });
      },
      onError: (error: Error) =>
        toast({ title: t("sessions.deleteFailed"), description: error.message, tone: "danger" }),
    });
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h2 className="text-body font-semibold">
          {t("sessions.title")}
          <span className="ml-2 font-normal nums text-muted-foreground">{total}</span>
        </h2>
        {selection.selected.size > 0 ? (
          <span className="text-small text-muted-foreground">
            {plural("sessions.selected", selection.selected.size)}
          </span>
        ) : null}
        {sessions.length > 0 ? (
          <Button
            variant="destructive"
            size="sm"
            className="ml-auto"
            disabled={selection.selected.size === 0 || remove.isPending}
            onClick={confirmDelete}
          >
            <Trash2 />
            {t("sessions.deleteSelection")}
          </Button>
        ) : null}
      </div>

      {sessions.length === 0 ? (
        <EmptyState title={t("sessions.empty")}>{t("sessions.emptyBody")}</EmptyState>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table minWidth="36rem">
            <THead>
              <TR>
                <TH className="w-8">
                  <Checkbox
                    checked={selection.all}
                    indeterminate={selection.some}
                    onCheckedChange={selection.toggleAll}
                    label={
                      selection.all
                        ? t("sessions.deselectAll")
                        : t("sessions.selectAll")
                    }
                  />
                </TH>
                <TH>{t("sessions.col.when")}</TH>
                <TH>{t("sessions.col.concepts")}</TH>
                <TH>{t("sessions.col.choice")}</TH>
                <TH>{t("sessions.col.reasoned")}</TH>
                <TH align="num">{t("sessions.col.rubric")}</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {sessions.map((session) => {
                const meta = session.choice_arm ? ARM_META[session.choice_arm] : null;
                return (
                  <TR key={session.id} selected={selection.selected.has(session.id)}>
                    <TD className="py-2 pl-3">
                      <Checkbox
                        checked={selection.selected.has(session.id)}
                        onCheckedChange={(next) => selection.toggle(session.id, next)}
                        label={t("sessions.selectOne", { id: session.id })}
                      />
                    </TD>
                    <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
                      {when(new Date(session.created_at * 1000).toISOString())}
                    </TD>
                    <TD className="max-w-64 truncate px-3 py-2">
                      {session.concepts.join(" · ")}
                    </TD>
                    <TD className="whitespace-nowrap px-3 py-2 text-small">
                      {session.chosen_at === null ? (
                        <span className="text-muted-foreground">{t("sessions.undecided")}</span>
                      ) : session.choice === null ? (
                        <span className="text-muted-foreground">{t("sessions.none")}</span>
                      ) : (
                        <span className="flex items-center gap-1.5">
                          <span
                            className="flex size-5 items-center justify-center rounded font-mono text-[11px]"
                            style={{
                              backgroundColor: meta?.colour,
                              color: "var(--background)",
                            }}
                          >
                            {letterFor(session.choice)}
                          </span>
                          {meta ? t(meta.shortKey) : null}
                        </span>
                      )}
                    </TD>
                    <TD className="px-3 py-2 text-small text-muted-foreground">
                      {session.think === null ? "—" : session.think ? t("fair.yes") : t("fair.no")}
                    </TD>
                    <TD className="px-3 py-2 text-small text-muted-foreground">
                      {session.rated ? t("fair.yes") : "—"}
                    </TD>
                    <TD className="px-3 py-2 text-right">
                      <Button variant="ghost" size="sm" onClick={() => onOpen(session.id)}>
                        {t("sessions.open")}
                      </Button>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </div>
      )}
    </div>
  );
}

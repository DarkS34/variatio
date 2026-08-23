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
      `¿Borrar ${chosen.length} comparación(es)?\n\n` +
      (decided ? `${decided} de ellas ya tienen elección y dejan de contar en el estudio.\n` : "") +
      "\nNo se puede deshacer.";
    if (!window.confirm(message)) return;
    remove.mutate(chosen, {
      onSuccess: ({ deleted }) => {
        selection.clear();
        onDeleted?.(deleted);
        toast({
          title: "Comparaciones borradas",
          description: `${deleted.length} sesión(es)`,
          tone: "attention",
        });
      },
      onError: (error: Error) =>
        toast({ title: "No se ha podido borrar", description: error.message, tone: "danger" }),
    });
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h2 className="text-body font-semibold">
          Tus comparaciones
          <span className="ml-2 font-normal nums text-muted-foreground">{total}</span>
        </h2>
        {selection.selected.size > 0 ? (
          <span className="text-small text-muted-foreground">
            {selection.selected.size} seleccionada(s)
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
            Borrar selección
          </Button>
        ) : null}
      </div>

      {sessions.length === 0 ? (
        <EmptyState title="Todavía no has comparado nada">
          Lanza una comparación y aquí quedará el registro de lo que has evaluado.
        </EmptyState>
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
                        ? "Deseleccionar todas las comparaciones"
                        : "Seleccionar todas las comparaciones"
                    }
                  />
                </TH>
                <TH>Cuándo</TH>
                <TH>Conceptos</TH>
                <TH>Elección</TH>
                <TH>Razonó</TH>
                <TH align="num">Rúbrica</TH>
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
                        label={`Seleccionar la comparación ${session.id}`}
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
                        <span className="text-muted-foreground">sin decidir</span>
                      ) : session.choice === null ? (
                        <span className="text-muted-foreground">ninguna</span>
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
                          {meta?.short}
                        </span>
                      )}
                    </TD>
                    <TD className="px-3 py-2 text-small text-muted-foreground">
                      {session.think === null ? "—" : session.think ? "sí" : "no"}
                    </TD>
                    <TD className="px-3 py-2 text-small text-muted-foreground">
                      {session.rated ? "sí" : "—"}
                    </TD>
                    <TD className="px-3 py-2 text-right">
                      <Button variant="ghost" size="sm" onClick={() => onOpen(session.id)}>
                        Abrir
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

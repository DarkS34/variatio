import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { when } from "@/lib/format";
import type { EvaluationSummary } from "@/lib/types";

import { ARM_META, letterFor } from "./arms";

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
}: {
  sessions: EvaluationSummary[];
  total: number;
  onOpen: (id: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">
          Tus comparaciones
          <span className="ml-2 font-normal nums text-muted-foreground">{total}</span>
        </h2>
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
                  <TR key={session.id}>
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

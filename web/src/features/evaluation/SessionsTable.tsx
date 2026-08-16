import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/misc";
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
          <span className="ml-2 font-normal tabular-nums text-muted-foreground">{total}</span>
        </h2>
      </div>

      {sessions.length === 0 ? (
        <EmptyState title="Todavía no has comparado nada">
          Lanza una comparación y aquí quedará el registro de lo que has evaluado.
        </EmptyState>
      ) : (
        <div className="thin-scroll overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">Cuándo</th>
                <th className="px-3 py-2 text-left font-medium">Conceptos</th>
                <th className="px-3 py-2 text-left font-medium">Elección</th>
                <th className="px-3 py-2 text-left font-medium">Razonó</th>
                <th className="px-3 py-2 text-left font-medium">Rúbrica</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => {
                const meta = session.choice_arm ? ARM_META[session.choice_arm] : null;
                return (
                  <tr key={session.id} className="border-b border-border/50 last:border-0">
                    <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                      {when(new Date(session.created_at * 1000).toISOString())}
                    </td>
                    <td className="max-w-64 truncate px-3 py-2">
                      {session.concepts.join(" · ")}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-xs">
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
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {session.think === null ? "—" : session.think ? "sí" : "no"}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {session.rated ? "sí" : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Button variant="ghost" size="sm" onClick={() => onOpen(session.id)}>
                        Abrir
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

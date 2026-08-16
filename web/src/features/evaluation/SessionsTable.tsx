import { Download } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/misc";
import { duration, when } from "@/lib/format";
import type { EvaluationAggregates, EvaluationSummary, ThinkSlice } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ARM_META, letterFor } from "./arms";

const CHANCE = 1 / 3;

/**
 * How often each arm was picked, read against chance.
 *
 * One row per arm rather than a stacked bar, because the question this study asks is
 * "did the system beat 1 in 3?" — and a stacked bar makes exactly that comparison hard.
 * The dashed marker IS the null hypothesis, drawn where it can be seen.
 *
 * Colour is not the carrier of identity here: every row is named. The system's row is
 * the only one tinted, because it is the entity under test.
 */
function Preferences({ aggregates }: { aggregates: EvaluationAggregates }) {
  const decided = aggregates.decided || 0;
  const rows = [
    ...(["system", "rag", "naive"] as const).map((arm) => ({
      key: arm,
      label: ARM_META[arm].label,
      count: aggregates.preferences[arm] ?? 0,
      highlight: arm === "system",
    })),
    {
      key: "none",
      label: "Ninguna convenció",
      count: aggregates.preferences.none ?? 0,
      highlight: false,
    },
  ];

  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2">
        <h3 className="text-xs font-medium">Cuántas veces ganó cada una</h3>
        <span className="text-[11px] text-muted-foreground">
          {decided} sesión{decided === 1 ? "" : "es"} con elección
        </span>
      </div>
      {decided === 0 ? (
        <p className="text-xs text-muted-foreground">
          Todavía no hay elecciones registradas.
        </p>
      ) : (
        <div className="space-y-1.5">
          {rows.map((row) => {
            const share = decided ? row.count / decided : 0;
            return (
              <div key={row.key} className="flex items-center gap-2">
                <span className="w-40 shrink-0 truncate text-xs text-muted-foreground">
                  {row.label}
                </span>
                <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      row.highlight ? "bg-primary" : "bg-muted-foreground/45",
                    )}
                    style={{ width: `${Math.round(share * 100)}%` }}
                  />
                  <span
                    className="absolute inset-y-0 w-px bg-foreground/35"
                    style={{ left: `${CHANCE * 100}%` }}
                    aria-hidden
                  />
                </div>
                <span className="w-16 shrink-0 text-right text-xs tabular-nums">
                  {row.count}
                  <span className="ml-1 text-muted-foreground">
                    {Math.round(share * 100)} %
                  </span>
                </span>
              </div>
            );
          })}
          <p className="text-[11px] text-muted-foreground">
            La línea vertical marca el 33 %: lo que saldría por azar.
          </p>
        </div>
      )}
    </div>
  );
}

/** A failed arm is a result, not an accident — reliability is part of the comparison. */
function Reliability({ aggregates }: { aggregates: EvaluationAggregates }) {
  // Counted over judged sessions only, like the server counts them: a pending session
  // must not contribute a number that identifies one of its own cards.
  const total = aggregates.decided || 0;
  if (total === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium">Propuestas sin ítem válido</h3>
      <div className="grid grid-cols-3 gap-2">
        {(["naive", "rag", "system"] as const).map((arm) => {
          const counts = aggregates.arm_status[arm] ?? {};
          const bad = (counts.failed ?? 0) + (counts.unavailable ?? 0);
          return (
            <div key={arm} className="rounded-lg border border-border px-2.5 py-1.5">
              <p className="truncate text-[11px] text-muted-foreground">{ARM_META[arm].short}</p>
              <p
                className={cn(
                  "text-sm tabular-nums",
                  bad > 0 ? "text-[var(--warning)]" : "text-foreground",
                )}
              >
                {bad}
                <span className="ml-1 text-xs text-muted-foreground">
                  de {total}
                </span>
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const RUBRIC_LABELS: Record<string, string> = {
  originality: "Originalidad",
  complexity: "Exigencia",
  concept_fit: "Ajuste al concepto",
  soundness: "Planteamiento",
};

function Rubric({ aggregates }: { aggregates: EvaluationAggregates }) {
  const rubric = aggregates.rubric ?? { n: 0 };
  if (!rubric.n) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2">
        <h3 className="text-xs font-medium">Rúbrica sobre la variante del sistema</h3>
        <span className="text-[11px] text-muted-foreground">{rubric.n} valorada{rubric.n === 1 ? "" : "s"}</span>
      </div>
      <div className="space-y-1.5">
        {Object.keys(RUBRIC_LABELS).map((key) => {
          const entry = rubric[key];
          if (!entry) return null;
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="w-40 shrink-0 truncate text-xs text-muted-foreground">
                {RUBRIC_LABELS[key]}
              </span>
              <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${((entry.mean - 1) / 4) * 100}%` }}
                />
                {key === "complexity" ? (
                  <span
                    className="absolute inset-y-0 w-px bg-foreground/35"
                    style={{ left: "50%" }}
                    aria-hidden
                  />
                ) : null}
              </div>
              <span className="w-16 shrink-0 text-right text-xs tabular-nums">
                {entry.mean.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>
      {rubric.complexity?.mean_distance_to_3 !== undefined ? (
        <p className="text-[11px] text-muted-foreground">
          En exigencia el objetivo es el 3, no el 5: la distancia media al 3 es{" "}
          <span className="tabular-nums">{rubric.complexity.mean_distance_to_3}</span>.
        </p>
      ) : null}
    </div>
  );
}

/**
 * ¿Sirve de algo el razonamiento previo?
 *
 * La otra pregunta del estudio, y la única que estas sesiones pueden responder porque el
 * modo se sortea en vez de elegirse: si lo decidiera quien evalúa, cada bloque de sesiones
 * llevaría dentro su estado de ánimo y su prisa, y la comparación no mediría el modo.
 *
 * Se cuenta sobre sesiones ya juzgadas —como todo lo demás aquí— y se muestra el tiempo
 * al lado de los aciertos: deliberar no es gratis, y el precio es parte de la respuesta.
 */
function ThinkEffect({ aggregates }: { aggregates: EvaluationAggregates }) {
  const think = aggregates.think;
  if (!think) return null;

  const total = think.on.decided + think.off.decided;
  const wins = (slice: ThinkSlice) => slice.preferences?.system ?? 0;
  const share = (slice: ThinkSlice) =>
    slice.decided ? `${Math.round((wins(slice) / slice.decided) * 100)} %` : "—";
  const mean = (slice: ThinkSlice, key: string) => {
    const entry = slice.rubric?.[key];
    return entry?.mean !== undefined ? entry.mean.toFixed(1) : "—";
  };

  const rows: { label: string; on: string; off: string }[] = [
    {
      label: "Sesiones decididas",
      on: String(think.on.decided),
      off: String(think.off.decided),
    },
    {
      label: "Ganó el sistema",
      on: `${wins(think.on)} · ${share(think.on)}`,
      off: `${wins(think.off)} · ${share(think.off)}`,
    },
    {
      label: "Tiempo medio del sistema",
      on: think.on.elapsed_ms?.system ? duration(think.on.elapsed_ms.system) : "—",
      off: think.off.elapsed_ms?.system ? duration(think.off.elapsed_ms.system) : "—",
    },
    ...Object.entries(RUBRIC_LABELS)
      .map(([key, label]) => ({
        label,
        on: mean(think.on, key),
        off: mean(think.off, key),
      }))
      .filter((row) => row.on !== "—" || row.off !== "—"),
  ];

  return (
    <div className="space-y-2 border-t border-border pt-3 lg:col-span-2">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="text-xs font-medium">¿Aporta algo el razonamiento previo?</h3>
        <span className="text-[11px] text-muted-foreground">
          se sortea al empezar cada sesión, igual para las dos propuestas locales
        </span>
      </div>

      {total === 0 ? (
        <p className="text-xs text-muted-foreground">
          Todavía no hay sesiones juzgadas de las que sacar la comparación.
        </p>
      ) : (
        <>
          <div className="thin-scroll overflow-x-auto">
            <table className="w-full min-w-[22rem] text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="py-1.5 pr-3 text-left font-medium" />
                  <th className="px-3 py-1.5 text-right font-medium">Con razonamiento</th>
                  <th className="py-1.5 pl-3 text-right font-medium">Sin razonamiento</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.label} className="border-b border-border/50 last:border-0">
                    <td className="py-1.5 pr-3 text-muted-foreground">{row.label}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{row.on}</td>
                    <td className="py-1.5 pl-3 text-right tabular-nums">{row.off}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {think.on.decided === 0 || think.off.decided === 0 ? (
            <p className="text-[11px] text-muted-foreground">
              Falta uno de los dos lados: hasta que el sorteo llene ambas columnas no hay
              comparación posible.
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

export function SessionsTable({
  sessions,
  aggregates,
  onOpen,
}: {
  sessions: EvaluationSummary[];
  aggregates: EvaluationAggregates;
  onOpen: (id: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 rounded-xl border border-border bg-card p-3 shadow-sm lg:grid-cols-2">
        <Preferences aggregates={aggregates} />
        <div className="space-y-4">
          <Reliability aggregates={aggregates} />
          <Rubric aggregates={aggregates} />
        </div>
        <ThinkEffect aggregates={aggregates} />
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">
            Sesiones
            <span className="ml-2 font-normal tabular-nums text-muted-foreground">
              {aggregates.sessions}
            </span>
          </h2>
          <a
            href="/api/evaluation/export.csv"
            download
            className={cn(buttonVariants({ variant: "outline", size: "sm" }), "ml-auto")}
          >
            <Download />
            CSV
          </a>
        </div>

        {sessions.length === 0 ? (
          <EmptyState title="Todavía no has comparado nada">
            Lanza una comparación y aquí quedará el registro de lo evaluado.
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
    </div>
  );
}

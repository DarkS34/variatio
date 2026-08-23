import { Download } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { BarRows, DayColumns, ShareMeter, type BarRow } from "@/features/admin/charts";
import { duration, when } from "@/lib/format";
import { cn } from "@/lib/utils";

import { ARM_META } from "./arms";
import { useAdminEvaluations } from "./queries";
import { studyApi } from "./api";
import type { AdminGroup, EvaluationAggregates, EvaluationArm } from "./types";

/** A three-way blind choice: what pure chance would produce. Every share is read
 *  against it, and the panel never shows one without drawing the other. */
const CHANCE = 1 / 3;

/** The order the arm palette was validated on. Anything that draws the three side by
 *  side draws them in it — the CVD check is over ADJACENT pairs. */
const ARMS: EvaluationArm[] = ["naive", "rag", "system"];

const RUBRIC_LABELS: Record<string, string> = {
  originality: "Originalidad",
  complexity: "Exigencia",
  concept_fit: "Ajuste al concepto",
  soundness: "Planteamiento",
};

export function StudyTab({
  data,
  loading,
  workspace,
  account,
  onWorkspace,
  onAccount,
}: {
  data: ReturnType<typeof useAdminEvaluations>["data"];
  loading: boolean;
  workspace: string | null;
  account: number | null;
  onWorkspace: (slug: string | null) => void;
  onAccount: (id: number | null) => void;
}) {
  if (loading && !data) return <Skeleton className="h-96" />;
  if (!data) return null;

  const filtered = Boolean(workspace || account !== null);
  const csv = studyApi.adminEvaluationCsvUrl({ workspace, account });

  return (
    <div className="space-y-5">
      {/* Filters in one row above the charts, so what is being looked at is stated
          before the numbers rather than inferred from them. */}
      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label="Filtrar el estudio por workspace"
          value={workspace ?? ""}
          onChange={(event) => onWorkspace(event.target.value || null)}
          className="w-56"
        >
          <option value="">Todos los workspaces</option>
          {data.filters.workspaces.map((slug) => (
            <option key={slug} value={slug}>
              {slug}
            </option>
          ))}
        </Select>

        {account !== null ? (
          <Button variant="outline" size="sm" onClick={() => onAccount(null)}>
            Quitar el filtro de cuenta
          </Button>
        ) : null}

        {filtered ? (
          <span className="text-small text-muted-foreground">
            {data.aggregates.sessions} sesión(es) en el filtro
          </span>
        ) : null}

        <a
          href={csv}
          download
          className={cn(buttonVariants({ variant: "outline", size: "sm" }), "ml-auto")}
        >
          <Download />
          CSV{filtered ? " (filtrado)" : ""}
        </a>
      </div>

      {data.aggregates.sessions === 0 ? (
        <EmptyState title="Todavía no hay comparaciones registradas">
          En cuanto alguien evalúe, aquí aparecerá el marcador y podrás descargarlo.
        </EmptyState>
      ) : (
        <>
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <Card title="Cuántas veces ganó cada propuesta">
              <Preferences aggregates={data.aggregates} />
            </Card>
            <Card title="Ritmo del estudio">
              <DayColumns points={data.per_day} />
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <Card title="Rúbrica sobre la variante del sistema">
              <Rubric aggregates={data.aggregates} />
            </Card>
            <Card title="¿Aporta algo el razonamiento previo?">
              <ThinkEffect aggregates={data.aggregates} />
            </Card>
          </div>

          <Card title="Por cuenta">
            <GroupTable
              groups={data.by_account}
              firstHeader="Evaluador"
              onSelect={(group) => onAccount(Number(group.key) || null)}
            />
          </Card>

          <Card title="Por workspace">
            <GroupTable
              groups={data.by_workspace}
              firstHeader="Workspace"
              onSelect={(group) => onWorkspace(String(group.key) || null)}
            />
          </Card>

          <Card title={`Sesiones (${data.sessions.length})`}>
            <SessionsTable rows={data.sessions} />
          </Card>
        </>
      )}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-3 shadow-sm">
      <h2 className="text-small font-medium">{title}</h2>
      {children}
    </section>
  );
}

/**
 * The question the study exists to answer, drawn so it can be answered.
 *
 * One row per arm rather than a stack, because "did the system beat 1 in 3?" is a
 * comparison against a line and a stacked bar makes exactly that comparison hard. The
 * reference line IS the null hypothesis, drawn where it can be seen.
 */
function Preferences({ aggregates }: { aggregates: EvaluationAggregates }) {
  const decided = aggregates.decided || 0;
  const rows: BarRow[] = [
    ...ARMS.map((arm) => ({
      key: arm,
      label: ARM_META[arm].label,
      value: aggregates.preferences[arm] ?? 0,
      colour: ARM_META[arm].colour,
      detail: aggregates.elapsed_ms?.[arm]
        ? `${ARM_META[arm].short} · ${duration(aggregates.elapsed_ms[arm])} de media`
        : ARM_META[arm].short,
    })),
    {
      key: "none",
      label: "Ninguna convenció",
      value: aggregates.preferences.none ?? 0,
      colour: "var(--muted-foreground)",
    },
  ];

  return (
    <div className="space-y-2">
      <p className="text-micro text-muted-foreground">
        {decided} sesión{decided === 1 ? "" : "es"} con elección, de {aggregates.sessions}
      </p>
      <BarRows
        rows={rows}
        total={decided}
        reference={CHANCE}
        referenceLabel="La línea vertical marca el 33 %: lo que saldría por azar."
      />
      <Reliability aggregates={aggregates} />
    </div>
  );
}

/** A failed arm is a result, not an accident — reliability is part of the comparison. */
function Reliability({ aggregates }: { aggregates: EvaluationAggregates }) {
  const total = aggregates.decided || 0;
  if (total === 0) return null;

  return (
    <div className="space-y-1.5 border-t border-border pt-2">
      <h3 className="text-micro font-medium text-muted-foreground">
        Propuestas sin ítem válido
      </h3>
      <div className="grid grid-cols-3 gap-2">
        {ARMS.map((arm) => {
          const counts = aggregates.arm_status[arm] ?? {};
          const bad = (counts.failed ?? 0) + (counts.unavailable ?? 0);
          return (
            <div key={arm} className="rounded-lg border border-border px-2.5 py-1.5">
              <p className="flex items-center gap-1.5 truncate text-micro text-muted-foreground">
                <span
                  className="size-2 shrink-0 rounded-[2px]"
                  style={{ backgroundColor: ARM_META[arm].colour }}
                />
                {ARM_META[arm].short}
              </p>
              <p
                className={cn(
                  "text-body nums",
                  bad > 0 ? "text-[var(--attention)]" : "text-foreground",
                )}
              >
                {bad}
                <span className="ml-1 text-small text-muted-foreground">de {total}</span>
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Rubric({ aggregates }: { aggregates: EvaluationAggregates }) {
  const rubric = aggregates.rubric ?? { n: 0 };
  if (!rubric.n) {
    return <p className="text-small text-muted-foreground">Ninguna sesión valorada todavía.</p>;
  }

  return (
    <div className="space-y-2">
      <p className="text-micro text-muted-foreground">
        {rubric.n} valorada{rubric.n === 1 ? "" : "s"} · escala de 1 a 5
      </p>
      <div className="space-y-1.5">
        {Object.keys(RUBRIC_LABELS).map((key) => {
          const entry = rubric[key];
          if (!entry) return null;
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="w-40 shrink-0 truncate text-small text-muted-foreground">
                {RUBRIC_LABELS[key]}
              </span>
              <div className="relative h-2.5 flex-1 overflow-hidden rounded-[2px] bg-muted">
                <div
                  className="h-full rounded-r-[4px] bg-primary"
                  style={{ width: `${((entry.mean - 1) / 4) * 100}%` }}
                />
                {key === "complexity" ? (
                  <span
                    aria-hidden
                    className="absolute inset-y-0 w-px bg-foreground/35"
                    style={{ left: "50%" }}
                  />
                ) : null}
              </div>
              <span className="w-10 shrink-0 text-right text-small nums">
                {entry.mean.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>
      {rubric.complexity?.mean_distance_to_3 !== undefined ? (
        <p className="text-micro text-muted-foreground">
          En exigencia el objetivo es el 3, no el 5 — de ahí la marca central. La distancia
          media al 3 es{" "}
          <span className="nums">{rubric.complexity.mean_distance_to_3}</span>.
        </p>
      ) : null}
    </div>
  );
}

/**
 * The other question the sessions can answer, and a table rather than a chart on purpose:
 * six rows of unrelated units — counts, percentages, seconds and 1-5 means — is exactly
 * the case where a chart would have to invent a shared axis it does not have.
 */
function ThinkEffect({ aggregates }: { aggregates: EvaluationAggregates }) {
  const think = aggregates.think;
  if (!think) return null;
  const total = think.on.decided + think.off.decided;
  if (total === 0) {
    return (
      <p className="text-small text-muted-foreground">
        Todavía no hay sesiones juzgadas de las que sacar la comparación.
      </p>
    );
  }

  const share = (slice: typeof think.on) =>
    slice.decided
      ? `${slice.preferences?.system ?? 0} · ${Math.round(((slice.preferences?.system ?? 0) / slice.decided) * 100)} %`
      : "—";
  const mean = (slice: typeof think.on, key: string) => {
    const entry = slice.rubric?.[key];
    return entry?.mean !== undefined ? entry.mean.toFixed(1) : "—";
  };

  const rows: { label: string; on: string; off: string }[] = [
    { label: "Sesiones decididas", on: String(think.on.decided), off: String(think.off.decided) },
    { label: "Ganó el sistema", on: share(think.on), off: share(think.off) },
    {
      label: "Tiempo medio del sistema",
      on: think.on.elapsed_ms?.system ? duration(think.on.elapsed_ms.system) : "—",
      off: think.off.elapsed_ms?.system ? duration(think.off.elapsed_ms.system) : "—",
    },
    ...Object.entries(RUBRIC_LABELS)
      .map(([key, label]) => ({ label, on: mean(think.on, key), off: mean(think.off, key) }))
      .filter((row) => row.on !== "—" || row.off !== "—"),
  ];

  return (
    <div className="space-y-2">
      <p className="text-micro text-muted-foreground">
        El modo se sortea al empezar cada sesión, igual para las dos propuestas locales.
      </p>
      <div>
        <Table minWidth="22rem">
          <THead>
            <TR>
              <TH />
              <TH align="num">Con razonamiento</TH>
              <TH align="num">Sin razonamiento</TH>
            </TR>
          </THead>
          <TBody>
            {rows.map((row) => (
              <TR key={row.label}>
                <TD className="py-1.5 pr-3 text-muted-foreground">{row.label}</TD>
                <TD align="num" className="px-3 py-1.5  nums">{row.on}</TD>
                <TD align="num" className="py-1.5 pl-3  nums">{row.off}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
      {think.on.decided === 0 || think.off.decided === 0 ? (
        <p className="text-micro text-muted-foreground">
          Falta uno de los dos lados: hasta que el sorteo llene ambas columnas no hay
          comparación posible.
        </p>
      ) : null}
    </div>
  );
}

/**
 * The study grouped, as a table.
 *
 * `sesiones` and `decididas` are separate columns on purpose: somebody who launched
 * twenty comparisons and judged three has contributed three data points, and a single
 * count would say the opposite.
 */
function GroupTable({
  groups,
  firstHeader,
  onSelect,
}: {
  groups: AdminGroup[];
  firstHeader: string;
  onSelect: (group: AdminGroup) => void;
}) {
  if (groups.length === 0) {
    return <p className="text-small text-muted-foreground">Nada que agrupar todavía.</p>;
  }

  return (
    <div>
      <Table minWidth="42rem">
        <THead>
          <TR>
            <TH>{firstHeader}</TH>
            <TH align="num">Sesiones</TH>
            <TH align="num">Decididas</TH>
            <TH>Ganó el sistema</TH>
            <TH align="num">Valoradas</TH>
            <TH align="num">Última</TH>
          </TR>
        </THead>
        <TBody>
          {groups.map((group) => (
            <TR key={String(group.key)} onSelect={() => onSelect(group)}>
              <TD className="max-w-56 truncate py-1.5 pr-3">
                {group.label}
                {group.name && group.name !== group.label ? (
                  <span className="ml-1 text-muted-foreground">· {group.name}</span>
                ) : null}
              </TD>
              <TD align="num" className="px-3 py-1.5  nums">{group.sessions}</TD>
              <TD align="num" className="px-3 py-1.5  nums">{group.decided}</TD>
              <TD className="px-3 py-1.5">
                <ShareMeter
                  value={group.preferences?.system ?? 0}
                  total={group.decided}
                  reference={CHANCE}
                  title={`${group.preferences?.system ?? 0} de ${group.decided}; la marca es el 33 % del azar`}
                />
              </TD>
              <TD align="num" className="px-3 py-1.5  nums">{group.rated}</TD>
              <TD align="num" className="whitespace-nowrap py-1.5 pl-3  text-muted-foreground">
                {group.last_at
                  ? when(new Date(group.last_at * 1000).toISOString())
                  : "—"}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function SessionsTable({ rows }: { rows: NonNullable<ReturnType<typeof useAdminEvaluations>["data"]>["sessions"] }) {
  return (
    <div className="thin-scroll max-h-[28rem] overflow-y-auto">
      <Table minWidth="48rem">
        <THead>
          <TR>
            <TH>Cuándo</TH>
            <TH>Evaluador</TH>
            <TH>Workspace</TH>
            <TH>Conceptos</TH>
            <TH>Eligió</TH>
            <TH className="text-center">Razonó</TH>
            <TH>Nota</TH>
          </TR>
        </THead>
        <TBody>
          {rows.map((row) => {
            const meta = row.choice_arm ? ARM_META[row.choice_arm] : null;
            return (
              <TR key={row.id}>
                <TD className="whitespace-nowrap py-1.5 pr-3 text-muted-foreground">
                  {when(new Date(row.created_at * 1000).toISOString())}
                </TD>
                <TD className="max-w-44 truncate px-3 py-1.5">{row.account ?? "—"}</TD>
                <TD className="px-3 py-1.5 font-mono text-micro text-muted-foreground">
                  {row.workspace ?? "—"}
                </TD>
                <TD className="max-w-52 truncate px-3 py-1.5">{row.concepts.join(" · ")}</TD>
                <TD className="whitespace-nowrap px-3 py-1.5">
                  {row.chosen_at === null ? (
                    <span className="text-muted-foreground">sin decidir</span>
                  ) : meta ? (
                    <span className="flex items-center gap-1.5">
                      <span
                        className="size-2 shrink-0 rounded-[2px]"
                        style={{ backgroundColor: meta.colour }}
                      />
                      {meta.short}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">ninguna</span>
                  )}
                </TD>
                <TD className="px-3 py-1.5 text-center text-muted-foreground">
                  {row.think ? "sí" : "no"}
                </TD>
                <TD className="max-w-64 truncate py-1.5 pl-3 text-muted-foreground">
                  {row.evaluator_note ?? ""}
                </TD>
              </TR>
            );
          })}
        </TBody>
      </Table>
    </div>
  );
}

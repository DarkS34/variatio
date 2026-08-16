import { Download, ShieldCheck, UserCheck, UserX } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Alert, EmptyState, Skeleton } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { ARM_META } from "@/features/evaluation/arms";
import { duration, when } from "@/lib/format";
import type { AdminGroup, EvaluationAggregates, EvaluationArm } from "@/lib/types";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useSession } from "@/state/auth";
import {
  useAdminEvaluations,
  useAdminOverview,
  useSetAccountEnabled,
} from "@/state/queries";

import { BarRows, DayColumns, ShareMeter, StatTile, type BarRow } from "./charts";

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

export function AdminScreen() {
  const session = useSession();
  const [tab, setTab] = useState("estudio");
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [account, setAccount] = useState<number | null>(null);

  const overview = useAdminOverview();
  const study = useAdminEvaluations({ workspace, account });

  if (!session.data?.user.is_admin) {
    return (
      <EmptyState icon={<ShieldCheck className="size-6" />} title="Solo para administración">
        Esta pantalla es del administrador de la instalación. Tu cuenta no lo es.
      </EmptyState>
    );
  }

  if (overview.isLoading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Administración</h1>
        <InfoHint label="Qué es esto">
          La instalación entera vista desde fuera: quién la usa, cuántos workspaces hay y
          cómo va el estudio de evaluación. Es la única pantalla que cruza cuentas.
        </InfoHint>
      </header>

      {overview.data ? <Totals overview={overview.data} /> : null}

      <Tabs
        items={[
          { value: "estudio", label: "Evaluaciones" },
          { value: "cuentas", label: "Cuentas" },
          { value: "workspaces", label: "Workspaces" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "estudio" ? (
        <StudyTab
          data={study.data}
          loading={study.isLoading}
          workspace={workspace}
          account={account}
          onWorkspace={setWorkspace}
          onAccount={setAccount}
        />
      ) : null}

      {tab === "cuentas" && overview.data ? (
        <AccountsTab
          overview={overview.data}
          onInspect={(id) => {
            setAccount(id);
            setTab("estudio");
          }}
        />
      ) : null}

      {tab === "workspaces" && overview.data ? (
        <WorkspacesTab overview={overview.data} />
      ) : null}
    </div>
  );
}

/* Headline ---------------------------------------------------------------------------- */

function Totals({ overview }: { overview: NonNullable<ReturnType<typeof useAdminOverview>["data"]> }) {
  const { totals, engine } = overview;
  return (
    <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5">
      <StatTile label="Cuentas" value={totals.users} />
      <StatTile label="Workspaces" value={totals.workspaces} />
      <StatTile label="Variantes generadas" value={totals.generations.toLocaleString("es-ES")} />
      <StatTile
        label="Comparaciones"
        value={totals.evaluations}
        hint={`${totals.decided} con elección registrada`}
      />
      <StatTile
        label="Motor"
        value={engine.busy ? "ocupado" : "libre"}
        tone={engine.busy ? "accent" : "plain"}
        hint={
          engine.busy
            ? `${engine.job?.label ?? "trabajo"} · ${engine.queued} en cola`
            : `${engine.warm_contexts.length} contexto(s) caliente(s)`
        }
      />
    </div>
  );
}

/* The study ---------------------------------------------------------------------------- */

function StudyTab({
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
  const csv = api.adminEvaluationCsvUrl({ workspace, account });

  return (
    <div className="space-y-5">
      {/* Filters in one row above the charts, so what is being looked at is stated
          before the numbers rather than inferred from them. */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={workspace ?? ""}
          onChange={(event) => onWorkspace(event.target.value || null)}
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
        >
          <option value="">Todos los workspaces</option>
          {data.filters.workspaces.map((slug) => (
            <option key={slug} value={slug}>
              {slug}
            </option>
          ))}
        </select>

        {account !== null ? (
          <Button variant="outline" size="sm" onClick={() => onAccount(null)}>
            Quitar el filtro de cuenta
          </Button>
        ) : null}

        {filtered ? (
          <span className="text-xs text-muted-foreground">
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
    <section className="space-y-3 rounded-xl border border-border bg-card p-3 shadow-sm">
      <h2 className="text-xs font-medium">{title}</h2>
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
      <p className="text-[11px] text-muted-foreground">
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
      <h3 className="text-[11px] font-medium text-muted-foreground">
        Propuestas sin ítem válido
      </h3>
      <div className="grid grid-cols-3 gap-2">
        {ARMS.map((arm) => {
          const counts = aggregates.arm_status[arm] ?? {};
          const bad = (counts.failed ?? 0) + (counts.unavailable ?? 0);
          return (
            <div key={arm} className="rounded-lg border border-border px-2.5 py-1.5">
              <p className="flex items-center gap-1.5 truncate text-[11px] text-muted-foreground">
                <span
                  className="size-2 shrink-0 rounded-[2px]"
                  style={{ backgroundColor: ARM_META[arm].colour }}
                />
                {ARM_META[arm].short}
              </p>
              <p
                className={cn(
                  "text-sm tabular-nums",
                  bad > 0 ? "text-[var(--warning)]" : "text-foreground",
                )}
              >
                {bad}
                <span className="ml-1 text-xs text-muted-foreground">de {total}</span>
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
    return <p className="text-xs text-muted-foreground">Ninguna sesión valorada todavía.</p>;
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-muted-foreground">
        {rubric.n} valorada{rubric.n === 1 ? "" : "s"} · escala de 1 a 5
      </p>
      <div className="space-y-1.5">
        {Object.keys(RUBRIC_LABELS).map((key) => {
          const entry = rubric[key];
          if (!entry) return null;
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="w-40 shrink-0 truncate text-xs text-muted-foreground">
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
              <span className="w-10 shrink-0 text-right text-xs tabular-nums">
                {entry.mean.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>
      {rubric.complexity?.mean_distance_to_3 !== undefined ? (
        <p className="text-[11px] text-muted-foreground">
          En exigencia el objetivo es el 3, no el 5 — de ahí la marca central. La distancia
          media al 3 es{" "}
          <span className="tabular-nums">{rubric.complexity.mean_distance_to_3}</span>.
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
      <p className="text-xs text-muted-foreground">
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
      <p className="text-[11px] text-muted-foreground">
        El modo se sortea al empezar cada sesión, igual para las dos propuestas locales.
      </p>
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
    return <p className="text-xs text-muted-foreground">Nada que agrupar todavía.</p>;
  }

  return (
    <div className="thin-scroll overflow-x-auto">
      <table className="w-full min-w-[42rem] text-xs">
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th className="py-1.5 pr-3 text-left font-medium">{firstHeader}</th>
            <th className="px-3 py-1.5 text-right font-medium">Sesiones</th>
            <th className="px-3 py-1.5 text-right font-medium">Decididas</th>
            <th className="px-3 py-1.5 text-left font-medium">Ganó el sistema</th>
            <th className="px-3 py-1.5 text-right font-medium">Valoradas</th>
            <th className="py-1.5 pl-3 text-right font-medium">Última</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <tr
              key={String(group.key)}
              className="cursor-pointer border-b border-border/50 last:border-0 hover:bg-accent/50"
              onClick={() => onSelect(group)}
            >
              <td className="max-w-56 truncate py-1.5 pr-3">
                {group.label}
                {group.name && group.name !== group.label ? (
                  <span className="ml-1 text-muted-foreground">· {group.name}</span>
                ) : null}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">{group.sessions}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{group.decided}</td>
              <td className="px-3 py-1.5">
                <ShareMeter
                  value={group.preferences?.system ?? 0}
                  total={group.decided}
                  reference={CHANCE}
                  title={`${group.preferences?.system ?? 0} de ${group.decided}; la marca es el 33 % del azar`}
                />
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">{group.rated}</td>
              <td className="whitespace-nowrap py-1.5 pl-3 text-right text-muted-foreground">
                {group.last_at
                  ? when(new Date(group.last_at * 1000).toISOString())
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SessionsTable({ rows }: { rows: NonNullable<ReturnType<typeof useAdminEvaluations>["data"]>["sessions"] }) {
  return (
    <div className="thin-scroll max-h-[28rem] overflow-auto">
      <table className="w-full min-w-[48rem] text-xs">
        <thead className="sticky top-0 bg-card">
          <tr className="border-b border-border text-muted-foreground">
            <th className="py-1.5 pr-3 text-left font-medium">Cuándo</th>
            <th className="px-3 py-1.5 text-left font-medium">Evaluador</th>
            <th className="px-3 py-1.5 text-left font-medium">Workspace</th>
            <th className="px-3 py-1.5 text-left font-medium">Conceptos</th>
            <th className="px-3 py-1.5 text-left font-medium">Eligió</th>
            <th className="px-3 py-1.5 text-center font-medium">Razonó</th>
            <th className="py-1.5 pl-3 text-left font-medium">Nota</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const meta = row.choice_arm ? ARM_META[row.choice_arm] : null;
            return (
              <tr key={row.id} className="border-b border-border/50 last:border-0">
                <td className="whitespace-nowrap py-1.5 pr-3 text-muted-foreground">
                  {when(new Date(row.created_at * 1000).toISOString())}
                </td>
                <td className="max-w-44 truncate px-3 py-1.5">{row.account ?? "—"}</td>
                <td className="px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
                  {row.workspace ?? "—"}
                </td>
                <td className="max-w-52 truncate px-3 py-1.5">{row.concepts.join(" · ")}</td>
                <td className="whitespace-nowrap px-3 py-1.5">
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
                </td>
                <td className="px-3 py-1.5 text-center text-muted-foreground">
                  {row.think ? "sí" : "no"}
                </td>
                <td className="max-w-64 truncate py-1.5 pl-3 text-muted-foreground">
                  {row.evaluator_note ?? ""}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* Accounts and workspaces --------------------------------------------------------------- */

function AccountsTab({
  overview,
  onInspect,
}: {
  overview: NonNullable<ReturnType<typeof useAdminOverview>["data"]>;
  onInspect: (id: number) => void;
}) {
  const toggle = useSetAccountEnabled();
  const session = useSession();

  return (
    <div className="thin-scroll overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[52rem] text-sm">
        <thead>
          <tr className="border-b border-border text-xs text-muted-foreground">
            <th className="px-3 py-2 text-left font-medium">Cuenta</th>
            <th className="px-3 py-2 text-left font-medium">Workspaces</th>
            <th className="px-3 py-2 text-right font-medium">Variantes</th>
            <th className="px-3 py-2 text-right font-medium">Comparaciones</th>
            <th className="px-3 py-2 text-left font-medium">Alta</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {overview.accounts.map((account) => (
            <tr key={account.id} className="border-b border-border/50 last:border-0">
              <td className="px-3 py-2">
                <span className="flex flex-wrap items-center gap-1.5">
                  <span
                    className={cn(
                      "truncate font-mono",
                      account.disabled && "line-through opacity-60",
                    )}
                  >
                    {account.username}
                  </span>
                  {account.is_admin ? <Badge variant="secondary">admin</Badge> : null}
                  {account.disabled ? <Badge variant="outline">desactivada</Badge> : null}
                </span>
                <span className="block text-xs text-muted-foreground">{account.name}</span>
              </td>
              <td className="px-3 py-2 text-xs">
                {account.workspaces.length === 0 ? (
                  <span className="text-muted-foreground">—</span>
                ) : (
                  account.workspaces.map((w) => `${w.slug}:${w.role}`).join(", ")
                )}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{account.generations}</td>
              <td className="px-3 py-2 text-right tabular-nums">
                {account.evaluations}
                <span className="ml-1 text-xs text-muted-foreground">
                  ({account.decided} dec.)
                </span>
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                {account.created_at ? when(account.created_at) : "—"}
              </td>
              <td className="whitespace-nowrap px-3 py-2 text-right">
                {account.evaluations > 0 ? (
                  <Button variant="ghost" size="sm" onClick={() => onInspect(account.id)}>
                    Ver sus sesiones
                  </Button>
                ) : null}
                {account.id !== session.data?.user.id ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={toggle.isPending}
                    onClick={() =>
                      toggle.mutate({ id: account.id, enabled: account.disabled })
                    }
                  >
                    {account.disabled ? <UserCheck /> : <UserX />}
                    {account.disabled ? "Reactivar" : "Desactivar"}
                  </Button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WorkspacesTab({
  overview,
}: {
  overview: NonNullable<ReturnType<typeof useAdminOverview>["data"]>;
}) {
  return (
    <div className="space-y-3">
      <Alert tone="info" title="Los workspaces son de sus miembros">
        <p>
          Esta tabla los cuenta; para entrar en uno, cámbiate a él con el selector de
          arriba. Como administrador puedes hacerlo aunque no seas miembro.
        </p>
      </Alert>

      <div className="thin-scroll overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[40rem] text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted-foreground">
              <th className="px-3 py-2 text-left font-medium">Workspace</th>
              <th className="px-3 py-2 text-right font-medium">Miembros</th>
              <th className="px-3 py-2 text-right font-medium">Variantes</th>
              <th className="px-3 py-2 text-left font-medium">Índices</th>
              <th className="px-3 py-2 text-left font-medium">Creado</th>
            </tr>
          </thead>
          <tbody>
            {overview.workspaces.map((workspace) => (
              <tr key={workspace.id} className="border-b border-border/50 last:border-0">
                <td className="px-3 py-2">
                  {workspace.name}
                  <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                    {workspace.slug}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{workspace.members}</td>
                <td className="px-3 py-2 text-right tabular-nums">{workspace.generations}</td>
                <td className="px-3 py-2 text-xs text-muted-foreground">
                  {workspace.warm ? "en memoria" : "fríos"}
                </td>
                <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                  {workspace.created_at ? when(workspace.created_at) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

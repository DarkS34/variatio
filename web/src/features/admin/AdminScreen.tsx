import {
  Check,
  ChevronRight,
  Copy,
  Download,
  Link as LinkIcon,
  ShieldCheck,
  Trash2,
  UserCheck,
  UserX,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select } from "@/components/ui/input";
import { EmptyState, Skeleton, Spinner } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { ARM_META } from "@/features/evaluation/arms";
import { FormError } from "@/features/auth/AuthLayout";
import { ARTIFACT_STATUS, duration, when } from "@/lib/format";
import type {
  AdminAccount,
  AdminGroup,
  AdminOverview,
  AdminWorkspace,
  EvaluationAggregates,
  EvaluationArm,
  Role,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { ROLE_HINTS, ROLE_LABELS, useSession } from "@/state/auth";
import {
  useAdminDeleteWorkspace,
  useAdminEvaluations,
  useAdminInvites,
  useAdminOverview,
  useCreateInvite,
  useDeleteAccount,
  useDeleteArtifact,
  useMembershipActions,
  useRevokeInvite,
  useSetAccountEnabled,
} from "@/state/queries";

import { BarRows, DayColumns, ShareMeter, StatTile, type BarRow } from "./charts";
import { ConfigTab } from "./ConfigTab";

/** A three-way blind choice: what pure chance would produce. Every share is read
 *  against it, and the panel never shows one without drawing the other. */
const CHANCE = 1 / 3;

/** The order the arm palette was validated on. Anything that draws the three side by
 *  side draws them in it — the CVD check is over ADJACENT pairs. */
const ARMS: EvaluationArm[] = ["naive", "rag", "system"];

const ROLES: Role[] = ["viewer", "editor", "owner"];

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
        <h1 className="font-display font-expanded text-display">Administración</h1>
        <InfoHint label="Qué es esto">
          La instalación entera vista desde fuera: quién la usa, quién puede entrar y en
          qué, cuántos workspaces hay y cómo va el estudio de evaluación. Es la única
          pantalla que cruza cuentas, y el único sitio desde el que se dan accesos.
        </InfoHint>
      </header>

      {overview.data ? <Totals overview={overview.data} /> : null}

      <Tabs
        items={[
          { value: "estudio", label: "Evaluaciones" },
          { value: "cuentas", label: "Cuentas y accesos" },
          { value: "workspaces", label: "Workspaces" },
          { value: "config", label: "Configuración" },
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

      {tab === "config" ? <ConfigTab /> : null}
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
        <Select
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

/* Accounts and workspaces --------------------------------------------------------------- */

/**
 * The one screen that decides who exists and who gets in.
 *
 * It used to be two: an owner's «Personas e invitaciones» dialog, which handed out access
 * to one workspace, and this table, which listed the same accounts and could only switch
 * them off. Two places to answer one question is how the two answers drift apart, so the
 * dialog is gone and this is the whole of it — issuing invitations, moving people between
 * workspaces and disabling an account, in that order, which is the order they happen in.
 *
 * Access is per workspace and this panel crosses them all, so a row's memberships open
 * where the row is rather than obliging the administrator to change workspace to grant one.
 */
function AccountsTab({
  overview,
  onInspect,
}: {
  overview: AdminOverview;
  onInspect: (id: number) => void;
}) {
  const toggle = useSetAccountEnabled();
  const remove = useDeleteAccount();
  const session = useSession();
  const toast = useToast();
  const [open, setOpen] = useState<number | null>(null);

  // Irreversible, so it is spelled out before it happens — and what it spells out is the
  // half people get wrong: the account goes, the material it produced does not.
  const confirmDelete = (account: AdminAccount) => {
    const kept = [
      account.generations ? `${account.generations} variante(s) guardada(s)` : "",
      account.evaluations ? `${account.evaluations} comparación(es)` : "",
    ].filter(Boolean);
    const message =
      `¿Eliminar la cuenta «${account.username}» por completo?\n\n` +
      "Pierde sus accesos y sus sesiones abiertas, y el usuario queda libre para otra " +
      "cuenta.\n" +
      (kept.length
        ? `Lo que generó se queda pero sin autor: ${kept.join(" y ")}.\n`
        : "") +
      "\nNo se puede deshacer. Para cerrarle la puerta sin borrar nada, desactívala.";
    if (!window.confirm(message)) return;
    // The dialog is the confirmation BEFORE; this is the one after. Everything on this
    // screen that destroys something says so once it is done, because the row simply
    // disappearing is indistinguishable from a list that reloaded.
    remove.mutate(account.id, {
      onSuccess: () =>
        toast({ title: "Cuenta eliminada", description: account.username, tone: "attention" }),
      onError: (error: Error) =>
        toast({ title: "No se ha podido eliminar", description: error.message, tone: "danger" }),
    });
  };

  return (
    <div className="space-y-5">
      <InviteSection overview={overview} />

      <section className="space-y-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          Cuentas ({overview.accounts.length})
        </h2>
        <div className="overflow-hidden rounded-lg border border-border">
          <Table minWidth="52rem">
            <THead>
              <TR>
                <TH>Cuenta</TH>
                <TH>Accesos</TH>
                <TH align="num">Variantes</TH>
                <TH align="num">Comparaciones</TH>
                <TH>Alta</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {overview.accounts.map((account) => (
                <AccountRows
                  key={account.id}
                  account={account}
                  overview={overview}
                  self={account.id === session.data?.user.id}
                  expanded={open === account.id}
                  onToggle={() => setOpen(open === account.id ? null : account.id)}
                  onInspect={() => onInspect(account.id)}
                  onEnabled={(enabled) => toggle.mutate({ id: account.id, enabled })}
                  onDelete={() => confirmDelete(account)}
                  busy={toggle.isPending || remove.isPending}
                />
              ))}
            </TBody>
          </Table>
        </div>
        <FormError error={remove.error} />
      </section>
    </div>
  );
}

function AccountRows({
  account,
  overview,
  self,
  expanded,
  onToggle,
  onInspect,
  onEnabled,
  onDelete,
  busy,
}: {
  account: AdminAccount;
  overview: AdminOverview;
  self: boolean;
  expanded: boolean;
  onToggle: () => void;
  onInspect: () => void;
  onEnabled: (enabled: boolean) => void;
  onDelete: () => void;
  busy: boolean;
}) {
  return (
    <>
      <TR>
        <TD className="px-3 py-2">
          <span className="flex flex-wrap items-center gap-1.5">
            <span
              className={cn("truncate font-mono", account.disabled && "line-through opacity-60")}
            >
              {account.username}
            </span>
            {account.is_admin ? <Badge variant="secondary">admin</Badge> : null}
            {self ? <Badge variant="outline">tú</Badge> : null}
            {account.disabled ? <Badge variant="outline">desactivada</Badge> : null}
          </span>
          <span className="block text-small text-muted-foreground">{account.name}</span>
        </TD>
        <TD className="px-3 py-2">
          <button
            type="button"
            onClick={onToggle}
            className="flex items-center gap-1.5 text-left text-small hover:text-foreground"
          >
            <ChevronRight
              className={cn("size-3.5 shrink-0 transition-transform", expanded && "rotate-90")}
            />
            {/* Para una cuenta de administración la lista de membresías no describe a qué
                entra: entra a todo. Decir «sin acceso a ninguno» ahí sería falso. */}
            {account.is_admin ? (
              <span className="text-muted-foreground">acceso total (administración)</span>
            ) : account.workspaces.length === 0 ? (
              <span className="text-muted-foreground">sin acceso a ninguno</span>
            ) : (
              <span className="flex flex-wrap gap-1">
                {account.workspaces.map((w) => (
                  <Badge key={w.slug} variant="outline">
                    {w.slug} · {ROLE_LABELS[w.role].toLowerCase()}
                  </Badge>
                ))}
              </span>
            )}
          </button>
        </TD>
        <TD align="num" className="px-3 py-2  nums">{account.generations}</TD>
        <TD align="num" className="px-3 py-2  nums">
          {account.evaluations}
          <span className="ml-1 text-small text-muted-foreground">({account.decided} dec.)</span>
        </TD>
        <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
          {account.created_at ? when(account.created_at) : "—"}
        </TD>
        <TD align="num" className="whitespace-nowrap px-3 py-2">
          {account.evaluations > 0 ? (
            <Button variant="ghost" size="sm" onClick={onInspect}>
              Ver sus sesiones
            </Button>
          ) : null}
          {/* Desactivar o borrar la propia cuenta deja la instalación sin quien la
              administre, y el servidor rechaza las dos igualmente; no ofrecerlas evita el
              409 por sorpresa. Van juntas y en este orden porque son la misma decisión con
              dos intensidades: cerrar la puerta, o quitar la cuenta. */}
          {self ? null : (
            <>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => onEnabled(account.disabled)}
              >
                {account.disabled ? <UserCheck /> : <UserX />}
                {account.disabled ? "Reactivar" : "Desactivar"}
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                title="Eliminar la cuenta por completo"
                disabled={busy}
                onClick={onDelete}
              >
                <Trash2 />
              </Button>
            </>
          )}
        </TD>
      </TR>

      {expanded ? (
        <TR className="bg-muted/30">
          <TD colSpan={6} className="py-3">
            <MembershipEditor account={account} overview={overview} />
          </TD>
        </TR>
      ) : null}
    </>
  );
}

/** The memberships of one account, editable where they are read. */
function MembershipEditor({
  account,
  overview,
}: {
  account: AdminAccount;
  overview: AdminOverview;
}) {
  const { grant, revoke } = useMembershipActions();
  const missing = overview.workspaces.filter(
    (workspace) => !account.workspaces.some((w) => w.slug === workspace.slug),
  );
  const [slug, setSlug] = useState(missing[0]?.slug ?? "");
  const [role, setRole] = useState<Role>("editor");

  // An administrator already reaches every workspace — that is the one `if` in
  // `access_for` — so granting them a membership changes nothing they could not already
  // do, and a role selector here would be a control with no effect. The memberships they
  // do have are still worth reading, because that is where the owner's own powers over a
  // workspace come from, but they are not something this screen hands out.
  if (account.is_admin) {
    return (
      <div className="space-y-2">
        <p className="text-small text-muted-foreground">
          Esta cuenta administra la instalación: entra en todos los workspaces sin ser
          miembro de ninguno, así que no hay accesos que darle.
        </p>
        {account.workspaces.length > 0 ? (
          <p className="flex flex-wrap items-center gap-1.5 text-small text-muted-foreground">
            Consta además como miembro de
            {account.workspaces.map((membership) => (
              <Badge key={membership.slug} variant="outline">
                {membership.slug} · {ROLE_LABELS[membership.role].toLowerCase()}
              </Badge>
            ))}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {account.workspaces.length === 0 ? (
        <p className="text-small text-muted-foreground">
          Esta cuenta no es miembro de ningún workspace: puede entrar, pero no verá nada
          hasta que le des acceso a alguno.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-background">
          {account.workspaces.map((membership) => (
            <li key={membership.slug} className="flex flex-wrap items-center gap-2 p-2">
              <span className="min-w-0 flex-1 truncate font-mono text-small">
                {membership.slug}
              </span>
              <Select
                value={membership.role}
                className="w-36"
                disabled={grant.isPending}
                onChange={(event) =>
                  grant.mutate({
                    id: account.id,
                    workspace: membership.slug,
                    role: event.target.value as Role,
                  })
                }
              >
                {ROLES.map((option) => (
                  <option key={option} value={option}>
                    {ROLE_LABELS[option]}
                  </option>
                ))}
              </Select>
              <Button
                variant="ghost"
                size="icon-sm"
                title="Quitar el acceso a este workspace"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate({ id: account.id, workspace: membership.slug })}
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}

      {missing.length > 0 ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor={`add-${account.id}`}>Dar acceso a</Label>
            <Select
              id={`add-${account.id}`}
              value={slug}
              className="w-56"
              onChange={(event) => setSlug(event.target.value)}
            >
              {missing.map((workspace) => (
                <option key={workspace.slug} value={workspace.slug}>
                  {workspace.name} ({workspace.slug})
                </option>
              ))}
            </Select>
          </div>
          <Select
            value={role}
            className="w-36"
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            disabled={!slug || grant.isPending}
            onClick={() => grant.mutate({ id: account.id, workspace: slug, role })}
          >
            {grant.isPending ? <Spinner /> : null}
            Conceder
          </Button>
          <span className="text-small text-muted-foreground">{ROLE_HINTS[role]}</span>
        </div>
      ) : null}

      <FormError error={grant.error ?? revoke.error} />
    </div>
  );
}

/**
 * Invitations, which are the only way an account comes into existence.
 *
 * The link IS the invitation: nothing is sent anywhere, it works once, it expires, and
 * whoever opens it chooses their own username. That is why the copy says not to leave it
 * in a shared place — until it is redeemed it is a credential.
 */
function InviteSection({ overview }: { overview: AdminOverview }) {
  const invites = useAdminInvites();
  const create = useCreateInvite();
  const revoke = useRevokeInvite();
  const [workspace, setWorkspace] = useState<string>(overview.workspaces[0]?.slug ?? "");
  const [role, setRole] = useState<Role>("editor");

  const pending = invites.data?.invites ?? [];

  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          Invitar a alguien
        </h2>
        <InfoHint label="Cómo se entra aquí">
          No hay registro abierto: una cuenta existe porque alguien abrió una invitación de
          un solo uso, o porque se creó desde la línea de órdenes. Quitar el registro
          público es lo que quita de en medio el mayor blanco de un login web.
        </InfoHint>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="invite-workspace">Workspace</Label>
          <Select
            id="invite-workspace"
            value={workspace}
            className="w-64"
            onChange={(event) => setWorkspace(event.target.value)}
          >
            <option value="">Ninguno (solo crear la cuenta)</option>
            {overview.workspaces.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.name} ({row.slug})
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="invite-role">Permiso</Label>
          <Select
            id="invite-role"
            value={role}
            className="w-40"
            disabled={!workspace}
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </Select>
        </div>
        <Button
          onClick={() => create.mutate({ workspace: workspace || null, role })}
          disabled={create.isPending}
        >
          {create.isPending ? <Spinner /> : <LinkIcon />}
          Crear enlace
        </Button>
        <span className="text-small text-muted-foreground">
          {workspace
            ? ROLE_HINTS[role]
            : "Entrará sin acceso a ninguna instancia; se lo das después desde la tabla."}
        </span>
      </div>

      <FormError error={create.error} />
      {create.isSuccess ? <InviteLink link={create.data.link} /> : null}

      {pending.length > 0 ? (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {pending.map((invite) => (
            <li key={invite.id} className="flex flex-wrap items-center gap-2 p-2 text-body">
              <div className="min-w-0 flex-1">
                {/* No hay destinatario que nombrar: lo que distingue dos enlaces pendientes
                    es cuándo se emitieron y para qué instancia. */}
                <p className="truncate">
                  Enlace del {new Date(invite.created_at).toLocaleDateString("es-ES")}
                  {invite.created_by ? (
                    <span className="ml-1 text-small text-muted-foreground">
                      · lo creó {invite.created_by}
                    </span>
                  ) : null}
                </p>
                <p className="text-small text-muted-foreground">
                  {invite.workspace_slug
                    ? `${invite.workspace_slug} · ${ROLE_LABELS[invite.role]}`
                    : "sin workspace"}{" "}
                  · caduca el {new Date(invite.expires_at).toLocaleDateString("es-ES")}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                title="Anular"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(invite.id)}
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function InviteLink({ link }: { link: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
      <p className="text-body">
        Pásaselo tú a quien invitas. Sirve una sola vez y quien lo abra elegirá su propio
        usuario, así que no lo dejes en un sitio compartido.
      </p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1 font-mono text-small">
          {link}
        </code>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            navigator.clipboard.writeText(link);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <Check /> : <Copy />}
          {copied ? "Copiado" : "Copiar"}
        </Button>
      </div>
    </div>
  );
}

/**
 * Las instancias de la instalación, y lo único que este panel escribe sobre ellas: quitarlas.
 *
 * Vaciar una etapa y borrar el workspace son la misma decisión con dos alcances, así que
 * viven en la misma fila: la etapa se vacía desde su distintivo, el workspace desde el
 * botón del final. Ninguna de las dos construye ni aprueba nada — para eso hay que entrar
 * en la instancia, que es donde se ve lo que se está tocando.
 */
function WorkspacesTab({ overview }: { overview: AdminOverview }) {
  const remove = useAdminDeleteWorkspace();
  const toast = useToast();
  const [target, setTarget] = useState<AdminWorkspace | null>(null);
  const only = overview.workspaces.length === 1;

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-lg border border-border">
        <Table minWidth="52rem">
          <THead>
            <TR>
              <TH>Workspace</TH>
              <TH>Cadena</TH>
              <TH align="num">Miembros</TH>
              <TH align="num">Variantes</TH>
              <TH>Creado</TH>
              <TH />
            </TR>
          </THead>
          <TBody>
            {overview.workspaces.map((workspace) => (
              <TR key={workspace.id}>
                <TD className="px-3 py-2">
                  {workspace.name}
                  <span className="ml-2 font-mono text-micro text-muted-foreground">
                    {workspace.slug}
                  </span>
                  {workspace.warm ? (
                    <span className="ml-2 text-micro text-muted-foreground">· en memoria</span>
                  ) : null}
                </TD>
                <TD className="px-3 py-2">
                  <ChainCell workspace={workspace} />
                </TD>
                <TD align="num" className="px-3 py-2  nums">{workspace.members}</TD>
                <TD align="num" className="px-3 py-2  nums">{workspace.generations}</TD>
                <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
                  {workspace.created_at ? when(workspace.created_at) : "—"}
                </TD>
                <TD align="num" className="whitespace-nowrap px-3 py-2">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    disabled={only || remove.isPending}
                    title={
                      only
                        ? "Es el único workspace de la instalación"
                        : "Eliminar el workspace y sus ficheros"
                    }
                    onClick={() => setTarget(workspace)}
                  >
                    <Trash2 />
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      <FormError error={remove.error} />

      {target ? (
        <DeleteWorkspaceDialog
          workspace={target}
          busy={remove.isPending}
          onClose={() => setTarget(null)}
          onConfirm={() =>
            remove.mutate(target.slug, {
              onSuccess: () => {
                setTarget(null);
                toast({
                  title: "Workspace eliminado",
                  description: `${target.slug}, con su árbol de ficheros.`,
                  tone: "attention",
                });
              },
              onError: (error: Error) =>
                toast({
                  title: "No se ha podido eliminar",
                  description: error.message,
                  tone: "danger",
                }),
            })
          }
        />
      ) : null}
    </div>
  );
}

/**
 * La cadena de una instancia, y el sitio desde el que se vacía una etapa.
 *
 * Vaciar deja el artefacto en «missing» y su workspace en pie: se borra el fichero curado,
 * el borrador y las derivaciones de la caché que hablaban de él. Las copias de `.history/`
 * no se tocan, así que un borrado equivocado se deshace desde «Restaurar» en la pantalla
 * del artefacto — y eso es justo lo que hace que ofrecerlo aquí no sea temerario.
 */
function ChainCell({ workspace }: { workspace: AdminWorkspace }) {
  const discard = useDeleteArtifact();
  const toast = useToast();

  const confirm = (artifact: AdminWorkspace["stages"][number]) => {
    const message =
      `¿Vaciar «${artifact.label}» de ${workspace.slug}?\n\n` +
      "Se borran el fichero del artefacto y las derivaciones de la caché que dependían " +
      "de él; la etapa vuelve a «sin construir» y habrá que reconstruirla.\n\n" +
      "Las copias del historial no se tocan: si te equivocas, se restaura desde la " +
      "pantalla del artefacto.";
    if (!window.confirm(message)) return;
    discard.mutate(
      { slug: workspace.slug, artifact: artifact.artifact },
      {
        onSuccess: () =>
          toast({
            title: "Etapa vaciada",
            description: `«${artifact.label}» de ${workspace.slug}. El historial sigue ahí.`,
            tone: "attention",
          }),
        onError: (error: Error) =>
          toast({ title: "No se ha podido vaciar", description: error.message, tone: "danger" }),
      },
    );
  };

  return (
    <span className="flex flex-wrap items-center gap-1">
      {workspace.stages.map((stage) => {
        const meta = ARTIFACT_STATUS[stage.status];
        const empty = stage.status === "missing";
        return (
          <button
            key={stage.artifact}
            type="button"
            disabled={empty || discard.isPending}
            title={
              empty
                ? `${stage.label}: sin construir`
                : `Vaciar «${stage.label}» de ${workspace.slug}`
            }
            onClick={() => confirm(stage)}
            className={cn(
              "rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              empty ? "cursor-default" : "hover:opacity-75",
            )}
          >
            <Badge variant={meta.tone as never}>
              {stage.label.split(" ")[0]} · {meta.label.toLowerCase()}
            </Badge>
          </button>
        );
      })}
    </span>
  );
}

/**
 * Borrar un workspace es irreversible y se lleva los ficheros, así que se escribe el slug.
 *
 * No es ceremonia: la fila de al lado se parece a esta, el botón es un icono, y lo que
 * desaparece incluye los documentos que alguien subió — que son lo único aquí que no se
 * puede reconstruir con una GPU y un rato.
 */
function DeleteWorkspaceDialog({
  workspace,
  busy,
  onClose,
  onConfirm,
}: {
  workspace: AdminWorkspace;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [typed, setTyped] = useState("");
  const built = workspace.stages.filter((stage) => stage.status !== "missing");

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Eliminar «${workspace.name}»`}
      description="No se puede deshacer."
      className="max-w-lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            disabled={typed !== workspace.slug || busy}
            onClick={onConfirm}
          >
            {busy ? <Spinner /> : <Trash2 />}
            Eliminar
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-body">
        <p>Desaparecen de la instalación y del disco:</p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          <li>
            {built.length > 0
              ? `sus artefactos construidos (${built.map((s) => s.label.toLowerCase()).join(", ")})`
              : "sus artefactos, que están todos sin construir"}
          </li>
          <li>los documentos en bruto que se subieron a esta instancia</li>
          <li>sus cachés, sus accesos y sus aprobaciones</li>
          <li>
            {workspace.generations > 0
              ? `sus ${workspace.generations} variante(s) guardada(s) y sus comparaciones`
              : "sus comparaciones de evaluación, si las hubiera"}
          </li>
        </ul>
        <div className="space-y-1">
          <Label htmlFor="confirm-slug">
            Escribe <span className="font-mono normal-case">{workspace.slug}</span> para
            confirmar
          </Label>
          <Input
            id="confirm-slug"
            value={typed}
            autoFocus
            autoComplete="off"
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
      </div>
    </Dialog>
  );
}

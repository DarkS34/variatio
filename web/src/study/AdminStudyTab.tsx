import { Download, Trash2 } from "lucide-react";
import { useMemo } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Checkbox, Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { BarRows, DayColumns, ShareMeter, type BarRow } from "@/features/admin/charts";
import { duration, when } from "@/lib/format";
import { cn } from "@/lib/utils";

import { AdminSetsPanel } from "./AdminSetsPanel";
import { ARM_META } from "./arms";
import { useAdminEvaluations, useDeleteEvaluations } from "./queries";
import { studyApi } from "./api";
import type { AdminEvaluations, AdminGroup, EvaluationAggregates, EvaluationArm } from "./types";
import { useSelection } from "./useSelection";
import { useT, type Key } from "@/lib/i18n";

/** A three-way blind choice: what pure chance would produce. Every share is read
 *  against it, and the panel never shows one without drawing the other. */
const CHANCE = 1 / 3;

/** The order the arm palette was validated on. Anything that draws the three side by
 *  side draws them in it — the CVD check is over ADJACENT pairs. */
const ARMS: EvaluationArm[] = ["naive", "rag", "system"];

const RUBRIC_LABELS: Record<string, Key> = {
  originality: "rubricScale.originality",
  complexity: "rubricScale.complexity",
  concept_fit: "rubricScale.concept_fit",
  soundness: "rubricScale.soundness",
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
  const { t, plural } = useT();
  if (loading && !data) return <Skeleton className="h-96" />;
  if (!data) return null;

  const filtered = Boolean(workspace || account !== null);
  const csv = studyApi.adminEvaluationCsvUrl({ workspace, account });

  return (
    <div className="space-y-8">
      {/* Handing comparisons out comes FIRST, before any number: it is the only thing on
          this screen that is work rather than a reading, and it is what makes the numbers
          below exist at all. It carries its own person-and-workspace choice, and the
          filter that now sits BELOW it does not reach it — the two used to run together
          in one column, with the reading filter on top, where it read as if it governed
          the reparto as well. */}
      <Section
        eyebrow={t("adminStudy.handOut.eyebrow")}
        title={t("adminStudy.handOut.title")}
        description={t("adminStudy.handOut.description")}
      >
        <Card>
          <AdminSetsPanel />
        </Card>
      </Section>

      <Section
        eyebrow={t("adminStudy.results.eyebrow")}
        title={t("adminStudy.results.title")}
        description={t("adminStudy.results.description")}
      >
        {/* The filter stays above the numbers inside its own section, so what is being
            looked at is stated before the numbers rather than inferred from them. */}
        <div className="flex flex-wrap items-center gap-2">
          <Select
            aria-label={t("adminStudy.filterByWorkspace")}
            value={workspace ?? ""}
            onChange={(event) => onWorkspace(event.target.value || null)}
            className="w-56"
          >
            <option value="">{t("adminStudy.allWorkspaces")}</option>
            {data.filters.workspaces.map((slug) => (
              <option key={slug} value={slug}>
                {slug}
              </option>
            ))}
          </Select>

          {account !== null ? (
            <Button variant="outline" size="sm" onClick={() => onAccount(null)}>
              {t("adminStudy.clearAccountFilter")}
            </Button>
          ) : null}

          {filtered ? (
            <span className="text-small text-muted-foreground">
              {plural("adminStudy.sessionsInFilter", data.aggregates.sessions)}
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

        {/* Not an `EmptyState`: its title sits at the same type step as the section
            heading right above it, and two titles of one level nested inside each other
            is the hierarchy this split exists to fix. Here it is a state of the section,
            so it is written at the level of what it replaces — the cards. */}
        {data.aggregates.sessions === 0 ? (
          <Card>
            <p className="text-small text-muted-foreground">
              {filtered ? t("adminStudy.filteredEmpty") : t("adminStudy.empty")}
            </p>
          </Card>
        ) : (
          <>
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
              <Card title={t("adminStudy.card.wins")}>
                <Preferences aggregates={data.aggregates} />
              </Card>
              <Card title={t("adminStudy.card.pace")}>
                <DayColumns points={data.per_day} />
              </Card>
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <Card title={t("adminStudy.card.triage")}>
                <Triage aggregates={data.aggregates} />
              </Card>
              <Card title={t("adminStudy.card.measurement")}>
                <Measurement data={data} />
              </Card>
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <Card title={t("adminStudy.card.rubric")}>
                <Rubric aggregates={data.aggregates} />
              </Card>
              <Card title={t("adminStudy.card.think")}>
                <ThinkEffect aggregates={data.aggregates} />
              </Card>
            </div>

            <Card title={t("adminStudy.card.byProfile")}>
              <GroupTable groups={data.by_profile} firstHeader={t("adminStudy.col.profile")} />
            </Card>

            <Card title={t("adminStudy.card.byAccount")}>
              <GroupTable
                groups={data.by_account}
                firstHeader={t("adminStudy.col.evaluator")}
                onSelect={(group) => onAccount(Number(group.key) || null)}
              />
            </Card>

            <Card title={t("adminStudy.card.byWorkspace")}>
              <GroupTable
                groups={data.by_workspace}
                firstHeader={t("adminStudy.col.workspace")}
                onSelect={(group) => onWorkspace(String(group.key) || null)}
              />
            </Card>

            <Card title={t("adminStudy.card.sessions", { n: data.sessions.length })}>
              <SessionsTable rows={data.sessions} />
            </Card>
          </>
        )}
      </Section>
    </div>
  );
}

/**
 * The two halves of this screen, told apart by structure rather than by colour: an
 * eyebrow at the condensed micro step, a title two steps above the cards' own, and a rule
 * under both. What separates them is the verb — the first WRITES (it generates and hands
 * out), the second only READS — and that is what the description line says, because the
 * mistake it exists to stop is reading the reparto as something the filter governs.
 */
function Section({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <header className="space-y-1 border-b border-border pb-2">
        <p className="text-micro font-condensed uppercase text-muted-foreground">{eyebrow}</p>
        <h2 className="font-display font-expanded text-title">{title}</h2>
        <p className="text-small text-muted-foreground">{description}</p>
      </header>
      {children}
    </section>
  );
}

function Card({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-3 shadow-sm">
      {title ? <h3 className="text-small font-medium">{title}</h3> : null}
      {children}
    </section>
  );
}

const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${Math.round(value * 100)} %`;

/** A p-value is written as a threshold, not as a verdict: the panel reports, it does not
 *  conclude. `< 0.001` rather than a wall of zeros, and never a "significativo" label. */
function pValue(p: number | null | undefined): string {
  if (p == null) return "—";
  if (p < 0.001) return "p < 0,001";
  return `p = ${p.toFixed(3).replace(".", ",")}`;
}

/**
 * The blind per-card answer, and the only quality signal the study has for ALL THREE
 * architectures — the rubric below describes the system's variant alone.
 *
 * «Usaría» folds «tal cual» and «con retoques» together, because that is the question a
 * teacher is really answering: would this save me work. The stricter reading sits beside
 * it rather than instead of it.
 */
function Triage({ aggregates }: { aggregates: EvaluationAggregates }) {
  const { t } = useT();
  const rows = ARMS.filter((arm) => aggregates.triage?.[arm]);
  if (rows.length === 0) {
    return (
      <p className="text-small text-muted-foreground">
        {t("adminStudy.noTriage")}
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <BarRows
        rows={rows.map((arm) => {
          const slice = aggregates.triage[arm]!;
          return {
            key: arm,
            label: t(ARM_META[arm].labelKey),
            value: slice.counts.yes + slice.counts.partly,
            colour: ARM_META[arm].colour,
            detail: t("adminStudy.triageDetail", {
              arm: t(ARM_META[arm].shortKey),
              yes: slice.counts.yes,
              partly: slice.counts.partly,
              no: slice.counts.no,
            }),
          };
        })}
        total={Math.max(...rows.map((arm) => aggregates.triage[arm]!.n))}
      />
      {/* Three rows of four short figures: a list, not a table. `ui/table.tsx` is for
          things that are actually tabular and scroll. */}
      <dl className="space-y-1 text-small">
        {rows.map((arm) => {
          const slice = aggregates.triage[arm]!;
          return (
            <div key={arm} className="flex flex-wrap items-baseline gap-x-3 border-t border-border pt-1">
              <dt className="min-w-20 text-muted-foreground">{t(ARM_META[arm].shortKey)}</dt>
              <dd className="nums font-medium">
                {t("adminStudy.wouldUse", { pct: percent(slice.usable) })}
              </dd>
              <dd className="nums text-muted-foreground">
                {t("adminStudy.asIs", { pct: percent(slice.outright) })}
              </dd>
              <dd className="ml-auto nums text-muted-foreground">
                {slice.ci95_usable
                  ? `IC95 ${percent(slice.ci95_usable[0])}–${percent(slice.ci95_usable[1])}`
                  : "—"}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

/**
 * Whether the study's own instrument can be trusted, which is the question the literature
 * asks hardest and the one this panel could not answer before.
 *
 * The agreement is POOLED over evaluator pairs sharing a set rather than computed for a
 * fixed pair of raters, because this panel is not one — evaluators teach different
 * subjects and overlap where an administrator decided. That makes it Scott's π rather than
 * Cohen's κ proper, and the memoria has to say so instead of calling the number κ.
 */
function Measurement({ data }: { data: AdminEvaluations }) {
  const { plural, t } = useT();
  const { agreement, aggregates } = data;
  const position = aggregates.position;
  const duration = aggregates.duration;

  return (
    <div className="space-y-3 text-small">
      <div className="space-y-1">
        <p className="font-medium">{t("adminStudy.agreement")}</p>
        {agreement.choice.pairs > 0 ? (
          <p className="text-muted-foreground">
            {t("adminStudy.agreement.head", {
              pairs: plural("adminStudy.pairs", agreement.choice.pairs),
              sets: plural("adminStudy.comparisons", agreement.sets_shared),
            })}
            <span className="nums text-foreground">{percent(agreement.choice.observed)}</span>{" "}
            {t("adminStudy.agreement.times")}
            {agreement.choice.kappa != null ? (
              <>
                {" "}
                (π ={" "}
                <span className="nums text-foreground">
                  {agreement.choice.kappa.toFixed(2).replace(".", ",")}
                </span>
                )
              </>
            ) : null}
            {agreement.triage.pairs > 0 ? (
              <>
                {t("adminStudy.agreement.triage", {
                  percent: percent(agreement.triage.observed),
                  pairs: agreement.triage.pairs,
                })}
              </>
            ) : (
              "."
            )}
          </p>
        ) : (
          <p className="text-muted-foreground">
            {t("adminStudy.agreement.none")}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <p className="font-medium">{t("adminStudy.position")}</p>
        {position.n > 0 ? (
          <p className="text-muted-foreground">
            A: <span className="nums text-foreground">{position.counts["1"] ?? 0}</span> · B:{" "}
            <span className="nums text-foreground">{position.counts["2"] ?? 0}</span> · C:{" "}
            <span className="nums text-foreground">{position.counts["3"] ?? 0}</span> ·{" "}
            <span className="nums">{pValue(position.p)}</span>
            {t("adminStudy.position.vsUniform")}
          </p>
        ) : (
          <p className="text-muted-foreground">{t("adminStudy.position.none")}</p>
        )}
      </div>

      <div className="space-y-1">
        <p className="font-medium">{t("adminStudy.duration")}</p>
        {duration.n > 0 ? (
          <p className="text-muted-foreground">
            {t("adminStudy.duration.median")}
            <span className="nums text-foreground">{duration.median} s</span>
            {t("adminStudy.duration.over", {
              n: plural("adminStudy.sessionCount", duration.n),
            })}
            {duration.under_20s ? (
              <>
                {" "}
                · <span className="nums">{duration.under_20s}</span>
                {t("adminStudy.duration.under20")}
              </>
            ) : null}
            .
          </p>
        ) : (
          <p className="text-muted-foreground">{t("adminStudy.duration.none")}</p>
        )}
      </div>

      {aggregates.declined > 0 ? (
        <div className="space-y-1">
          <p className="font-medium">{t("adminStudy.declined")}</p>
          <p className="text-muted-foreground">
            <span className="nums text-foreground">
              {plural("adminStudy.sessionCount", aggregates.declined)}
            </span>
            {t("adminStudy.declined.body")}
          </p>
        </div>
      ) : null}
    </div>
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
  const { plural, t } = useT();
  const decided = aggregates.decided || 0;
  const rows: BarRow[] = [
    ...ARMS.map((arm) => ({
      key: arm,
      label: t(ARM_META[arm].labelKey),
      value: aggregates.preferences[arm] ?? 0,
      colour: ARM_META[arm].colour,
      detail: aggregates.elapsed_ms?.[arm]
        ? t("adminStudy.onAverage", {
            arm: t(ARM_META[arm].shortKey),
            time: duration(aggregates.elapsed_ms[arm]),
          })
        : t(ARM_META[arm].shortKey),
    })),
    {
      key: "none",
      label: t("adminStudy.noneConvinced"),
      value: aggregates.preferences.none ?? 0,
      colour: "var(--muted-foreground)",
    },
  ];

  return (
    <div className="space-y-2">
      <p className="text-micro text-muted-foreground">
        {t("adminStudy.decidedOf", {
          decided: plural("adminStudy.sessionCount", decided),
          total: aggregates.sessions,
        })}
      </p>
      <BarRows
        rows={rows}
        total={decided}
        reference={CHANCE}
        referenceLabel={t("adminStudy.chanceLine")}
      />
      <Reliability aggregates={aggregates} />
    </div>
  );
}

/** A failed arm is a result, not an accident — reliability is part of the comparison. */
function Reliability({ aggregates }: { aggregates: EvaluationAggregates }) {
  const { t } = useT();
  const total = aggregates.decided || 0;
  if (total === 0) return null;

  return (
    <div className="space-y-1.5 border-t border-border pt-2">
      <h3 className="text-micro font-medium text-muted-foreground">
        {t("adminStudy.noValidItem")}
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
                {t(ARM_META[arm].shortKey)}
              </p>
              <p
                className={cn(
                  "text-body nums",
                  bad > 0 ? "text-[var(--attention)]" : "text-foreground",
                )}
              >
                {bad}
                <span className="ml-1 text-small text-muted-foreground">
                  {t("adminStudy.ofTotal", { n: total })}
                </span>
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Rubric({ aggregates }: { aggregates: EvaluationAggregates }) {
  const { plural, t } = useT();
  const rubric = aggregates.rubric ?? { n: 0 };
  if (!rubric.n) {
    return <p className="text-small text-muted-foreground">{t("adminStudy.noRated")}</p>;
  }

  return (
    <div className="space-y-2">
      <p className="text-micro text-muted-foreground">
        {t("adminStudy.ratedScale", { rated: plural("adminStudy.ratedCount", rubric.n) })}
      </p>
      <div className="space-y-1.5">
        {Object.keys(RUBRIC_LABELS).map((key) => {
          const entry = rubric[key];
          if (!entry) return null;
          return (
            <div key={key} className="flex items-center gap-2">
              <span className="w-40 shrink-0 truncate text-small text-muted-foreground">
                {t(RUBRIC_LABELS[key])}
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
          {t("adminStudy.complexityNote")}
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
  const { t } = useT();
  const think = aggregates.think;
  if (!think) return null;
  const total = think.on.decided + think.off.decided;
  if (total === 0) {
    return (
      <p className="text-small text-muted-foreground">
        {t("adminStudy.think.none")}
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
    {
      label: t("adminStudy.think.decided"),
      on: String(think.on.decided),
      off: String(think.off.decided),
    },
    { label: t("adminStudy.think.systemWon"), on: share(think.on), off: share(think.off) },
    {
      label: t("adminStudy.think.systemTime"),
      on: think.on.elapsed_ms?.system ? duration(think.on.elapsed_ms.system) : "—",
      off: think.off.elapsed_ms?.system ? duration(think.off.elapsed_ms.system) : "—",
    },
    ...Object.entries(RUBRIC_LABELS)
      .map(([key, label]) => ({
        label: t(label),
        on: mean(think.on, key),
        off: mean(think.off, key),
      }))
      .filter((row) => row.on !== "—" || row.off !== "—"),
  ];

  return (
    <div className="space-y-2">
      <p className="text-micro text-muted-foreground">
        {t("adminStudy.think.drawn")}
      </p>
      <div>
        <Table minWidth="22rem">
          <THead>
            <TR>
              <TH />
              <TH align="num">{t("adminStudy.think.on")}</TH>
              <TH align="num">{t("adminStudy.think.off")}</TH>
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
          {t("adminStudy.think.oneSided")}
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
/** `onSelect` is optional because not every grouping is a filter: the panel filters by
 *  workspace and by account, and there is nothing to narrow to when the rows are the two
 *  evaluator profiles. A row that is not a filter must not look clickable. */
function GroupTable({
  groups,
  firstHeader,
  onSelect,
}: {
  groups: AdminGroup[];
  firstHeader: string;
  onSelect?: (group: AdminGroup) => void;
}) {
  const { t } = useT();
  if (groups.length === 0) {
    return <p className="text-small text-muted-foreground">{t("adminStudy.nothingToGroup")}</p>;
  }

  return (
    <div>
      <Table minWidth="42rem">
        <THead>
          <TR>
            <TH>{firstHeader}</TH>
            <TH align="num">{t("adminStudy.col.sessions")}</TH>
            <TH align="num">{t("adminStudy.col.decided")}</TH>
            <TH>{t("adminStudy.col.systemWon")}</TH>
            <TH align="num">{t("adminStudy.col.rated")}</TH>
            <TH align="num">{t("adminStudy.col.last")}</TH>
          </TR>
        </THead>
        <TBody>
          {groups.map((group) => (
            <TR key={String(group.key)} onSelect={onSelect ? () => onSelect(group) : undefined}>
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
                  title={t("adminStudy.shareTitle", {
                    system: group.preferences?.system ?? 0,
                    decided: group.decided,
                  })}
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

type SessionRow = NonNullable<ReturnType<typeof useAdminEvaluations>["data"]>["sessions"][number];

function SessionsTable({ rows }: { rows: SessionRow[] }) {
  const { plural, t } = useT();
  const toast = useToast();
  const remove = useDeleteEvaluations();
  const ids = useMemo(() => rows.map((row) => row.id), [rows]);
  const { selected, all: allSelected, some: someSelected, toggle, toggleAll, clear } =
    useSelection(ids);

  const confirmDelete = () => {
    const ids = [...selected];
    const decided = rows.filter((row) => selected.has(row.id) && row.chosen_at !== null).length;
    const message =
      (ids.length === 1
        ? t("adminStudy.confirmHeadOne")
        : t("adminStudy.confirmHeadMany", { n: ids.length })) +
      (decided ? t("sessions.confirmDecided", { n: decided }) : "") +
      t("sessions.confirmTail");
    if (!window.confirm(message)) return;
    remove.mutate(ids, {
      onSuccess: ({ deleted }) => {
        clear();
        toast({
          title: t("adminStudy.sessionsDeleted"),
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
        <span className="text-small text-muted-foreground">
          {selected.size > 0
            ? plural("sessions.selected", selected.size)
            : t("adminStudy.selectToDelete")}
        </span>
        <Button
          variant="destructive"
          size="sm"
          className="ml-auto"
          disabled={selected.size === 0 || remove.isPending}
          onClick={confirmDelete}
        >
          <Trash2 />
          {t("sessions.deleteSelection")}
        </Button>
      </div>
    <div className="thin-scroll max-h-[28rem] overflow-y-auto">
      <Table minWidth="48rem">
        <THead>
          <TR>
            <TH className="w-8">
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected}
                onCheckedChange={toggleAll}
                label={
                  allSelected
                    ? t("adminStudy.deselectAllSessions")
                    : t("adminStudy.selectAllSessions")
                }
              />
            </TH>
            <TH>{t("sessions.col.when")}</TH>
            <TH>{t("adminStudy.col.evaluator")}</TH>
            <TH>{t("adminStudy.col.workspace")}</TH>
            <TH>{t("sessions.col.concepts")}</TH>
            <TH>{t("adminStudy.col.chose")}</TH>
            <TH className="text-center">{t("sessions.col.reasoned")}</TH>
            <TH>{t("adminStudy.col.note")}</TH>
          </TR>
        </THead>
        <TBody>
          {rows.map((row) => {
            const meta = row.choice_arm ? ARM_META[row.choice_arm] : null;
            return (
              <TR key={row.id} selected={selected.has(row.id)}>
                <TD className="py-1.5 pl-3">
                  <Checkbox
                    checked={selected.has(row.id)}
                    onCheckedChange={(next) => toggle(row.id, next)}
                    label={t("adminStudy.selectSession", { id: row.id })}
                  />
                </TD>
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
                    <span className="text-muted-foreground">{t("sessions.undecided")}</span>
                  ) : meta ? (
                    <span className="flex items-center gap-1.5">
                      <span
                        className="size-2 shrink-0 rounded-[2px]"
                        style={{ backgroundColor: meta.colour }}
                      />
                      {t(meta.shortKey)}
                    </span>
                  ) : (
                    <span className="text-muted-foreground">{t("sessions.none")}</span>
                  )}
                </TD>
                <TD className="px-3 py-1.5 text-center text-muted-foreground">
                  {row.think ? t("fair.yes") : t("fair.no")}
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
    </div>
  );
}

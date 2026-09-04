import { Download, Trash2 } from "lucide-react";
import { useMemo } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { Checkbox, LoadError, Skeleton } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { BarRows, Segments, ShareMeter, StatTile, type BarRow } from "@/features/admin/charts";
import { PROFILES, profileLabel } from "@/lib/evaluator";
import { duration, when } from "@/lib/format";
import { artifactName } from "@/lib/names";
import { STEPS } from "@/lib/steps";
import type { EvaluatorProfile } from "@/lib/types";
import { cn } from "@/lib/utils";

import { AdminSetsPanel } from "./AdminSetsPanel";
import { CROSS_EVALUATION } from "./config";
import { ARM_META } from "./arms";
import {
  useAdminEvaluations,
  useAdminStageEvaluations,
  useDeleteEvaluations,
  useDeleteEvaluatorRecords,
} from "./queries";
import { studyApi } from "./api";
import type {
  AdminEvaluations,
  AdminGroup,
  AdminStageEvaluations,
  EvaluationAggregates,
  EvaluationArm,
  StageAccountGroup,
  StageArtifactSummary,
  StudyFilters,
} from "./types";
import { useSelection } from "./useSelection";
import { useT, type Key, type Language } from "@/lib/i18n";

/** A three-way blind choice: what pure chance would produce. Every share is read
 *  against it, and the panel never shows one without drawing the other. */
const CHANCE = 1 / 3;

/** The order the arm palette was validated on. Anything that draws the three side by
 *  side draws them in it — the CVD check is over ADJACENT pairs. */
const ARMS: EvaluationArm[] = ["naive", "rag", "system"];

const RUBRIC_LABELS: Record<string, Key> = {
  prerequisites: "rubricScale.prerequisites",
  complexity: "rubricScale.complexity",
  concept_fit: "rubricScale.concept_fit",
  soundness: "rubricScale.soundness",
};

/** The two kinds of account as the FILTER names them — plural, because the button names a
 *  group of people, where `profileLabel` names one person's own profile. */
const PROFILE_FILTER_LABELS: Record<EvaluatorProfile, Key> = {
  teacher: "adminStudy.profile.teachers",
  student: "adminStudy.profile.students",
};

/** The three stages of the chain in the order the bar numbers them, so the forms are
 *  read in the order they were answered. */
const STAGE_ARTIFACTS = STEPS.flatMap((step) => (step.artifact ? [step.artifact] : []));

/**
 * The study's tab: WHO first, then the two instruments, each with its own CSV.
 *
 * The filter is one and it sits above both blocks, because the two instruments describe
 * the same people: a teacher who judged three comparisons also answered the forms at the
 * foot of each stage, and reading the two apart by different filters would be reading two
 * studies. The order of the selectors is the order of the question — which person, which
 * kind of person, which subject — and the account list narrows with the profile.
 */
export function StudyTab({
  filters,
  onFilters,
}: {
  filters: StudyFilters;
  onFilters: (next: StudyFilters) => void;
}) {
  const { t, plural } = useT();
  const study = useAdminEvaluations(filters);
  const stages = useAdminStageEvaluations(filters);

  if (study.isLoading && !study.data) return <Skeleton className="h-96" />;
  if (!study.data) {
    return (
      <LoadError title={t("adminStudy.unreadable")} error={study.error} onRetry={study.refetch} />
    );
  }
  const data = study.data;
  const filtered = Boolean(filters.workspace || filters.account != null || filters.profile);

  return (
    <div className="space-y-8">
      {/* Repartir comparaciones entre evaluadores es la mitad CRUZADA del estudio, apagada
          en esta rama (`study/config.ts`). Se va la sección entera y no solo su contenido:
          un encabezado sobre una tarjeta vacía dice que la función está rota, que es
          justo lo contrario de que no esté. */}
      {CROSS_EVALUATION ? (
        <Section
          eyebrow={t("adminStudy.handOut.eyebrow")}
          title={t("adminStudy.handOut.title")}
          description={t("adminStudy.handOut.description")}
        >
          <Card>
            <AdminSetsPanel />
          </Card>
        </Section>
      ) : null}

      <FilterBar
        data={data}
        filters={filters}
        onFilters={onFilters}
        summary={
          filtered
            ? `${plural("adminStudy.comparisonCount", data.aggregates.sessions)} · ${plural(
                "adminStudy.formCount",
                stages.data?.aggregates.answered ?? 0,
              )}`
            : null
        }
      />

      {/* The evaluators come FIRST, before either instrument: the reading starts from a
          person, and this table is what turns «este evaluador» into a filter over the
          whole tab. It carries both instruments in one row, because the same person
          answered both. */}
      <Card
        title={t("adminStudy.card.byAccount")}
        aside={
          filters.account != null ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onFilters({ ...filters, account: null })}
            >
              {t("adminStudy.backToAll")}
            </Button>
          ) : null
        }
      >
        <EvaluatorsTable
          study={data}
          stages={stages.data ?? null}
          selectedAccount={filters.account ?? null}
          onSelect={(id) => onFilters({ ...filters, account: id })}
        />
      </Card>

      <Section
        title={t("adminStudy.build.title")}
        description={t("adminStudy.build.description")}
        action={<CsvLink href={studyApi.adminStageCsvUrl(filters)} filtered={filtered} />}
      >
        {stages.data ? (
          stages.data.aggregates.rows === 0 ? (
            <Card>
              <p className="text-small text-muted-foreground">
                {filtered ? t("adminStudy.stages.filteredEmpty") : t("adminStudy.stages.empty")}
              </p>
            </Card>
          ) : (
            <StageForms data={stages.data} />
          )
        ) : stages.isLoading ? (
          <Skeleton className="h-48" />
        ) : (
          <LoadError
            title={t("adminStudy.stages.unreadable")}
            error={stages.error}
            onRetry={stages.refetch}
          />
        )}
      </Section>

      <Section
        title={t("adminStudy.tests.title")}
        description={t("adminStudy.tests.description")}
        action={<CsvLink href={studyApi.adminEvaluationCsvUrl(filters)} filtered={filtered} />}
      >
        {data.aggregates.sessions === 0 ? (
          <Card>
            <p className="text-small text-muted-foreground">
              {filtered ? t("adminStudy.filteredEmpty") : t("adminStudy.empty")}
            </p>
          </Card>
        ) : (
          <Comparisons data={data} />
        )}
      </Section>
    </div>
  );
}

/* The filter ------------------------------------------------------------------------- */

/**
 * WHO → which KIND of who → WHERE. Three selects on one line, each with its caption.
 *
 * The account list follows the profile: with «Docentes» chosen it offers teachers only,
 * and choosing a profile the chosen account does not have drops the account rather than
 * keeping a filter that matches nobody. An account already in the filter but absent
 * from the list — set from «Cuentas» on an API older than the bundle — is still offered,
 * by its id, so the filter can always be seen and cleared.
 */
function FilterBar({
  data,
  filters,
  onFilters,
  summary,
}: {
  data: AdminEvaluations;
  filters: StudyFilters;
  onFilters: (next: StudyFilters) => void;
  summary: string | null;
}) {
  const { t } = useT();
  const accounts = data.filters.accounts ?? [];
  const offered = filters.profile
    ? accounts.filter((account) => account.evaluator_profile === filters.profile)
    : accounts;
  const current = accounts.find((account) => account.id === filters.account);
  const filtered = Boolean(filters.workspace || filters.account != null || filters.profile);

  const setProfile = (profile: EvaluatorProfile | null) => {
    const keep = !profile || !current || current.evaluator_profile === profile;
    onFilters({ ...filters, profile, account: keep ? filters.account : null });
  };

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-3 shadow-sm">
      <Field label={t("adminStudy.filter.profile")}>
        {/* Three buttons and not a select: which KIND of person is the first question
            of the reading, and a control with all its options in view is one that gets
            found. `aria-pressed` says which is on. */}
        <div role="group" aria-label={t("adminStudy.filter.profile")} className="flex gap-1">
          {([null, ...PROFILES] as (EvaluatorProfile | null)[]).map((profile) => (
            <Button
              key={profile ?? "all"}
              type="button"
              size="sm"
              variant={(filters.profile ?? null) === profile ? "default" : "outline"}
              aria-pressed={(filters.profile ?? null) === profile}
              onClick={() => setProfile(profile)}
            >
              {profile ? t(PROFILE_FILTER_LABELS[profile]) : t("adminStudy.allProfiles")}
            </Button>
          ))}
        </div>
      </Field>

      <Field label={t("adminStudy.filter.account")}>
        <Select
          aria-label={t("adminStudy.filter.account")}
          value={filters.account ?? ""}
          onChange={(event) =>
            onFilters({ ...filters, account: event.target.value ? Number(event.target.value) : null })
          }
          className="w-56"
        >
          <option value="">{t("adminStudy.allAccounts")}</option>
          {filters.account != null && !current ? (
            <option value={filters.account}>#{filters.account}</option>
          ) : null}
          {offered.map((account) => (
            <option key={account.id} value={account.id}>
              {account.username}
              {account.name && account.name !== account.username ? ` · ${account.name}` : ""}
            </option>
          ))}
        </Select>
      </Field>

      <Field label={t("adminStudy.filter.workspace")}>
        <Select
          aria-label={t("adminStudy.filterByWorkspace")}
          value={filters.workspace ?? ""}
          onChange={(event) => onFilters({ ...filters, workspace: event.target.value || null })}
          className="w-52"
        >
          <option value="">{t("adminStudy.allWorkspaces")}</option>
          {data.filters.workspaces.map((slug) => (
            <option key={slug} value={slug}>
              {slug}
            </option>
          ))}
        </Select>
      </Field>

      {summary ? <span className="pb-2 text-small text-muted-foreground">{summary}</span> : null}

      {filtered ? (
        <Button variant="outline" size="sm" className="ml-auto" onClick={() => onFilters({})}>
          {t("adminStudy.backToTotal")}
        </Button>
      ) : null}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-micro font-condensed uppercase text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function CsvLink({ href, filtered }: { href: string; filtered: boolean }) {
  const { t } = useT();
  return (
    <a href={href} download className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
      <Download />
      CSV{filtered ? t("adminStudy.csvFiltered") : ""}
    </a>
  );
}

/* The blind comparisons ---------------------------------------------------------------- */

/**
 * The most important readings of the comparisons and nothing more: who won and whether
 * that beats chance, whether the proposals would be used, the rubric on the system's own
 * exercise, whether the instrument can be trusted, and the sessions themselves. The pace,
 * the reasoning draw and the per-subject and per-profile tables left the screen — the
 * profile is a filter now, the evaluators are the table at the top, and the rest is in
 * the CSV.
 */
function Comparisons({ data }: { data: AdminEvaluations }) {
  const { t } = useT();
  return (
    <>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Card title={t("adminStudy.card.wins")}>
          <Preferences aggregates={data.aggregates} />
        </Card>
        <Card title={t("adminStudy.card.triage")}>
          <Triage aggregates={data.aggregates} />
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card title={t("adminStudy.card.rubric")}>
          <Rubric aggregates={data.aggregates} />
        </Card>
        <Card title={t("adminStudy.card.measurement")}>
          <Measurement data={data} />
        </Card>
      </div>

      <Card title={t("adminStudy.card.sessions", { n: data.sessions.length })}>
        <SessionsTable rows={data.sessions} />
      </Card>
    </>
  );
}

/**
 * The two halves of this screen, told apart by structure rather than by colour: an
 * eyebrow at the condensed micro step, a title two steps above the cards' own, and a rule
 * under both. The action slot holds the block's own CSV, on the title's line, because a
 * download is scoped to what the block shows and belongs beside its name.
 */
function Section({
  eyebrow,
  title,
  description,
  action,
  children,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-border pb-2">
        <div className="space-y-1">
          {eyebrow ? (
            <p className="text-micro font-condensed uppercase text-muted-foreground">{eyebrow}</p>
          ) : null}
          <h2 className="font-display font-expanded text-title">{title}</h2>
          <p className="text-small text-muted-foreground">{description}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </header>
      {children}
    </section>
  );
}

function Card({
  title,
  aside,
  children,
}: {
  title?: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-3 shadow-sm">
      {title ? (
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-small font-medium">{title}</h3>
          {aside}
        </div>
      ) : null}
      {children}
    </section>
  );
}

const percent = (value: number | null | undefined) =>
  value == null ? "—" : `${Math.round(value * 100)} %`;

/** A mean on a 1-5 scale, one decimal, with the reader's own decimal mark. */
function fixed1(value: number | null | undefined, language: Language): string {
  if (value == null) return "—";
  const text = value.toFixed(1);
  return language === "es" ? text.replace(".", ",") : text;
}

/** A p-value is written as a threshold, not as a verdict: the panel reports, it does not
 *  conclude. `< 0.001` rather than a wall of zeros, and never a "significativo" label. */
function pValue(p: number | null | undefined, language: Language): string {
  if (p == null) return "—";
  const decimal = (value: string) => (language === "es" ? value.replace(".", ",") : value);
  if (p < 0.001) return `p < ${decimal("0.001")}`;
  return `p = ${decimal(p.toFixed(3))}`;
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
                  ? t("adminStudy.ci95", {
                      low: percent(slice.ci95_usable[0]),
                      high: percent(slice.ci95_usable[1]),
                    })
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
  const { plural, t, language } = useT();
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
            <span className="nums">{pValue(position.p, language)}</span>
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
      <p className="text-small text-muted-foreground">
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
      <h3 className="text-small font-medium text-muted-foreground">
        {t("adminStudy.noValidItem")}
      </h3>
      <div className="grid grid-cols-3 gap-2">
        {ARMS.map((arm) => {
          const counts = aggregates.arm_status[arm] ?? {};
          const bad = (counts.failed ?? 0) + (counts.unavailable ?? 0);
          return (
            <div key={arm} className="rounded-lg border border-border px-2.5 py-1.5">
              <p className="flex items-center gap-1.5 truncate text-small text-muted-foreground">
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
      <p className="text-small text-muted-foreground">
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
        <p className="text-small text-muted-foreground">
          {t("adminStudy.complexityNote")}
          <span className="nums">{rubric.complexity.mean_distance_to_3}</span>.
        </p>
      ) : null}
    </div>
  );
}

/**
 * One row per person, both instruments side by side: how far down the construction they
 * went and how they judged it, then how many comparisons they decided and how often the
 * system won. Sorted by who did most. A row is a filter over the whole tab, and the
 * selected one is drawn as such; the way back is the button in the card's header.
 *
 * `sessions` and `decided` stay separate on purpose: somebody who launched twenty
 * comparisons and judged three has contributed three data points.
 */
function EvaluatorsTable({
  study,
  stages,
  selectedAccount,
  onSelect,
}: {
  study: AdminEvaluations;
  stages: AdminStageEvaluations | null;
  /** The account the tab is filtered by, drawn as the selected row. */
  selectedAccount: number | null;
  onSelect: (id: number | null) => void;
}) {
  const { t, plural, language } = useT();
  const confirm = useConfirm();
  const toast = useToast();
  const remove = useDeleteEvaluatorRecords();

  const rows = useMemo(() => {
    const merged = new Map<string, EvaluatorRow>();
    const row = (key: string, label: string, name: string | null, profile: EvaluatorProfile | null | undefined) => {
      let entry = merged.get(key);
      if (!entry) {
        entry = { key, label, name, profile: profile ?? null, forms: null, comparisons: null, last_at: 0 };
        merged.set(key, entry);
      }
      return entry;
    };
    for (const group of stages?.by_account ?? []) {
      const entry = row(String(group.key), group.label, group.name, group.evaluator_profile);
      entry.forms = group;
      entry.last_at = Math.max(entry.last_at, group.last_at);
    }
    for (const group of study.by_account) {
      const entry = row(String(group.key), group.label, group.name, group.evaluator_profile);
      entry.comparisons = group;
      entry.last_at = Math.max(entry.last_at, group.last_at);
    }
    return [...merged.values()].sort(
      (a, b) =>
        (b.forms?.answered ?? 0) + (b.comparisons?.decided ?? 0) -
          ((a.forms?.answered ?? 0) + (a.comparisons?.decided ?? 0)) ||
        b.last_at - a.last_at ||
        a.label.localeCompare(b.label),
    );
  }, [study.by_account, stages?.by_account]);

  // Only a row with an account can be withdrawn: stock nobody holds has no evaluator.
  const ids = useMemo(() => rows.map((r) => r.key).filter((key) => Number(key) > 0), [rows]);
  const { selected, all: allSelected, some: someSelected, toggle, toggleAll, clear } =
    useSelection(ids);

  const confirmDelete = async () => {
    const accounts = [...selected].map(Number);
    const names = rows.filter((r) => selected.has(r.key)).map((r) => r.label);
    const forms = rows
      .filter((r) => selected.has(r.key))
      .reduce((sum, r) => sum + (r.forms?.opened ?? 0), 0);
    const sessions = rows
      .filter((r) => selected.has(r.key))
      .reduce((sum, r) => sum + (r.comparisons?.sessions ?? 0), 0);
    const message =
      t("adminStudy.records.confirmHead", { names: names.join(", ") }) +
      t("adminStudy.records.confirmBody", {
        sessions: plural("adminStudy.comparisons", sessions),
        forms: plural("adminStudy.formCount", forms),
      });
    if (!(await confirm({ title: message, tone: "danger" }))) return;
    remove.mutate(accounts, {
      onSuccess: (result) => {
        clear();
        if (selectedAccount !== null && accounts.includes(selectedAccount)) onSelect(null);
        toast({
          title: t("adminStudy.records.deleted"),
          description: t("adminStudy.records.deletedBody", {
            sessions: plural("adminStudy.comparisons", result.sessions),
            forms: plural("adminStudy.formCount", result.forms),
          }),
          tone: "attention",
        });
      },
      onError: (error: Error) =>
        toast({ title: t("adminStudy.records.failed"), description: error.message, tone: "danger" }),
    });
  };

  if (rows.length === 0) {
    return <p className="text-small text-muted-foreground">{t("adminStudy.nothingToGroup")}</p>;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-small text-muted-foreground">
          {selected.size > 0
            ? plural("adminStudy.records.selected", selected.size)
            : t("adminStudy.records.selectHint")}
        </span>
        <Button
          variant="destructive"
          size="sm"
          className="ml-auto"
          disabled={selected.size === 0 || remove.isPending}
          onClick={confirmDelete}
        >
          <Trash2 />
          {t("adminStudy.records.delete")}
        </Button>
      </div>
      <Table minWidth="64rem">
        <THead>
          <TR>
            <TH className="w-8">
              <Checkbox
                checked={allSelected}
                indeterminate={someSelected}
                onCheckedChange={toggleAll}
                label={allSelected ? t("adminStudy.records.deselectAll") : t("adminStudy.records.selectAll")}
              />
            </TH>
            <TH>{t("adminStudy.col.evaluator")}</TH>
            <TH>{t("adminStudy.col.profile")}</TH>
            {STAGE_ARTIFACTS.map((artifact) => (
              <TH key={artifact} align="num">
                {artifactName(artifact, t)}
              </TH>
            ))}
            <TH align="num">{t("adminStudy.stages.col.mean")}</TH>
            <TH align="num">{t("adminStudy.stages.col.curated")}</TH>
            <TH align="num">{t("adminStudy.col.sessions")}</TH>
            <TH align="num">{t("adminStudy.col.decided")}</TH>
            <TH>{t("adminStudy.col.systemWon")}</TH>
            <TH align="num">{t("adminStudy.col.last")}</TH>
          </TR>
        </THead>
        <TBody>
          {rows.map((entry) => {
            const id = Number(entry.key) || null;
            return (
              <TR
                key={entry.key}
                selected={selectedAccount !== null && selectedAccount === id}
                onSelect={() => onSelect(id)}
              >
                {/* The checkbox cell swallows the click, or ticking a box would also filter
                    the whole tab by that person. */}
                <TD className="py-1.5 pl-3" onClick={(event) => event.stopPropagation()}>
                  {id !== null ? (
                    <Checkbox
                      checked={selected.has(entry.key)}
                      onCheckedChange={(next) => toggle(entry.key, next)}
                      label={t("adminStudy.records.select", { name: entry.label })}
                    />
                  ) : null}
                </TD>
                <TD className="max-w-56 truncate py-1.5 pr-3">
                  {entry.label}
                  {entry.name && entry.name !== entry.label ? (
                    <span className="ml-1 text-muted-foreground">· {entry.name}</span>
                  ) : null}
                </TD>
                <TD className="px-3 py-1.5 text-muted-foreground">
                  {profileLabel(entry.profile, t)}
                </TD>
                {STAGE_ARTIFACTS.map((artifact) => (
                  <TD key={artifact} align="num" className="px-3 py-1.5 nums">
                    {entry.forms?.per_artifact[artifact] ?? 0}
                  </TD>
                ))}
                <TD align="num" className="px-3 py-1.5 nums">
                  {fixed1(entry.forms?.overall_mean, language)}
                </TD>
                <TD align="num" className="px-3 py-1.5 nums">{entry.forms?.curated ?? 0}</TD>
                <TD align="num" className="px-3 py-1.5 nums">{entry.comparisons?.sessions ?? 0}</TD>
                <TD align="num" className="px-3 py-1.5 nums">{entry.comparisons?.decided ?? 0}</TD>
                <TD className="px-3 py-1.5">
                  <ShareMeter
                    value={entry.comparisons?.preferences?.system ?? 0}
                    total={entry.comparisons?.decided ?? 0}
                    reference={CHANCE}
                    title={t("adminStudy.shareTitle", {
                      system: entry.comparisons?.preferences?.system ?? 0,
                      decided: entry.comparisons?.decided ?? 0,
                    })}
                  />
                </TD>
                <TD align="num" className="whitespace-nowrap py-1.5 pl-3 text-muted-foreground">
                  {entry.last_at ? when(new Date(entry.last_at * 1000).toISOString()) : "—"}
                </TD>
              </TR>
            );
          })}
        </TBody>
      </Table>
    </div>
  );
}

interface EvaluatorRow {
  key: string;
  label: string;
  name: string | null;
  profile: EvaluatorProfile | null;
  forms: StageAccountGroup | null;
  comparisons: AdminGroup | null;
  last_at: number;
}

type SessionRow = AdminEvaluations["sessions"][number];

function SessionsTable({ rows }: { rows: SessionRow[] }) {
  const { plural, t } = useT();
  const confirm = useConfirm();
  const toast = useToast();
  const remove = useDeleteEvaluations();
  const ids = useMemo(() => rows.map((row) => row.id), [rows]);
  const { selected, all: allSelected, some: someSelected, toggle, toggleAll, clear } =
    useSelection(ids);

  const confirmDelete = async () => {
    const ids = [...selected];
    const decided = rows.filter((row) => selected.has(row.id) && row.chosen_at !== null).length;
    const message =
      (ids.length === 1
        ? t("adminStudy.confirmHeadOne")
        : t("adminStudy.confirmHeadMany", { n: ids.length })) +
      (decided ? plural("sessions.confirmDecided", decided) : "") +
      t("sessions.confirmTail");
    if (!(await confirm({ title: message, tone: "danger" }))) return;
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

/* The construction forms --------------------------------------------------------------- */

/**
 * What the teachers said about the chain itself, stage by stage.
 *
 * Four figures first, then one card per stage in the order the bar numbers them. Every
 * distribution is one ordinal answer, so every one is the same segmented bar: darker is
 * better, and the card can be read top to bottom as a column of verdicts without reading
 * a single legend. The forms themselves are the CSV's; a log of who filled what in when
 * was drawn here for a day and taken out — nobody reads a study that way.
 */
function StageForms({ data }: { data: AdminStageEvaluations }) {
  const { t, language } = useT();
  const { aggregates, by_account } = data;
  const curated = by_account.reduce((sum, group) => sum + group.curated, 0);
  const byArtifact = new Map(aggregates.by_artifact.map((entry) => [entry.artifact, entry]));

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label={t("adminStudy.stages.stat.answered")}
          value={aggregates.answered}
          hint={t("adminStudy.stages.stat.opened", { n: aggregates.rows })}
        />
        <StatTile
          label={t("adminStudy.stages.stat.mean")}
          value={fixed1(aggregates.overall_mean, language)}
          hint={t("adminStudy.stages.stat.outOf")}
        />
        <StatTile
          label={t("adminStudy.stages.stat.people")}
          value={by_account.filter((group) => group.answered > 0).length}
        />
        <StatTile
          label={t("adminStudy.stages.stat.curated")}
          value={curated}
          hint={t("adminStudy.stages.stat.curatedHint", {
            pct: percent(aggregates.answered ? curated / aggregates.answered : null),
          })}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {STAGE_ARTIFACTS.map((artifact) => {
          const summary = byArtifact.get(artifact);
          return summary ? <StageCard key={artifact} summary={summary} /> : null;
        })}
      </div>
    </>
  );
}

/**
 * One stage: the 1-5 scale first, then the five questions in the order asked, then the
 * two facts a mean hides — whether the person had corrected the artifact first, and how
 * long they took.
 */
function StageCard({ summary }: { summary: StageArtifactSummary }) {
  const { t, plural, language } = useT();
  const stepIndex = STEPS.findIndex((step) => step.artifact === summary.artifact);

  return (
    <Card
      title={
        stepIndex >= 0
          ? t("adminStudy.stages.cardTitle", { n: stepIndex + 1, name: artifactName(summary.artifact, t) })
          : artifactName(summary.artifact, t)
      }
      aside={
        <span className="text-small text-muted-foreground">
          {plural("adminStudy.stages.answers", summary.answered)}
          {summary.opened > summary.answered
            ? ` · ${plural("adminStudy.stages.openedOnly", summary.opened - summary.answered)}`
            : ""}
        </span>
      }
    >
      {summary.answered === 0 ? (
        <p className="text-small text-muted-foreground">{t("adminStudy.stages.noAnswers")}</p>
      ) : (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-small text-muted-foreground">{t("adminStudy.stages.overall")}</p>
              <p className="text-title nums">
                {fixed1(summary.overall.mean, language)}
                <span className="ml-1 text-small text-muted-foreground">/ 5</span>
              </p>
            </div>
            <Segments
              best="last"
              segments={Object.entries(summary.overall.counts).map(([value, count]) => ({
                key: value,
                label: value,
                value: count,
              }))}
            />
          </div>

          <div className="space-y-3 border-t border-border pt-3">
            {summary.questions.map((question) => (
              <div key={question.key} className="space-y-1.5">
                <p className="text-small">{question.question}</p>
                <Segments
                  best="first"
                  segments={question.options.map((option) => ({
                    key: option.value,
                    label: option.label,
                    value: question.counts[option.value] ?? 0,
                  }))}
                />
              </div>
            ))}
            {summary.usable != null ? (
              <p className="text-small text-muted-foreground">
                {t("adminStudy.stages.usable", { pct: percent(summary.usable) })}
              </p>
            ) : null}
          </div>

          <dl className="space-y-1 border-t border-border pt-2 text-small text-muted-foreground">
            <div className="flex flex-wrap gap-x-2">
              <dt>{t("adminStudy.stages.curation")}</dt>
              <dd className="nums">
                {(["yes", "no", "unknown"] as const)
                  .map((state) => {
                    const slice = summary.curation[state];
                    const mean =
                      slice.overall_mean != null
                        ? ` (${t("adminStudy.stages.meanShort", {
                            mean: fixed1(slice.overall_mean, language),
                          })})`
                        : "";
                    return `${slice.n} ${t(CURATION_LABELS[state])}${mean}`;
                  })
                  .join(" · ")}
              </dd>
            </div>
            {/* A median of zero is a form saved the instant it opened — a clock that
                measured nothing — and «0 ms» would report it as a speed. */}
            {summary.seconds.median ? (
              <div className="flex flex-wrap gap-x-2">
                <dt>{t("adminStudy.stages.time")}</dt>
                <dd className="nums">
                  {t("adminStudy.stages.median", {
                    time: duration(summary.seconds.median * 1000),
                    n: plural("adminStudy.formCount", summary.seconds.n),
                  })}
                </dd>
              </div>
            ) : null}
            {summary.notes > 0 ? (
              <div className="flex flex-wrap gap-x-2">
                <dt>{t("adminStudy.stages.notes")}</dt>
                <dd className="nums">{summary.notes}</dd>
              </div>
            ) : null}
          </dl>
        </div>
      )}
    </Card>
  );
}

const CURATION_LABELS: Record<"yes" | "no" | "unknown", Key> = {
  yes: "adminStudy.stages.curatedYes",
  no: "adminStudy.stages.curatedNo",
  unknown: "adminStudy.stages.curatedUnknown",
};

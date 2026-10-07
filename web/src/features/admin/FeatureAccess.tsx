import { useId, useState, type Dispatch, type SetStateAction } from "react";

import { ChoicePill } from "@/components/ui/choice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SearchInput, Select } from "@/components/ui/input";
import { Checkbox, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { PersonName } from "@/components/ui/person";
import { useRadioGroup } from "@/components/ui/radio";
import { useToast } from "@/components/ui/toast";
import { accountsIn } from "@/features/admin/accounts";
import { SectionHeader } from "@/features/admin/Sections";
import { FormError } from "@/features/auth/AuthLayout";
import { useT, type Key, type Translate } from "@/lib/i18n";
import { featureLabelKey } from "@/lib/steps";
import { fold } from "@/lib/text";
import {
  featureAccessOf,
  SUBJECT_LISTED,
  type AdminAccount,
  type AdminWorkspace,
  type FeatureAccessState,
  type FeatureMode,
  type FeatureName,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { useSession } from "@/state/auth";
import { useAdminFeatures, useSetFeature } from "@/state/queries";

const MODES: { mode: FeatureMode; labelKey: Key }[] = [
  { mode: "off", labelKey: "feature.mode.off" },
  { mode: "all", labelKey: "feature.mode.all" },
  { mode: "selected", labelKey: "feature.mode.selected" },
];

// Below this many accounts a search box finds nothing a glance would not.
const SEARCH_FROM = 9;

/** The panel's unsaved changes to who may use each function: none until one is edited. */
export type AccessDrafts = {
  values: Partial<Record<FeatureName, FeatureAccessState>>;
  set: Dispatch<SetStateAction<Partial<Record<FeatureName, FeatureAccessState>>>>;
};

/**
 * Hold the drafts of who may use each function, for the screen that draws every tab.
 *
 * Held there for the reason the stages' draft is (`useStagesDraft`): a folded setting under a
 * function's settings links to «Configuración», and a draft kept inside the tab died with it,
 * mode and ticks gone without a word, while the stages' draft beside it came back pending.
 */
export function useAccessDrafts(): AccessDrafts {
  const [values, set] = useState<Partial<Record<FeatureName, FeatureAccessState>>>({});
  return { values, set };
}

/**
 * WHO ONE OPTIONAL FUNCTION IS FOR: nobody, every account, or the accounts ticked. It is
 * the «Permisos de uso» section of the function's tab, header included: the header's one
 * sentence is the SAVED state, and the block under it is the draft.
 *
 * The draft is the panel's (`useAccessDrafts`) and one button saves it. The server keeps the
 * list whatever the mode, so the ticks stay on screen, dimmed, while another mode is chosen:
 * switching back finds them as they were. Only a list that changed is sent, because a write
 * without one leaves the server's as it is.
 *
 * The administrator is not exempt (`server/features.py`): under «Cuentas elegidas» their own
 * account opens the function only when it is ticked, like anybody's. One line says so,
 * because the panel is the one screen where an administrator expects to see everything.
 *
 * A class is ticked at once: under «Cuentas elegidas» a subject is chosen and every account
 * in it now (`accountsIn`, teachers included, paused memberships left out) is ticked, or
 * unticked, in one press. The ticks are the draft as any other, so nothing is saved by it.
 *
 * The tutor may also list whole subjects («Asignaturas elegidas», `SUBJECT_LISTED`): everybody
 * in one uses it there, whoever joins later included, and not in their other subjects. The
 * accounts' shortcut ticks who is in a subject today; the subject's list follows its class.
 */
export function FeatureAccess({
  feature,
  accounts,
  workspaces,
  drafts,
}: {
  feature: FeatureName;
  accounts: AdminAccount[];
  workspaces: AdminWorkspace[];
  drafts: AccessDrafts;
}) {
  const { t, plural } = useT();
  const toast = useToast();
  const session = useSession();
  const query = useAdminFeatures();
  const write = useSetFeature();
  const draft = drafts.values[feature] ?? null;
  const setDraft = (next: FeatureAccessState | null) =>
    drafts.set((held) => {
      const updated = { ...held };
      if (next) updated[feature] = next;
      else delete updated[feature];
      return updated;
    });
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("");
  const headingId = useId();
  const subjectId = useId();
  const saved = query.data ? featureAccessOf(query.data, feature) : null;
  const current = draft ?? saved;
  // Back to the saved state is no draft at all, so the save button greys out again.
  const change = (next: FeatureAccessState) =>
    setDraft(
      saved &&
        next.mode === saved.mode &&
        sameIds(next.accounts, saved.accounts) &&
        sameSlugs(next.workspaces ?? [], saved.workspaces ?? [])
        ? null
        : next,
    );
  const modes = useRadioGroup(
    MODES.map(({ mode }) => mode),
    current?.mode,
    (mode) => {
      if (current) change({ ...current, mode });
    },
  );

  if (query.isLoading) return <Skeleton className="h-40" />;
  if (!saved || !current) {
    return (
      <LoadError title={t("feature.unreadable")} error={query.error} onRetry={query.refetch} />
    );
  }

  const name = t(featureLabelKey(feature));
  const listChanged = !sameIds(current.accounts, saved.accounts);
  // A function a whole subject may be listed for (the tutor): its subjects are a list of their own.
  const bySubjects = SUBJECT_LISTED.includes(feature);
  const subjects = current.workspaces ?? [];
  const subjectsChanged = bySubjects && !sameSlugs(subjects, saved.workspaces ?? []);
  const dirty = current.mode !== saved.mode || listChanged || subjectsChanged;
  const listedSubjects = new Set(subjects);
  const tickSubjectRow = (slug: string, on: boolean) =>
    change({
      ...current,
      workspaces: on
        ? [...subjects, slug].sort((a, b) => a.localeCompare(b))
        : subjects.filter((other) => other !== slug),
    });
  const selecting = current.mode === "selected";
  const ticked = new Set(current.accounts);
  const known = accounts.filter((account) => ticked.has(account.id));

  const tick = (id: number, on: boolean) =>
    change({
      ...current,
      accounts: on
        ? [...current.accounts, id].sort((a, b) => a - b)
        : current.accounts.filter((other) => other !== id),
    });

  // The chosen subject's accounts, and how many of them are ticked already.
  const inSubject = subject ? accountsIn(accounts, subject) : [];
  const tickedInSubject = inSubject.filter((id) => ticked.has(id)).length;
  const tickSubject = (on: boolean) => {
    const wanted = new Set(inSubject);
    change({
      ...current,
      accounts: on
        ? [...new Set([...current.accounts, ...inSubject])].sort((a, b) => a - b)
        : current.accounts.filter((id) => !wanted.has(id)),
    });
  };

  const submit = () =>
    write.mutate(
      {
        feature,
        mode: current.mode,
        ...(listChanged ? { accounts: current.accounts } : {}),
        ...(subjectsChanged ? { workspaces: subjects } : {}),
      },
      {
        onSuccess: () => {
          setDraft(null);
          toast({ title: t("feature.saved"), description: name });
        },
      },
    );

  // With another mode chosen only the ticked rows are drawn, and unfiltered: they are what is
  // kept, and a dimmed list of everybody else says nothing.
  const wanted = selecting ? fold(search.trim()) : "";
  const rows = (selecting ? accounts : known).filter(
    (account) => !wanted || fold(`${account.username} ${account.name}`).includes(wanted),
  );

  return (
    <>
      <SectionHeader
        id={headingId}
        title={t("feature.section.access")}
        description={stateSentence(saved, t, plural, bySubjects)}
      />
      <section aria-labelledby={headingId} className="surface space-y-4 p-5">
        <div
          role="radiogroup"
          aria-label={t("feature.heading", { name })}
          className="flex flex-wrap gap-2"
          {...modes.group}
        >
          {MODES.map(({ mode, labelKey }) => {
            const chosen = mode === current.mode;
            return (
              <ChoicePill
                key={mode}
                {...modes.radio(mode)}
                chosen={chosen}
                disabled={write.isPending}
                onClick={() => change({ ...current, mode })}
              >
                {t(labelKey)}
              </ChoicePill>
            );
          })}
        </div>

        {bySubjects && (selecting || subjects.length > 0) ? (
          <div className="space-y-2">
            <h3 className="text-heading">{t("feature.subjects.title")}</h3>
            <p className="text-small text-muted-foreground">
              {selecting ? t("feature.subjects.lead") : t("feature.kept")}
            </p>
            {workspaces.length === 0 ? (
              <p className="text-small text-muted-foreground">{t("feature.subjects.none")}</p>
            ) : (
              <ul
                className={cn(
                  "well thin-scroll rows max-h-56 overflow-y-auto px-2 py-1 rows-flush",
                  !selecting && "opacity-60",
                )}
              >
                {(selecting ? workspaces : workspaces.filter((row) => listedSubjects.has(row.slug))).map(
                  (row) => (
                    <li key={row.slug}>
                      <label
                        className={cn(
                          "flex items-center gap-2 rounded-md px-1 py-2",
                          selecting && "cursor-pointer hover:bg-accent",
                        )}
                      >
                        <Checkbox
                          checked={listedSubjects.has(row.slug)}
                          disabled={!selecting || write.isPending}
                          onCheckedChange={(on) => tickSubjectRow(row.slug, on)}
                          label={row.name}
                          className={selecting ? undefined : "disabled:opacity-100"}
                        />
                        <span className="truncate">{row.name}</span>
                        <span className="min-w-0 flex-1 truncate font-mono text-small text-muted-foreground">
                          {row.slug}
                        </span>
                      </label>
                    </li>
                  ),
                )}
              </ul>
            )}
          </div>
        ) : null}

        {selecting || known.length > 0 ? (
          <div className="space-y-2">
            {bySubjects ? <h3 className="text-heading">{t("feature.accounts.title")}</h3> : null}
            {selecting && workspaces.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2">
                <label htmlFor={subjectId} className="text-small text-muted-foreground">
                  {t("feature.bySubject")}
                </label>
                <Select
                  id={subjectId}
                  value={subject}
                  className="w-full sm:w-auto sm:min-w-64 sm:max-w-md"
                  onChange={(event) => setSubject(event.target.value)}
                >
                  <option value="">{t("feature.bySubject.pick")}</option>
                  {workspaces.map((row) => (
                    <option key={row.slug} value={row.slug}>
                      {row.name}
                    </option>
                  ))}
                </Select>
                {subject ? (
                  <>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={write.isPending || tickedInSubject === inSubject.length}
                      onClick={() => tickSubject(true)}
                    >
                      {t("feature.bySubject.tick", { n: inSubject.length })}
                    </Button>
                    {tickedInSubject > 0 ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={write.isPending}
                        onClick={() => tickSubject(false)}
                      >
                        {t("feature.bySubject.untick", { n: tickedInSubject })}
                      </Button>
                    ) : null}
                  </>
                ) : null}
              </div>
            ) : null}
            {selecting && accounts.length >= SEARCH_FROM ? (
              <SearchInput
                value={search}
                aria-label={t("feature.search")}
                placeholder={t("feature.search")}
                className="sm:w-72"
                onChange={(event) => setSearch(event.target.value)}
              />
            ) : null}
            <p className="text-small text-muted-foreground">
              {selecting
                ? t("feature.ticked", { n: known.length, total: accounts.length })
                : t("feature.kept")}
            </p>
            {rows.length === 0 ? (
              <p className="text-small text-muted-foreground">{t("feature.noMatch")}</p>
            ) : (
              // Only the list is dimmed while another mode is chosen: the sentence above it is
              // the one that says why, and dimmed it fell under the contrast floor.
              <ul
                className={cn(
                  "well thin-scroll rows max-h-72 overflow-y-auto px-2 py-1 rows-flush",
                  !selecting && "opacity-60",
                )}
              >
                {rows.map((account) => (
                  <li key={account.id}>
                    {/* A label around the box: the whole row ticks it, the name included. */}
                    <label
                      className={cn(
                        "flex items-center gap-2 rounded-md px-1 py-2",
                        selecting && "cursor-pointer hover:bg-accent",
                      )}
                    >
                      <Checkbox
                        checked={ticked.has(account.id)}
                        disabled={!selecting || write.isPending}
                        onCheckedChange={(on) => tick(account.id, on)}
                        label={account.username}
                        // The kept list is dimmed once, as a whole; the box's own disabled
                        // dimming on top would all but erase the ticks.
                        className={selecting ? undefined : "disabled:opacity-100"}
                      />
                      <PersonName
                        name={account.name || account.username}
                        username={account.username}
                        badges={
                          <>
                            {account.id === session.data?.user.id ? (
                              <Badge variant="outline">{t("acc.badge.you")}</Badge>
                            ) : null}
                            {account.disabled ? (
                              <Badge variant="outline">{t("acc.badge.disabled")}</Badge>
                            ) : null}
                          </>
                        }
                      />
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}

        <p className="text-small text-muted-foreground">{t("feature.adminNote")}</p>

        <FormError error={write.error} />
        <Button disabled={!dirty || write.isPending} onClick={submit}>
          {write.isPending ? <Spinner /> : null}
          {t("feature.save")}
        </Button>
      </section>
    </>
  );
}

/**
 * What the SAVED state means, in one sentence: the draft is what the controls show. For a
 * function a subject may be listed for, it names the three things — the mode, the accounts
 * and the subjects.
 */
function stateSentence(
  saved: FeatureAccessState,
  t: Translate["t"],
  plural: Translate["plural"],
  bySubjects = false,
): string {
  if (saved.mode === "all") return t("feature.state.all");
  if (saved.mode !== "selected") return t("feature.state.off");
  const subjects = bySubjects ? (saved.workspaces ?? []).length : 0;
  if (subjects > 0) {
    const where = plural("feature.state.subjectsN", subjects);
    return saved.accounts.length > 0
      ? t("feature.state.accountsAndSubjects", {
          accounts: plural("feature.state.accountsN", saved.accounts.length),
          subjects: where,
        })
      : t("feature.state.subjectsOnly", { subjects: where });
  }
  if (saved.accounts.length > 0) return plural("feature.state.selected", saved.accounts.length);
  return t("feature.state.empty");
}

/** Whether two lists of subject slugs hold the same subjects, whatever their order. */
function sameSlugs(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const other = new Set(b);
  return a.every((slug) => other.has(slug));
}

/** Whether two lists of account ids hold the same accounts, whatever their order. */
function sameIds(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  const other = new Set(b);
  return a.every((id) => other.has(id));
}

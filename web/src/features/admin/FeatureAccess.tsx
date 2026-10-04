import { useId, useState, type Dispatch, type SetStateAction } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { FormError } from "@/features/auth/AuthLayout";
import { useT, type Key, type Translate } from "@/lib/i18n";
import { featureLabelKey } from "@/lib/steps";
import { fold } from "@/lib/text";
import {
  featureAccessOf,
  type AdminAccount,
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
 */
export function FeatureAccess({
  feature,
  accounts,
  drafts,
}: {
  feature: FeatureName;
  accounts: AdminAccount[];
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
  const headingId = useId();
  const saved = query.data ? featureAccessOf(query.data, feature) : null;
  const current = draft ?? saved;
  // Back to the saved state is no draft at all, so the save button greys out again.
  const change = (next: FeatureAccessState) =>
    setDraft(
      saved && next.mode === saved.mode && sameIds(next.accounts, saved.accounts) ? null : next,
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
  const dirty = current.mode !== saved.mode || listChanged;
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

  const submit = () =>
    write.mutate(
      {
        feature,
        mode: current.mode,
        ...(listChanged ? { accounts: current.accounts } : {}),
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
        description={stateSentence(saved, t, plural)}
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
              <button
                key={mode}
                {...modes.radio(mode)}
                type="button"
                role="radio"
                aria-checked={chosen}
                disabled={write.isPending}
                onClick={() => change({ ...current, mode })}
                className={cn(
                  "rounded-lg flex items-center gap-2 border px-3 py-2 text-left text-body transition-colors",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  "disabled:cursor-not-allowed disabled:opacity-60",
                  chosen ? "border-primary" : "border-input hover:border-primary",
                )}
              >
                {/* The square the mark is made of: filled is the one chosen. */}
                <span
                  aria-hidden
                  className={cn(
                    "size-3 shrink-0 border-[1.5px]",
                    chosen ? "border-primary bg-primary" : "border-input",
                  )}
                />
                {t(labelKey)}
              </button>
            );
          })}
        </div>

        {selecting || known.length > 0 ? (
          <div className="space-y-2">
            {selecting && accounts.length >= SEARCH_FROM ? (
              <Input
                type="search"
                value={search}
                aria-label={t("feature.search")}
                placeholder={t("feature.search")}
                className="w-full sm:w-72"
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
                  "thin-scroll max-h-72 divide-y divide-border overflow-y-auto",
                  !selecting && "opacity-60",
                )}
              >
                {rows.map((account) => (
                  <li key={account.id}>
                    {/* A label around the box: the whole row ticks it, the name included. */}
                    <label
                      className={cn(
                        "flex items-center gap-2 px-1 py-2",
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
                      <span className="truncate font-mono">{account.username}</span>
                      {account.id === session.data?.user.id ? (
                        <Badge variant="outline">{t("acc.badge.you")}</Badge>
                      ) : null}
                      {account.disabled ? (
                        <Badge variant="outline">{t("acc.badge.disabled")}</Badge>
                      ) : null}
                      <span className="min-w-0 flex-1 truncate text-small text-muted-foreground">
                        {account.name}
                      </span>
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

/** What the SAVED state means, in one sentence: the draft is what the controls show. */
function stateSentence(
  saved: FeatureAccessState,
  t: Translate["t"],
  plural: Translate["plural"],
): string {
  if (saved.mode === "all") return t("feature.state.all");
  if (saved.mode === "selected" && saved.accounts.length > 0) {
    return plural("feature.state.selected", saved.accounts.length);
  }
  return saved.mode === "selected" ? t("feature.state.empty") : t("feature.state.off");
}

/** Whether two lists of account ids hold the same accounts, whatever their order. */
function sameIds(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  const other = new Set(b);
  return a.every((id) => other.has(id));
}

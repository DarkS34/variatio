import { Check, CircleSlash, Plus, Search, Send, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { EMPTY_FORM, type FormState } from "@/features/generate/commission";
import { Count, GenerateForm } from "@/features/generate/GenerateForm";
import { profileLabel } from "@/lib/evaluator";
import { when } from "@/lib/format";
import { artifactName } from "@/lib/names";
import { fold } from "@/lib/text";
import { cn } from "@/lib/utils";
import { useKg, useKgGraph, useProfile } from "@/state/queries";

import { toStockParams } from "./commission";
import {
  useAssignSet,
  useAssignableAccounts,
  useEvaluationSets,
  useGenerateEvaluations,
} from "./queries";
import type {
  AssignableAccount,
  AssignableWorkspace,
  EvaluationSet,
  EvaluatorProfile,
} from "./types";
import { useT } from "@/lib/i18n";

/**
 * Handing comparisons out, in the order the decision is actually made.
 *
 * WHO first, then WHERE, then WHICH — and that order is the design. With evaluators drawn
 * from different subjects and different years there is no rule that can share a workload
 * out: only the administrator knows who teaches what, and asking somebody to judge a
 * syllabus they have never taught produces an answer of convenience, which is worse than
 * producing none. Starting from the person is what makes "¿puede juzgar esto?" the first
 * question instead of an afterthought.
 *
 * What a copy shares with its source is the three EXERCISES; what it does not share is the
 * order. Two evaluators on one shuffle share a position bias, and an agreement that
 * includes it is not an agreement about the exercises.
 */

// The label is shared with "Cuentas y accesos", which is where it is set; what belongs to
// this screen is the MARK on an account nobody classified — here it decides which wording
// that person will be asked, so it is something to act on before handing anything over.
function Profile({ value }: { value: EvaluatorProfile | null }) {
  const { t } = useT();
  return (
    <span className={cn("text-small", value ? "text-muted-foreground" : "text-attention")}>
      {profileLabel(value, t).toLowerCase()}
    </span>
  );
}

/* 1 · WHO ---------------------------------------------------------------------------- */

function PersonStep({
  accounts,
  chosen,
  onChoose,
}: {
  accounts: AssignableAccount[];
  chosen: AssignableAccount | null;
  onChoose: (account: AssignableAccount | null) => void;
}) {
  const { t } = useT();
  const [query, setQuery] = useState("");

  // Username AND display name, folded on both sides: the administrator handing sets out
  // knows people by the name they are called, and the row is keyed by the one they log in
  // with. `lib/text.fold` is the app's single accent rule, shared with the guide's search.
  const shown = useMemo(() => {
    const needle = fold(query.trim());
    if (!needle) return accounts;
    return accounts.filter(
      (account) =>
        fold(account.username).includes(needle) || fold(account.name).includes(needle),
    );
  }, [accounts, query]);

  if (chosen) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body font-medium">{chosen.username}</span>
        <Profile value={chosen.evaluator_profile} />
        <Button variant="ghost" size="sm" onClick={() => onChoose(null)}>
          {t("sets.change")}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="relative w-full sm:w-64">
        <Search
          aria-hidden
          className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground"
        />
        <Input
          aria-label={t("sets.searchAccounts")}
          placeholder={t("sets.searchAccounts")}
          className="pl-9"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {shown.length === 0 ? (
        <p className="text-small text-muted-foreground">
          {t("sets.noAccountMatches", { query: query.trim() })}
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {shown.map((account) => (
            <button
              key={account.id}
              type="button"
              onClick={() => onChoose(account)}
              className="border border-border px-3 py-2 text-left transition-colors hover:bg-accent/40"
            >
              <span className="block text-body font-medium">{account.username}</span>
              <span className="block">
                <Profile value={account.evaluator_profile} />
                <span className="text-small text-muted-foreground">
                  {" "}
                  · {account.workspaces.length} workspace
                  {account.workspaces.length === 1 ? "" : "s"}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* 2 · WHERE -------------------------------------------------------------------------- */

function WorkspaceStep({
  account,
  chosen,
  onChoose,
}: {
  account: AssignableAccount;
  chosen: string | null;
  onChoose: (slug: string | null) => void;
}) {
  const { t } = useT();
  if (account.workspaces.length === 0) {
    return (
      <p className="text-small text-attention">
        {t("sets.noWorkspaces", { username: account.username })}
      </p>
    );
  }

  if (chosen) {
    const found = account.workspaces.find((entry) => entry.slug === chosen);
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body font-medium">{found?.name ?? chosen}</span>
        <span className="font-mono text-small text-muted-foreground">{chosen}</span>
        <Button variant="ghost" size="sm" onClick={() => onChoose(null)}>
          {t("sets.change")}
        </Button>
      </div>
    );
  }

  // Only the instances this person can actually open: the rest would 404 in their queue.
  //
  // An instance whose chain is not approved is drawn, and drawn UNSELECTABLE with the
  // stages it is waiting on underneath. Hiding it would be the worse of the three options
  // on offer: "it does not appear" is indistinguishable from "they have no access", and the
  // do about it — approve the profile, the graph, the bank — is exactly what the row would
  // have said. It carries no colour: `--attention` is the screen's scarcest ink and means
  // "act here", which an option that cannot be chosen is not.
  return (
    <div className="flex flex-wrap gap-2">
      {account.workspaces.map((entry) => (
        <WorkspaceOption key={entry.slug} entry={entry} onChoose={onChoose} />
      ))}
    </div>
  );
}

function WorkspaceOption({
  entry,
  onChoose,
}: {
  entry: AssignableWorkspace;
  onChoose: (slug: string) => void;
}) {
  const { t } = useT();
  // `false` and not falsy: an API older than this bundle sends no verdict at all, and "no
  // lo sabe" is not "no". Unknown stays selectable, and the server refuses the commission
  // with the same gate if it turns out not to be ready.
  const blocked = entry.ready === false;
  const pending = (entry.pending ?? []).map((artifact) => artifactName(artifact, t));

  return (
    <button
      type="button"
      disabled={blocked}
      onClick={() => onChoose(entry.slug)}
      className={cn(
        "max-w-full border border-border px-3 py-2 text-left transition-colors",
        blocked ? "cursor-not-allowed opacity-60" : "hover:bg-accent/40",
      )}
    >
      <span className="block text-body font-medium">{entry.name}</span>
      <span className="block font-mono text-small text-muted-foreground">{entry.slug}</span>
      {blocked ? (
        <span className="mt-1 block max-w-64 text-small text-muted-foreground">
          {pending.length > 0
            ? t("sets.notReady", { stages: pending.join(", ") })
            : t("sets.notReadyUnknown")}
        </span>
      ) : null}
    </button>
  );
}

/* 3 · WHICH -------------------------------------------------------------------------- */

function SetRow({
  set,
  accountId,
  picked,
  onPick,
}: {
  set: EvaluationSet;
  accountId: number;
  picked: boolean;
  onPick: (next: boolean) => void;
}) {
  const { t } = useT();
  const holder = set.holders.find((entry) => entry.account_id === accountId);
  const others = set.holders.filter((entry) => entry.account_id !== accountId);

  return (
    <label
      className={cn(
        "flex cursor-pointer flex-wrap items-center gap-3 border-b border-border px-4 py-3 transition-colors last:border-b-0",
        picked ? "bg-primary/5" : "hover:bg-accent/40",
        holder && "cursor-default opacity-60",
      )}
    >
      <Checkbox
        checked={picked}
        onCheckedChange={onPick}
        disabled={Boolean(holder)}
        label={t("sets.assignAria", { concepts: set.concepts.join(", ") })}
      />
      <span className="min-w-48 flex-1">
        <span className="block text-body font-medium">
          {set.concepts.join(", ") || t("sets.noConcepts")}
        </span>
        <span className="block text-small text-muted-foreground">
          {when(new Date(set.created_at * 1000).toISOString())}
          {set.think ? t("sets.withReasoning") : t("sets.withoutReasoning")}
        </span>
      </span>

      {/* Who else holds it, which is what an administrator needs in order to build overlap
          on purpose: two people on one set is the only way agreement can be computed. */}
      <span className="flex flex-wrap items-center gap-1.5">
        {others.map((entry) => (
          <span
            key={entry.session_id}
            className={cn(
              "inline-flex items-center gap-1 border px-2 py-0.5 text-small",
              entry.decided || entry.declined
                ? "border-settled text-settled"
                : "border-border text-muted-foreground",
            )}
          >
            {entry.decided ? <Check className="size-3" /> : null}
            {entry.declined ? <CircleSlash className="size-3" /> : null}
            {entry.account ?? t("sets.deletedAccount")}
          </span>
        ))}
        {others.length === 0 ? (
          <span className="text-small text-muted-foreground">{t("sets.unassigned")}</span>
        ) : null}
      </span>

      {holder ? (
        <span className="text-micro font-condensed text-settled uppercase">
          {t("sets.alreadyHas")}
        </span>
      ) : null}
    </label>
  );
}

export function AdminSetsPanel() {
  const { plural, t } = useT();
  const accounts = useAssignableAccounts();
  const [account, setAccount] = useState<AssignableAccount | null>(null);
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [composing, setComposing] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // ITS OWN NUMBER, and that is the whole point of it being here. "¿Cuántas comparaciones?"
  // is not "¿cuántos ítems produce este encargo?" — an evaluation always produces one per
  // arm — so the form hides its counter, and reading that hidden counter as this one is
  // what made a single commission arrive as two sessions.
  const [comparisons, setComparisons] = useState(1);

  const sets = useEvaluationSets(workspace);
  const assign = useAssignSet();
  const generate = useGenerateEvaluations();
  const toast = useToast();

  // The CHOSEN workspace drives the data and not the one the tab is standing in. The three
  // reads a commission is composed from take a slug, which goes into the header and into
  // the query key, so composing against one graph and running in another cannot happen. An
  // administrator reaches another instance through the bypass in `auth.deps.access_for`,
  // the same door `assign_set` uses.
  //
  // What still cannot happen is commissioning in an instance whose chain is not approved:
  // the WHERE step draws such a workspace unselectable with the stages it waits on, from
  // the same `gate_error` the endpoint enforces.
  const profileQuery = useProfile(workspace);
  const kg = useKg(workspace);
  const kgGraph = useKgGraph(workspace);

  // Now that the form reads the CHOSEN instance, a commission composed for one workspace
  // is about concepts the next one does not have: leaving it in place would send names the
  // target graph never heard of. Moving between instances therefore empties it and folds
  // the composer, which is also what says the form is about to ask a different question.
  const forgetCommission = () => {
    setForm(EMPTY_FORM);
    setComposing(false);
  };

  const free = useMemo(
    () => (sets.data?.sets ?? []).filter((set) => !set.holders.some((h) => h.account_id === account?.id)),
    [sets.data, account],
  );

  // One call per set: the endpoint hands ONE set to a list of people, and this screen is
  // the transpose — one person taking a list of sets. Failures are counted rather than
  // thrown, so a network hiccup on the fourth does not hide that three did land.
  const send = async () => {
    if (!account) return;
    const results = await Promise.all(
      picked.map((setId) =>
        assign
          .mutateAsync({ setId, accounts: [account.id] })
          .then(() => true)
          .catch(() => false),
      ),
    );
    const done = results.filter(Boolean).length;
    const failed = results.length - done;

    toast({
      title:
        done > 0 ? t("sets.assignedTo", { username: account.username }) : t("sets.assignFailed"),
      description:
        done > 0
          ? `${plural("sets.assignedCount", done)}${failed ? plural("sets.failedCount", failed) : ""}.`
          : t("sets.assignedNone"),
      tone: failed && done ? "attention" : done ? "settled" : "danger",
    });
    setPicked([]);
  };

  const launch = () => {
    if (!workspace) return;
    generate.mutate(
      toStockParams(form, workspace, comparisons),
      {
        onSuccess: ({ jobs }) => {
          toast({
            title: t("sets.commissioned", { n: jobs.length }),
            description: t("sets.commissioned.body"),
            tone: "settled",
          });
          setComposing(false);
        },
        onError: (error) =>
          toast({
            title: t("sets.commissionFailed"),
            description: (error as Error).message,
            tone: "danger",
          }),
      },
    );
  };

  if (accounts.isLoading) return <Skeleton className="h-40" />;
  // NEVER a silent `null`. Rendering nothing is what turned a 404 from a route-ordering
  // bug into a card with a heading and no body — which reads as "esta función no existe"
  // rather than "esto falló", and cost a round of "sigo sin ver la opción".
  if (accounts.isError) {
    return (
      <LoadError
        title={t("sets.accountsFailed")}
        error={accounts.error}
        onRetry={accounts.refetch}
      />
    );
  }
  if (!accounts.data) {
    return <p className="text-small text-muted-foreground">{t("sets.noAccountData")}</p>;
  }
  if (accounts.data.accounts.length === 0) {
    return (
      <p className="text-small text-muted-foreground">{t("sets.noAccounts")}</p>
    );
  }

  return (
    <div className="space-y-4">
      <Step index={1} title={t("sets.step1")} done={Boolean(account)}>
        <PersonStep
          accounts={accounts.data.accounts}
          chosen={account}
          onChoose={(next) => {
            setAccount(next);
            setWorkspace(null);
            setPicked([]);
            forgetCommission();
          }}
        />
      </Step>

      {account ? (
        <Step index={2} title={t("sets.step2")} done={Boolean(workspace)}>
          <WorkspaceStep
            account={account}
            chosen={workspace}
            onChoose={(slug) => {
              setWorkspace(slug);
              setPicked([]);
              forgetCommission();
            }}
          />
        </Step>
      ) : null}

      {account && workspace ? (
        <Step index={3} title={t("sets.step3")} done={picked.length > 0}>
          {sets.isLoading ? (
            <Skeleton className="h-24" />
          ) : (
            <div className="space-y-3">
              {free.length === 0 && (sets.data?.sets.length ?? 0) === 0 ? (
                <p className="text-small text-muted-foreground">{t("sets.noneYet")}</p>
              ) : (
                <div className="border border-border">
                  {(sets.data?.sets ?? []).map((set) => (
                    <SetRow
                      key={set.set_id}
                      set={set}
                      accountId={account.id}
                      picked={picked.includes(set.set_id)}
                      onPick={(next) =>
                        setPicked((current) =>
                          next
                            ? [...current, set.set_id]
                            : current.filter((id) => id !== set.set_id),
                        )
                      }
                    />
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  disabled={picked.length === 0 || assign.isPending}
                  onClick={send}
                >
                  {assign.isPending ? <Spinner /> : <Send />}
                  {t("sets.assignTo", {
                    n: picked.length || "",
                    username: account.username,
                  })}
                </Button>
                <Button variant="outline" onClick={() => setComposing((value) => !value)}>
                  <Plus />
                  {t("sets.commissionMore")}
                </Button>
                {picked.length > 0 ? (
                  <p className="text-small text-muted-foreground">{t("sets.sameExercises")}</p>
                ) : null}
              </div>

              {composing ? (
                <div className="animate-fade-in space-y-3 border border-border bg-muted/30 p-3">
                  <p className="flex items-start gap-2 text-small text-muted-foreground">
                    <Sparkles className="mt-0.5 size-3.5 shrink-0" />
                    {t("sets.composeHint")}
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-body font-medium">{t("sets.howMany")}</span>
                    <Count value={comparisons} onChange={setComparisons} max={10} />
                    <span className="text-small text-muted-foreground">
                      {comparisons === 1
                        ? t("sets.oneSession")
                        : t("sets.manySessions", { n: comparisons })}
                    </span>
                  </div>
                  <GenerateForm
                    state={form}
                    onChange={setForm}
                    profile={profileQuery.data?.profile ?? null}
                    concepts={kg.data?.concepts ?? []}
                    graph={kgGraph.data}
                    disabled={false}
                    running={false}
                    pending={generate.isPending}
                    error={generate.isError ? (generate.error as Error).message : null}
                    blockedInstructions={null}
                    variant="evaluation"
                    workspace={workspace}
                    launchLabel={plural("sets.launchLabel", comparisons)}
                    onLaunch={launch}
                  />
                </div>
              ) : null}
            </div>
          )}
        </Step>
      ) : null}
    </div>
  );
}

/** A numbered step, because here the order genuinely is a dependency: you cannot pick a
 *  workspace before a person, nor a comparison before a workspace. */
function Step({
  index,
  title,
  done,
  children,
}: {
  index: number;
  title: string;
  done: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "flex size-6 shrink-0 items-center justify-center rounded-full text-small font-semibold nums",
            done ? "bg-primary/12 text-primary" : "bg-primary text-primary-foreground",
          )}
        >
          {done ? <Check className="size-3.5" /> : index}
        </span>
        <h3 className="text-body font-medium">{title}</h3>
      </div>
      <div className="pl-8.5">{children}</div>
    </section>
  );
}

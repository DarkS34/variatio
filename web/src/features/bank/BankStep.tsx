import { ArrowRight, Check, Circle, Eye, EyeOff, Pencil, RefreshCw, X } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { BuildProgress, JobProgress } from "@/components/BuildProgress";
import { CancelButton } from "@/components/CancelButton";
import {
  STAGE_KICKER,
  StageHeader,
  WayOn,
  continueLabel,
  useStageControl,
  type StageControl,
} from "@/components/StageGate";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm";
import { InfoHint } from "@/components/ui/hint";
import { Spinner } from "@/components/ui/misc";
import { ProfilePart, useProfileIntro } from "@/features/profile/ProfileEditor";
import { useT, type Key } from "@/lib/i18n";
import { artifactName } from "@/lib/names";
import { isLive } from "@/lib/queue";
import { rawDriftOf, slotLabelOf } from "@/lib/raw";
import { Link, useRouter } from "@/lib/router";
import { nextStepOf, stepNumberOf } from "@/lib/steps";
import type { BuildPhase, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAsksStageReview, useCanEdit } from "@/state/auth";
import {
  useEngineOffline,
  useJobPhases,
  useJobRun,
  useProfile,
  useRawMissingFor,
  useSubmitJob,
} from "@/state/queries";
import type { RunView } from "@/state/runStore";

import { BankPart } from "./BankScreen";

/**
 * STEP 3, «Banco de ejercicios»: the types of exercise and the bank, one step in two parts
 * (the user's decision, 2026-10-08).
 *
 * They were two steps only because deciding which concepts work as labels needs the types
 * closed, and that review now heads the bank's collection on the server (`jobs/chain.py`):
 * «Recoger el banco» closes the types, decides the labels, extracts and tags the exercises
 * and warms the indices, and none of it is named on its own.
 *
 * ONE PAGE, TWO PARTS, read in order: first the shape of the exercises, then the exercises
 * collected with that shape. They are told apart by space and a rule on the ground, never by
 * a box — a box around blocks would be a third level of depth (`web/DESIGN.md` §1) —, and each
 * part carries its place, its state and its own action. The types fold to one line once a
 * bank exists, since from then on they are what the bank was collected with and not the
 * next thing to do; folded is never dropped, and opening them is one press.
 *
 * ONE CORAL on the screen, on the move that is next: building the types, rebuilding them
 * when their documents changed, collecting the bank, collecting it again, or going on to
 * generate. The parts' own actions are outline buttons. Only one part may be corrected at a
 * time, because the bar that saves a correction is one.
 */
export function BankStep({
  profile,
  bank,
  graph,
}: {
  profile: StageState | undefined;
  bank: StageState | undefined;
  graph: StageState | undefined;
}) {
  const { t } = useT();
  const types = useStageControl(profile);
  const exercises = useStageControl(bank);
  const intro = useProfileIntro(profile);
  const asksReview = useAsksStageReview();
  const canEdit = useCanEdit();
  const offline = useEngineOffline();
  const rawMissing = useRawMissingFor("exemplars_bank");
  const submit = useSubmitJob();
  const confirm = useConfirm();
  const { navigate } = useRouter();
  // The links of the collection and the retagging, which writes the bank without being one.
  const reviewRun = useJobRun("review_taggability");
  const extractRun = useJobRun("build_bank");
  const indexRun = useJobRun("index");
  const tagRun = useJobRun("tag");
  const reviewPhases = useJobPhases("review_taggability");
  // Opened by hand while folded, for reading. Nothing remembers it past the visit.
  const [showTypes, setShowTypes] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  if (!profile || !bank) {
    return (
      <div className="flex items-center gap-2 text-body text-muted-foreground">
        <Spinner /> {t("stage.loading")}
      </div>
    );
  }

  // The links of THIS collection: what the latest review queued behind it. An extraction or
  // an index from before it belongs to an older collection, and would read as done here.
  const since = reviewRun?.job?.created_at ?? 0;
  const ofThis = (run: RunView | null) => (run?.job && run.job.created_at >= since ? run : null);
  const links: Links = { review: reviewRun, extract: ofThis(extractRun), index: ofThis(indexRun) };
  const chainLive = [links.review, links.extract, links.index].some((run) => isLive(run?.job));
  // The pipeline marks the bank as building from the review on; a retagging marks it too and
  // is not a collection — it patches the bank in place, under the bank's own part.
  const collecting = chainLive || (bank.status === "building" && !isLive(tagRun?.job));
  const collected = bank.status !== "missing" && !collecting;
  const typesBuilt = profile.status !== "missing" && profile.status !== "building";
  const graphReady = graph?.status === "approved";
  const typesDrift = profile.stale_because.some((cause) => rawDriftOf(cause) !== null);
  const bankDrift = bank.stale_because.some((cause) => rawDriftOf(cause) !== null);
  // A bank collected over types reopened since — an edit withdraws their approval, and
  // collecting gives it — or stale for any cause: what to do next is to collect it again.
  const recollect = collected && (profile.status !== "approved" || bank.stale_because.length > 0);
  const failedCollection =
    bank.status === "missing" &&
    [links.review, links.extract, links.index].some((run) => run?.job?.status === "failed");

  // The types fold once there is a bank, unless they are being built or corrected, read, or
  // stale for their documents — whose notice carries the one move left.
  const foldable = collected || collecting;
  const typesOpen = !typesBuilt || !foldable || types.curating || showTypes || typesDrift;
  const bankName = artifactName("exemplars_bank", t, bank.label);
  const next = nextStepOf("exemplars_bank");

  // Why «Recoger el banco» cannot be pressed, the permission first: advice about documents to
  // somebody who could not press the button after following it is no advice.
  const collectReason = !canEdit
    ? t("build.readOnly")
    : !graphReady
      ? t("bank.step.needsSyllabus")
      : rawMissing
        ? t("build.rawMissing", { slot: slotLabelOf(rawMissing, t)! })
        : bank.transcribing_slot
          ? t("build.transcribing", { slot: slotLabelOf(bank.transcribing_slot, t)! })
          : offline
            ? offline
            : types.blocked;
  const finishReason = !graphReady ? t("bank.step.needsSyllabus") : exercises.blocked;
  const busy = submit.isPending || types.closing || exercises.closing;

  // Close the types — saving what is pending first —, then queue the review that heads the
  // collection. Collecting again replaces the bank, and its corrections with it: asked first.
  const collect = async () => {
    setFailed(null);
    if (collected) {
      const ok = await confirm({
        title: t("build.rebuildTitle", { stage: bankName }),
        body: t("build.rebuildBody", { slot: slotLabelOf("exemplars", t)! }),
        confirmLabel: t("bank.step.recollect"),
      });
      if (!ok) return;
    }
    try {
      await types.close();
      types.setCurating(false);
      exercises.setCurating(false);
      await submit.mutateAsync({ kind: "review_taggability" });
      setShowTypes(false);
    } catch (error) {
      setFailed(t("build.failed", { error: (error as Error).message }));
    }
  };

  // Close both parts as they stand and go on to generate.
  const finish = async () => {
    setFailed(null);
    try {
      await types.close();
      await exercises.close();
    } catch {
      setFailed(t("stage.continueFailed"));
      return;
    }
    navigate(next.path);
  };

  const collectButton = (
    <Button
      variant="attention"
      size="xl"
      disabled={busy || Boolean(collectReason)}
      title={collectReason ?? t(collected ? "bank.step.recollectTip" : "bank.step.collectTip")}
      onClick={() => void collect()}
    >
      {busy ? <Spinner /> : collected ? <RefreshCw /> : null}
      {t(collected ? "bank.step.recollect" : "bank.step.collect")}
      {busy || collected ? null : <ArrowRight />}
    </Button>
  );

  // The way out beside the title, by what is next. Nothing while the types are missing or
  // being built, while the bank is being collected, or while the types' documents changed:
  // the move then is inside a part (its build button, its progress, its rebuild).
  const wayOn = ((): ReactNode => {
    if (!typesBuilt || collecting || typesDrift) return null;
    // A refusal names the move out of it: nothing here can be collected or closed while the
    // syllabus is open, so the coral goes to it.
    if (!graphReady) {
      return (
        <WayOn caption={t("bank.step.needsSyllabus")}>
          <Link to="/prepare/graph" className={cn(buttonVariants({ variant: "attention", size: "xl" }))}>
            {t("chain.goFix", { n: stepNumberOf("knowledge_graph") ?? "", label: t("nav.step.graph") })}
            <ArrowRight />
          </Link>
        </WayOn>
      );
    }
    if (types.curating || !collected) {
      return (
        <WayOn
          caption={t(types.curating ? "stage.curate.editingTitle" : "bank.step.collectCaption")}
          error={failed}
        >
          {collectButton}
          {collectReason ? <InfoHint label={t("build.whyNot")}>{collectReason}</InfoHint> : null}
        </WayOn>
      );
    }
    if (recollect) {
      return (
        <WayOn caption={t("bank.step.recollectCaption")} error={failed}>
          {/* Keeping it is a real choice where the bank can be closed as it is; with its
              documents changed it cannot, and offering it would close nothing. */}
          {bankDrift ? null : (
            <Button
              variant="outline"
              disabled={busy || Boolean(finishReason)}
              title={finishReason ?? t("bank.step.keepTip")}
              onClick={() => void finish()}
            >
              {t("bank.step.keep")}
            </Button>
          )}
          {collectButton}
        </WayOn>
      );
    }
    return (
      <WayOn
        caption={t(
          exercises.curating
            ? "stage.curate.editingTitle"
            : bank.status === "approved"
              ? "stage.curate.closedTitle"
              : "bank.step.finishCaption",
        )}
        error={failed}
      >
        <Button
          variant="attention"
          size="xl"
          disabled={busy || Boolean(finishReason)}
          title={finishReason ?? (exercises.curating ? t("stage.curate.editing") : undefined)}
          onClick={() => void finish()}
        >
          {busy ? <Spinner /> : null}
          {continueLabel(next, t)}
          {busy ? null : <ArrowRight />}
        </Button>
        {finishReason ? <InfoHint label={t("build.whyNot")}>{finishReason}</InfoHint> : null}
      </WayOn>
    );
  })();

  // Correcting one part waits for the other's correction to end: one bar saves it.
  const correct = (control: StageControl, other: StageControl, label: Key) =>
    canEdit && !control.curating ? (
      <Button
        size="sm"
        variant="outline"
        disabled={other.curating}
        title={other.curating ? t("bank.part.otherCurating") : undefined}
        onClick={() => {
          control.setCurating(true);
          setShowTypes(false);
        }}
      >
        <Pencil />
        {t(label)}
      </Button>
    ) : null;

  // One part says «Te toca ahora», the one the coral acts on. Types edited since the bank was
  // collected are not the next move — collecting again is, and it closes them —, so they say
  // what happened to them.
  const typesState: PartState =
    profile.status === "building"
      ? "building"
      : types.curating
        ? "curating"
        : profile.status === "approved"
          ? "done"
          : collected
            ? "changed"
            : "now";
  const bankState: PartState = collecting
    ? "building"
    : exercises.curating
      ? "curating"
      : bank.status === "approved"
        ? "done"
        : collected || profile.status === "approved"
          ? "now"
          : "later";

  return (
    <div>
      <StageHeader
        number={stepNumberOf("exemplars_bank")}
        title={t("nav.step.bank")}
        lead={
          <p className="max-w-[74ch] text-body text-muted-foreground">
            {t("bank.step.lead")}
            {asksReview ? ` ${t("stage.what.rated")}` : null}
          </p>
        }
        guide="bank"
        wayOn={wayOn}
      />

      <Part
        n={1}
        title={t("nav.step.profile")}
        lead={
          intro
            ? // What to do with them is said only where they are drawn: folded, it would point
              // at nothing.
              typesOpen
              ? `${intro} ${t("stage.what.profile.why")}`
              : intro
            : t("stage.what.profile")
        }
        state={typesState}
        actions={
          typesBuilt && !collecting ? (
            <>
              {foldable && showTypes && !types.curating ? (
                <Button size="sm" variant="ghost" onClick={() => setShowTypes(false)}>
                  <EyeOff />
                  {t("bank.part.types.hide")}
                </Button>
              ) : null}
              {correct(types, exercises, "bank.part.types.correct")}
            </>
          ) : null
        }
      >
        {typesOpen ? (
          <ProfilePart stage={profile} control={types} />
        ) : (
          <TypesFolded onOpen={() => setShowTypes(true)} />
        )}
      </Part>

      <Part
        n={2}
        title={bankName}
        lead={t(collected ? "stage.what.bank" : "bank.part.bank.lead")}
        state={bankState}
        dimmed={bankState === "later"}
        actions={
          collected && !recollect && graphReady
            ? correct(exercises, types, "bank.part.bank.correct")
            : null
        }
      >
        {collecting ? (
          <Collection links={links} reviewPhases={reviewPhases} />
        ) : collected ? (
          <BankPart stage={bank} control={exercises} />
        ) : (
          // A collection that stopped says where in its own block; otherwise one sentence says
          // when the bank comes.
          failedCollection ? (
            <Collection links={links} reviewPhases={reviewPhases} />
          ) : (
            <p className="text-body text-muted-foreground">
              {t(profile.status === "approved" ? "bank.part.bank.ready" : "bank.part.bank.later")}
            </p>
          )
        )}
      </Part>
    </div>
  );
}

type PartState = "done" | "now" | "later" | "building" | "curating" | "changed";

// The words are the bar's under its steps, so a part says what a step would; correcting, and
// types changed since the bank was collected, are the two states a step never shows.
const PART_STATE: Record<
  PartState,
  { key: Key; variant: "settled" | "default" | "outline"; mark: ReactNode }
> = {
  done: { key: "nav.state.done", variant: "settled", mark: <Check aria-hidden /> },
  now: { key: "nav.state.now", variant: "default", mark: null },
  later: { key: "nav.state.later", variant: "outline", mark: null },
  building: { key: "nav.state.building", variant: "default", mark: <Spinner /> },
  curating: { key: "bank.part.curating", variant: "default", mark: <Pencil aria-hidden /> },
  changed: { key: "bank.part.changed", variant: "outline", mark: <Pencil aria-hidden /> },
};

/**
 * One part of the step: a rule across the ground, its place and name, one sentence, its
 * state and its action, then its blocks.
 *
 * The division is space and a rule: 56 px from what is above, twice the distance between
 * two blocks so it never reads as one more of them. The name is the display face at a
 * block title's size — a group on the ground (`web/DESIGN.md` §3), told apart from the
 * blocks it heads by the width of its letters. A part that is not next yet is dimmed, as
 * what lies ahead is everywhere.
 */
function Part({
  n,
  title,
  lead,
  state,
  actions,
  dimmed = false,
  children,
}: {
  n: number;
  title: string;
  lead: string;
  state: PartState;
  actions?: ReactNode;
  dimmed?: boolean;
  children: ReactNode;
}) {
  const { t } = useT();
  const id = useId();
  const badge = PART_STATE[state];
  return (
    <section aria-labelledby={id} className="mt-14 space-y-4 border-t border-border pt-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between lg:gap-10">
        <div className="min-w-0 space-y-1">
          <p className={STAGE_KICKER}>{t("bank.part", { n, total: 2 })}</p>
          <h2 id={id} className="font-display font-expanded text-heading">
            {title}
          </h2>
          <p className="max-w-[74ch] text-small text-muted-foreground">{lead}</p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
          <Badge variant={badge.variant} mark={badge.mark}>
            {t(badge.key)}
          </Badge>
          {actions}
        </div>
      </div>
      <div className={cn(dimmed && "opacity-60")}>{children}</div>
    </section>
  );
}

/**
 * The types of exercise folded to one line: how many, and how many fields between them.
 *
 * Counted off the file, never a draft: folded, nothing is being edited.
 */
function TypesFolded({ onOpen }: { onOpen: () => void }) {
  const { t, plural } = useT();
  const query = useProfile();
  const profile = query.data?.exists ? query.data.profile : null;
  const kinds = profile ? Object.values(profile.item_types) : [];
  const fields = kinds.reduce((sum, spec) => sum + Object.keys(spec.fields ?? {}).length, 0);
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-5">
        <p className="text-body">
          {profile
            ? `${plural("bank.part.types.count", kinds.length)} · ${plural("bank.part.fields.count", fields)}`
            : t("stage.loading")}
        </p>
        <Button size="sm" variant="ghost" onClick={onOpen}>
          <Eye />
          {t("bank.part.types.show")}
        </Button>
      </CardContent>
    </Card>
  );
}

interface Links {
  review: RunView | null;
  extract: RunView | null;
  index: RunView | null;
}

/**
 * The collection of the bank, link by link, and the progress of the one running.
 *
 * Three rows in the order they run: the labels, the extraction with its tagging, the index.
 * A review the server skipped — nothing it reads changed — is done at once and says so. Under
 * the rows, the running link's own progress card (the review's and the extraction's have a
 * phase plan); a link waiting its turn draws none, since a bar over a job that has not
 * started says work is happening that is not.
 */
function Collection({ links, reviewPhases }: { links: Links; reviewPhases: BuildPhase[] }) {
  const { t } = useT();
  const stopped = ![links.review, links.extract, links.index].some((run) => isLive(run?.job));
  // Named as every screen names the job — the panel's queue, the progress card under these
  // rows —, so one job carries one name.
  const rows: { key: keyof Links; label: Key }[] = [
    { key: "review", label: "job.review_taggability.label" },
    { key: "extract", label: "job.build_bank.label" },
    { key: "index", label: "job.index.label" },
  ];
  const running = rows.find((row) => links[row.key]?.job?.status === "running")?.key ?? null;
  const live = rows.map((row) => links[row.key]).filter((run) => isLive(run?.job));
  return (
    <div className="space-y-7">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>{t(stopped ? "bank.chain.stoppedTitle" : "bank.chain.title")}</CardTitle>
            {/* The extraction's card carries its own stop: one stop per job on screen. */}
            {running !== "extract" && live.length > 0 ? <CancelButton run={live} /> : null}
          </div>
          <CardDescription>
            {t(stopped ? "bank.chain.stoppedLead" : "bank.chain.lead")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="rows rows-tight">
            {rows.map((row) => (
              <CollectionRow
                key={row.key}
                run={links[row.key]}
                label={t(row.label)}
                review={row.key === "review"}
              />
            ))}
          </ol>
        </CardContent>
      </Card>
      {running === "review" ? (
        <JobProgress
          run={links.review}
          phases={reviewPhases}
          compact
          waiting={t("bank.chain.taggabilityWaiting")}
        />
      ) : running === "extract" ? (
        <BuildProgress artifact="exemplars_bank" />
      ) : running === "index" ? (
        <JobProgress run={links.index} phases={[]} compact />
      ) : null}
    </div>
  );
}

/**
 * One link of the collection: a mark, its name, and its state in a word — the bar's words,
 * plus the review's own when the server skipped it.
 */
function CollectionRow({
  run,
  label,
  review,
}: {
  run: RunView | null;
  label: string;
  review: boolean;
}) {
  const { t } = useT();
  const status = run?.job?.status;
  const skipped = review && status === "succeeded" && Boolean(run?.job?.result?.skipped);
  const { mark, word, tone } = rowState(status, skipped, t);
  return (
    <li className="flex items-start gap-3">
      <span className="mt-0.5 flex size-4 shrink-0 items-center justify-center">{mark}</span>
      <div className="min-w-0 flex-1">
        <p className={cn("text-body", !status && "text-muted-foreground")}>{label}</p>
        {status === "failed" && run?.job?.error ? (
          <p className="text-small text-destructive">{run.job.error}</p>
        ) : null}
      </div>
      <span className={cn("shrink-0 text-small", tone)}>{word}</span>
    </li>
  );
}

/** How a link of the collection reads in its row, by the state of its job. */
function rowState(
  status: string | undefined,
  skipped: boolean,
  t: (key: Key) => string,
): { mark: ReactNode; word: string; tone: string } {
  switch (status) {
    case "succeeded":
      return {
        mark: <Check aria-hidden className="size-4 text-settled" />,
        word: t(skipped ? "bank.chain.skipped" : "nav.state.done"),
        tone: "text-settled",
      };
    case "running":
      return { mark: <Spinner />, word: t("nav.state.building"), tone: "text-foreground" };
    case "queued":
      return {
        mark: <Circle aria-hidden className="size-4 text-muted-foreground" />,
        word: t("stage.queued"),
        tone: "text-muted-foreground",
      };
    case "failed":
      return {
        mark: <X aria-hidden className="size-4 text-destructive" />,
        word: t("bank.chain.failed"),
        tone: "text-destructive",
      };
    case "cancelled":
      return {
        mark: <X aria-hidden className="size-4 text-muted-foreground" />,
        word: t("bank.chain.cancelled"),
        tone: "text-muted-foreground",
      };
    default:
      return {
        mark: <Circle aria-hidden className="size-4 text-muted-foreground" />,
        word: t("nav.state.later"),
        tone: "text-muted-foreground",
      };
  }
}

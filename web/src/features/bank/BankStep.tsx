import { ArrowRight, Check, Circle, Hammer, Lock, Pencil, RefreshCw, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { BuildProgress, JobProgress } from "@/components/BuildProgress";
import { CancelButton } from "@/components/CancelButton";
import { StageHeader, WayOn, continueLabel, useStageControl } from "@/components/StageGate";
import { tabIds } from "@/components/TabStrip";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CARD_CHOICE, CARD_CHOSEN, ChoiceMark } from "@/components/ui/choice";
import { useConfirm } from "@/components/ui/confirm";
import { InfoHint } from "@/components/ui/hint";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import { ProfilePart, useProfileIntro } from "@/features/profile/ProfileEditor";
import { useT, type Key } from "@/lib/i18n";
import { artifactName, buildCall } from "@/lib/names";
import { isLive } from "@/lib/queue";
import { rawDriftOf, slotLabelOf } from "@/lib/raw";
import { Link, useRouter } from "@/lib/router";
import { nextStepOf, stepNumberOf } from "@/lib/steps";
import type { BuildPhase, StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useAsksStageReview, useCanEdit } from "@/state/auth";
import {
  useActiveWorkspace,
  useEngineOffline,
  useJobPhases,
  useJobRun,
  useRawMissingFor,
  useSubmitJob,
} from "@/state/queries";
import type { RunView } from "@/state/runStore";

import { BankPart } from "./BankScreen";
import { PARTS, readParts, type Part, type PartState } from "./parts";

/** Ties each card of the parts' block to the panel it shows (`TabStrip.tabIds`). */
const PICKER = "bank-parts";

/**
 * STEP 3, «Banco de ejercicios»: the types of exercise and the bank, one step in two parts
 * (the user's decision, 2026-10-08).
 *
 * They were two steps only because deciding which concepts work as labels needs the types
 * closed, and that review now heads the bank's collection on the server (`jobs/chain.py`):
 * «Recoger el banco» closes the types, decides the labels, extracts and tags the exercises
 * and warms the indices, and none of it is named on its own.
 *
 * TWO PARTS, ONE ON SCREEN (the user's request, the same day: the two stacked on one page
 * under a heading of the step read as a long page with two headings). A block of two cards
 * at the top chooses the part, as the engine's choice does (`PartPicker`), and says where
 * each stands; the bank's opens once the types exist, and then says it is next. Under it the
 * part on screen is headed as a step is — its place joined to the step's, «Paso 3 de 3 ·
 * Parte 1 de 2», its name, what it is, its way out —, and the other part stays mounted and
 * hidden, so a draft survives the switch.
 *
 * ONE CORAL on the screen, on the move that is next: building the types, rebuilding them
 * when their documents changed, going on to the bank, collecting it, collecting it again, or
 * going on to generate. Only one part may be corrected at a time, because the bar that saves
 * a correction is one.
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
  const workspace = useActiveWorkspace();
  // The links of the collection and the retagging, which writes the bank without being one.
  const reviewRun = useJobRun("review_taggability");
  const extractRun = useJobRun("build_bank");
  const indexRun = useJobRun("index");
  const tagRun = useJobRun("tag");
  const reviewPhases = useJobPhases("review_taggability");
  // The part chosen by hand on this visit; until somebody chooses, the one the state points
  // at. Nothing remembers it past the visit.
  const [chosen, setChosen] = useState<Part | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  // Another subject is another step: what was chosen in the last one does not carry over.
  useEffect(() => {
    setChosen(null);
    setFailed(null);
  }, [workspace]);

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
  const chain = [links.review, links.extract, links.index];
  // The pipeline marks the bank as building from the review on; a retagging marks it too and
  // is not a collection — it patches the bank in place, under the bank's own part.
  const collecting =
    chain.some((run) => isLive(run?.job)) || (bank.status === "building" && !isLive(tagRun?.job));
  const typesBuilt = profile.status !== "missing" && profile.status !== "building";
  const graphReady = graph?.status === "approved";
  const typesDrift = profile.stale_because.some((cause) => rawDriftOf(cause) !== null);
  const bankDrift = bank.stale_because.some((cause) => rawDriftOf(cause) !== null);
  const failedCollection =
    bank.status === "missing" && chain.some((run) => run?.job?.status === "failed");
  const parts = readParts({
    profile: profile.status,
    profileHash: Boolean(profile.hash),
    typesDrift,
    typesCurating: types.curating,
    typesDirty: Boolean(types.pending?.dirty),
    bank: bank.status,
    bankStale: bank.stale_because.length > 0,
    bankCurating: exercises.curating,
    collecting,
    collectionFailed: failedCollection,
    graphReady,
  });
  const { collected, recollect } = parts;
  const part: Part = parts.bankOpen ? (chosen ?? parts.opening) : "types";
  const typesName = artifactName("exemplars_profile", t, profile.label);
  const bankName = artifactName("exemplars_bank", t, bank.label);
  const next = nextStepOf("exemplars_bank");

  // Why «Recoger el banco» cannot be pressed, the permission first: advice about documents to
  // somebody who could not press the button after following it is no advice.
  const collectReason = !canEdit
    ? t("build.readOnly")
    : !graphReady
      ? t("bank.step.needsSyllabus")
      : profile.status === "building"
        ? t("bank.step.typesBuilding")
        : typesDrift
          ? t("bank.step.typesDrift")
          : rawMissing
            ? t("build.rawMissing", { slot: slotLabelOf(rawMissing, t)! })
            : bank.transcribing_slot
              ? t("build.transcribing", { slot: slotLabelOf(bank.transcribing_slot, t)! })
              : offline
                ? offline
                : types.blocked;
  // Closing the bank closes the types with it, a draft of theirs included.
  const finishReason = !graphReady
    ? t("bank.step.needsSyllabus")
    : (exercises.blocked ?? types.blocked);
  const busy = submit.isPending || types.closing || exercises.closing || leaving;

  const choose = (to: Part) => {
    setFailed(null);
    setChosen(to);
  };

  // On to the bank: write what the types' correction holds and end it. The types are
  // confirmed when the bank is collected or closed, never here, so that a bank collected with
  // other types before is still offered again (`readParts`).
  const toBank = async () => {
    setFailed(null);
    setLeaving(true);
    try {
      if (types.pending?.dirty) {
        await types.pending.save();
        types.markWrote();
      }
    } catch {
      setFailed(t("stage.curate.saveFailed"));
      return;
    } finally {
      setLeaving(false);
    }
    types.setCurating(false);
    choose("bank");
  };

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
      setChosen("bank");
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

  // A disabled control says why where a keyboard and a finger reach it too.
  const whyNot = (reason: string | null) =>
    reason ? <InfoHint label={t("build.whyNot")}>{reason}</InfoHint> : null;

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

  // A refusal names the move out of it: nothing in the bank can be collected or closed while
  // the syllabus is open, so the coral goes to it.
  const toSyllabus = (
    <Link to="/prepare/graph" className={cn(buttonVariants({ variant: "attention", size: "xl" }))}>
      {t("chain.goFix", { n: stepNumberOf("knowledge_graph") ?? "", label: t("nav.step.graph") })}
      <ArrowRight />
    </Link>
  );

  // Correcting one part waits for the other's correction to end: one bar saves it.
  const correct = (which: Part) => {
    const control = which === "types" ? types : exercises;
    const other = which === "types" ? exercises : types;
    const stage = which === "types" ? profile : bank;
    if (!canEdit || control.curating) return null;
    return (
      <Button
        variant="outline"
        disabled={other.curating}
        title={
          other.curating
            ? t("bank.part.otherCurating")
            : stage.status === "approved"
              ? t("stage.curate.closed")
              : t(which === "bank" ? "stage.curate.bodyBank" : "stage.curate.body")
        }
        onClick={() => {
          choose(which);
          control.setCurating(true);
        }}
      >
        <Pencil />
        {t("stage.curate.start")}
      </Button>
    );
  };

  // The types' way out: correct them, or go on to the bank. Nothing while they are missing or
  // being built — the build is the move —, or stale for their documents, whose notice carries
  // the rebuild.
  const typesWayOn =
    !typesBuilt || typesDrift ? null : (
      <WayOn
        caption={t(
          types.curating
            ? "stage.curate.editingTitle"
            : collecting
              ? "bank.part.types.collecting"
              : profile.status === "approved"
                ? "bank.part.closedTitle"
                : "stage.curate.title",
        )}
        error={failed}
      >
        {/* Types corrected while the bank is collected with them would be stale before it
            ends: they wait for it. */}
        {collecting ? null : correct("types")}
        <Button
          variant="attention"
          size="xl"
          disabled={busy || Boolean(types.blocked)}
          title={types.blocked ?? t("bank.part.continueTip")}
          onClick={() => void toBank()}
        >
          {busy ? <Spinner /> : null}
          {t("bank.part.continue")}
          {busy ? null : <ArrowRight />}
        </Button>
        {whyNot(types.blocked)}
      </WayOn>
    );

  // The bank's way out, by what is next. Nothing while there is no bank — the call in its
  // place is the move, or the stopped collection's —, while it is being collected, or while
  // the types' documents changed: rebuilding the types comes first.
  const bankWayOn = ((): ReactNode => {
    if (!collected || typesDrift) return null;
    if (!graphReady) return <WayOn caption={t("bank.step.needsSyllabus")}>{toSyllabus}</WayOn>;
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
          {whyNot(collectReason)}
        </WayOn>
      );
    }
    return (
      <WayOn
        caption={t(
          exercises.curating
            ? "stage.curate.editingTitle"
            : bank.status === "approved"
              ? "bank.part.closedTitle"
              : "stage.curate.title",
        )}
        error={failed}
      >
        {correct("bank")}
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
        {whyNot(finishReason)}
      </WayOn>
    );
  })();

  // What the bank's part offers while there is no bank: collecting it, or — with the
  // syllabus open, which refuses that — the way to the syllabus.
  const collectAction = (
    <>
      <span className="inline-flex flex-wrap items-center gap-2">
        {graphReady ? collectButton : toSyllabus}
        {graphReady ? whyNot(collectReason) : null}
      </span>
      {failed ? <p className="mt-2 text-small text-destructive">{failed}</p> : null}
    </>
  );
  const bankCall = buildCall("exemplars_bank");

  return (
    <div className="flex flex-col gap-7">
      <PartPicker
        part={part}
        onChoose={choose}
        cards={{
          types: { title: typesName, note: t("bank.part.types.note"), state: parts.types, locked: null },
          bank: {
            title: bankName,
            // With nothing to collect from yet, the sentence says what it waits for.
            note: !graphReady && !collected ? t("bank.step.needsSyllabus") : t("bank.part.bank.note"),
            state: parts.bank,
            locked: parts.bankOpen ? null : t("bank.part.bank.locked"),
          },
        }}
      />

      <StageHeader
        number={stepNumberOf("exemplars_bank")}
        part={{ n: PARTS.indexOf(part) + 1, total: PARTS.length }}
        title={part === "types" ? typesName : bankName}
        lead={
          <p className="max-w-[74ch] text-body text-muted-foreground">
            {part === "types"
              ? // A profile read before the stage was emptied still names its types: not without one.
                intro && profile.status !== "missing"
                ? `${intro} ${t("stage.what.profile.why")}`
                : t("stage.what.profile")
              : collected
                ? `${t("stage.what.bank")}${asksReview ? ` ${t("stage.what.rated")}` : ""}`
                : t("bank.part.bank.lead")}
          </p>
        }
        guide="bank"
        wayOn={part === "types" ? typesWayOn : bankWayOn}
      />

      <PartPanel part="types" shown={part === "types"}>
        <ProfilePart stage={profile} control={types} />
      </PartPanel>
      <PartPanel part="bank" shown={part === "bank"}>
        {collecting ? (
          <Collection links={links} reviewPhases={reviewPhases} />
        ) : collected ? (
          <BankPart stage={bank} control={exercises} />
        ) : failedCollection ? (
          // A collection that stopped says where, and offers itself again under the rows.
          <Collection links={links} reviewPhases={reviewPhases} action={collectAction} />
        ) : (
          // Nothing collected yet: the call in the middle, as every step's unbuilt stage.
          <EmptyState
            icon={<Hammer />}
            title={bankCall ? t(bankCall.title) : t("build.callTitle")}
            action={collectAction}
          >
            {bankCall ? <p>{t(bankCall.body)}</p> : null}
            <p className="mt-2">{t("build.callTakesTime")}</p>
          </EmptyState>
        )}
      </PartPanel>
    </div>
  );
}

type BadgeVariant = NonNullable<BadgeProps["variant"]>;

// The words are the bar's under its steps, in the bar's tones, so a part says what a step
// would: «Te toca ahora» in coral marks where the next move is, as it does under the step
// in the bar — a state, never a control; the screen's one coral control is its way out.
// Correcting, and types changed since the bank was collected, are the two states a step
// never shows.
const PART_STATE: Record<PartState, { key: Key; variant: BadgeVariant; mark: ReactNode }> = {
  done: { key: "nav.state.done", variant: "settled", mark: <Check aria-hidden /> },
  now: { key: "nav.state.now", variant: "attention", mark: <ArrowRight aria-hidden /> },
  later: { key: "nav.state.later", variant: "outline", mark: null },
  building: { key: "nav.state.building", variant: "default", mark: <Spinner /> },
  curating: { key: "bank.part.curating", variant: "default", mark: <Pencil aria-hidden /> },
  changed: { key: "bank.part.changed", variant: "outline", mark: <Pencil aria-hidden /> },
};

// A part that cannot be opened yet: later, with the lock as its shape.
const LOCKED: { key: Key; variant: BadgeVariant; mark: ReactNode } = {
  key: "nav.state.later",
  variant: "outline",
  mark: <Lock aria-hidden />,
};

interface PartCard {
  title: string;
  /** What the part is, in one sentence. */
  note: string;
  state: PartState;
  /** Why the part cannot be opened yet, or null. Said in place of the sentence. */
  locked: string | null;
}

/**
 * The two parts as two cards in a block at the top, the one on screen pressed in.
 *
 * The engine's choice drawn again (`features/admin/EngineChoice`, the user's request of
 * 2026-10-08): one `CARD_CHOICE` per part with the square of the choice, its name, its state
 * in the bar's words and one sentence of what it is — or, while it cannot be opened, why.
 * They work as TABS, each showing its panel, with the keys of a radio group: one stop in the
 * tab order, the arrows move between them and skip a part that cannot be opened. A tab of the
 * app is the sunk pill (`web/DESIGN.md` §7.3); these are cards because each says where its
 * part stands, which a pill has no room for.
 *
 * The types take three tenths of the line and the bank seven (the user's request, the same
 * day). Below `xl` three tenths leave the types' name and state no room on one line, so
 * there the two halve the line, and on a phone they stack.
 */
function PartPicker({
  part,
  onChoose,
  cards,
}: {
  part: Part;
  onChoose: (part: Part) => void;
  cards: Record<Part, PartCard>;
}) {
  const { t } = useT();
  const keys = useRadioGroup(PARTS, part, onChoose);
  return (
    <Card className="p-5">
      <div
        role="tablist"
        aria-label={t("bank.parts.label")}
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[3fr_7fr]"
        {...keys.group}
      >
        {PARTS.map((key) => {
          const card = cards[key];
          const chosen = key === part;
          const ids = tabIds(PICKER, key);
          const badge = card.locked ? LOCKED : PART_STATE[card.state];
          // The tab is named by its part alone; its state and its sentence describe it.
          return (
            <button
              key={key}
              {...keys.radio(key)}
              type="button"
              role="tab"
              id={ids.tab}
              aria-controls={ids.panel}
              aria-selected={chosen}
              aria-labelledby={`${ids.tab}-name`}
              aria-describedby={`${ids.tab}-state ${ids.tab}-note`}
              disabled={Boolean(card.locked)}
              onClick={() => onChoose(key)}
              className={cn(CARD_CHOICE, "flex items-start gap-3 p-3", chosen && CARD_CHOSEN)}
            >
              <ChoiceMark chosen={chosen} className="mt-1.5" />
              <span className="min-w-0 flex-1 space-y-0.5">
                <span className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                  <span id={`${ids.tab}-name`} className="font-expanded text-heading">
                    {card.title}
                  </span>
                  <Badge id={`${ids.tab}-state`} variant={badge.variant} mark={badge.mark}>
                    {t(badge.key)}
                  </Badge>
                </span>
                <span id={`${ids.tab}-note`} className="block text-small text-muted-foreground">
                  {card.locked ?? card.note}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

/**
 * One part's panel. Hidden and never unmounted while the other part is on screen: a draft of
 * the types, a page of the bank or a filter survives the switch, and closing the bank still
 * saves the types' draft (`StageControl.close`), which only a mounted editor holds.
 */
function PartPanel({ part, shown, children }: { part: Part; shown: boolean; children: ReactNode }) {
  const ids = tabIds(PICKER, part);
  return (
    <div role="tabpanel" id={ids.panel} aria-labelledby={ids.tab} hidden={!shown}>
      {children}
    </div>
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
 * started says work is happening that is not. A collection that stopped keeps its rows, and
 * `action` under them offers it again.
 */
function Collection({
  links,
  reviewPhases,
  action,
}: {
  links: Links;
  reviewPhases: BuildPhase[];
  action?: ReactNode;
}) {
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
        <CardContent className="space-y-5">
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
          {action ? <div>{action}</div> : null}
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

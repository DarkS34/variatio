import {
  ArrowRight,
  Eye,
  Hammer,
  Lock,
  Pencil,
  Save,
  TriangleAlert,
  UploadCloud,
} from "lucide-react";
import {
  createContext,
  lazy,
  Suspense,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { BuildButton } from "@/components/BuildButton";
import { BuildProgress } from "@/components/BuildProgress";
import { Button } from "@/components/ui/button";
import { GuideLink } from "@/components/GuideLink";
import type { GuideSlug } from "@/features/guide/sections";
import { Alert, EmptyState, Spinner } from "@/components/ui/misc";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { isQueued, waitOf, waitReason } from "@/lib/queue";
import { rawDriftLines, rawDriftOf, slotLabelOf } from "@/lib/raw";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { isRebuild } from "@/lib/progress";
import { STEPS, nextStepOf, stepNumberOf } from "@/lib/steps";
import {
  useArtifactRun,
  useInvalidateChain,
  useLanes,
  useRawMissingFor,
  useSplitEngine,
} from "@/state/queries";
import { useAsksStageReview } from "@/state/auth";
import { useMutation } from "@tanstack/react-query";
import { useT, withCatalogues, type Key } from "@/lib/i18n";
import { artifactName, buildCall, jobName } from "@/lib/names";

// The stage questionnaire is the evaluation's: its code reaches the browser only for an
// account it is asked of (`useAsksStageReview`), and everything it needs is behind this one
// component.
const StageReviewSlot = lazy(() =>
  withCatalogues(import("@/evaluation/StageReviewSlot")).then((m) => ({
    default: m.StageReviewSlot,
  })),
);

// What the stage IS, in two sentences and without naming a single piece of the system.
// Visible under the title and not behind a glyph: the sentence that says what a screen is
// about cannot be the one thing hidden on it.
const WHAT: Record<string, Key> = {
  exemplars_profile: "stage.what.profile",
  knowledge_graph: "stage.what.graph",
  exemplars_bank: "stage.what.bank",
};

// The stages whose description goes on to say what the questionnaire at the foot asks
// (`stage.what.rated`), when the questionnaire is asked of the account. The profile's never did: it
// is the fallback the profile's own intro replaces as soon as it loads.
const RATED_AFTER_WHAT = new Set(["knowledge_graph", "exemplars_bank"]);

// Why correcting this particular stage is worth the time. One shared argument, and the
// bank's own because the tutor hardened it there: past the bank, what is not corrected is
// what every generated exercise is copied from.
const CURATE_WHY: Record<string, Key> = {
  exemplars_bank: "stage.curate.bodyBank",
};

// Which page of the guide explains each stage. One map rather than a prop, because all
// three stage screens render through this header and none of them should have to remember.
const GUIDE: Record<string, GuideSlug> = {
  exemplars_profile: "profile",
  knowledge_graph: "graph",
  exemplars_bank: "bank",
};

/**
 * Why the screen below may not be written to right now.
 *
 * Read-only does not mean "approved": viewing and correcting are two tasks, so a stage
 * opens as a STATIC VIEW — closed or not — and one button beside the title unlocks it. What
 * closing means lives on the server: what is approved is the file's hash, and every hand
 * edit withdraws the approval by itself, so a corrected stage reads as open again.
 *
 * While viewing, a control that only corrects is HIDDEN rather than greyed: nothing is
 * wrong, it is simply not this moment's task. What does not rewrite the artifact stays
 * live in both states — the concept descriptions and the curriculum are separate files.
 */
export type StageLockReason = "reviewing" | "reading" | null;

const StageLock = createContext<StageLockReason>(null);

export function useStageLockReason() {
  return useContext(StageLock);
}

export function useStageLocked() {
  return useContext(StageLock) !== null;
}

/**
 * What a control that is disabled RIGHT NOW should say about itself.
 *
 * A key and not a sentence: four screens read it and each has its own `t`. Preferably
 * nothing reads it at all — a control that only corrects is hidden while the stage is being
 * looked at, since greying it out claims something is wrong.
 */
export function useStageLockedHint(): Key {
  return "stage.viewHint";
}

/**
 * What a screen is holding that the artifact on disk does not have yet.
 *
 * Two buttons write it and neither is the screen's own: "Guardar los cambios" in the
 * correction bar, and "Continuar", which saves FIRST and closes after. That order is
 * forced: what is approved is the file's hash, so closing over an unwritten change would
 * stamp the artifact about to be replaced and the next write would revoke the approval.
 *
 * A registration and not a prop, because the draft lives in the editor under the header
 * that draws the buttons. The mirror of `StageLock`, which travels the other way.
 */
export interface PendingEdit {
  /** Whether the screen is holding something the file does not have. */
  dirty: boolean;
  /** Why it cannot be written right now — the validator's own sentence, or null. */
  blocked: string | null;
  /** Write it. `approve` awaits this and never approves if it rejects. */
  save: () => Promise<unknown>;
  /** Drop it, back to what the file holds — what leaving the correction does once it asks. */
  discard: () => void;
}

const StagePending = createContext<((edit: PendingEdit | null) => void) | null>(null);

/**
 * The two contexts every stage screen sits in, as ONE element: the lock travels down (what
 * may be edited) and the pending edit travels up (what is not written yet).
 */
function StageScope({
  locked,
  register,
  children,
}: {
  locked: StageLockReason;
  register: (edit: PendingEdit | null) => void;
  children: ReactNode;
}) {
  return (
    <StageLock.Provider value={locked}>
      <StagePending.Provider value={register}>{children}</StagePending.Provider>
    </StageLock.Provider>
  );
}

/**
 * The static view with no way out of it: what a student reads a stage through.
 *
 * Every control that only corrects reads the lock and hides under it, exactly as while a
 * teacher looks at a stage before correcting — but nothing above lifts it: there is no
 * «Quiero corregir algo», since nothing a student could write would be accepted.
 */
export function ReadingScope({ children }: { children: ReactNode }) {
  return <StageLock.Provider value="reading">{children}</StageLock.Provider>;
}

/**
 * Offer this screen's unsaved edit to the buttons above it.
 *
 * `save` is a fresh closure over the draft on every render, so it is kept in a ref and the
 * effect re-runs only when `dirty` or `blocked` change: registering on every keystroke
 * would re-render the header for each character typed.
 */
export function useRegisterPendingEdit({ dirty, blocked, save, discard }: PendingEdit) {
  const register = useContext(StagePending);
  const latest = useRef({ save, discard });
  latest.current = { save, discard };
  useEffect(() => {
    register?.({
      dirty,
      blocked,
      save: () => latest.current.save(),
      discard: () => latest.current.discard(),
    });
    return () => register?.(null);
  }, [register, dirty, blocked]);
}

/**
 * What a stage screen holds for one visit: whether it is being corrected, what is pending
 * under it, whether this visit wrote, and the one way to close it.
 *
 * A hook of its own and not `StageGate`'s private state because the bank's step draws TWO
 * stages under one header (`features/bank/BankStep`): its way out has to save the types'
 * draft and close them before collecting the bank, and only one of the two parts may be
 * corrected at a time.
 */
export interface StageControl {
  /** Whether the stage is open for correcting: an act of this visit, never the default. */
  curating: boolean;
  setCurating: (on: boolean) => void;
  /** Whether this visit has written to the artifact — what the questionnaire records. */
  wrote: boolean;
  markWrote: () => void;
  /** What the screen under the stage holds that the file does not have yet. */
  pending: PendingEdit | null;
  register: (edit: PendingEdit | null) => void;
  /** Why the pending edit may not be written, or null. */
  blocked: string | null;
  /** Save what is pending, then close the stage — unless it is closed and nothing was written. */
  close: () => Promise<void>;
  closing: boolean;
}

export function useStageControl(stage: StageState | undefined): StageControl {
  const { t } = useT();
  const invalidate = useInvalidateChain();
  const toast = useToast();
  // Correcting is an act and not the default state. It belongs to the visit and not to the
  // artifact: "estoy corrigiendo ahora" is nothing anything on disk records.
  const [curating, setCurating] = useState(false);
  // Whether this visit has written to the artifact. A fact of the stage, and the one the
  // stage questionnaire records as "corrected before judging" (`StageReviewSlot`).
  const [wrote, setWrote] = useState(false);
  const [pending, setPending] = useState<PendingEdit | null>(null);
  const register = useCallback((edit: PendingEdit | null) => setPending(edit), []);
  // Another artifact is another stage: what was open for correcting was the one you left.
  useEffect(() => {
    setCurating(false);
    setWrote(false);
  }, [stage?.artifact]);
  const approve = useMutation({
    // Save first, approve second, and never approve if the write fails: an approval over
    // the previous file is worse than none, because it reads as done.
    mutationFn: async () => {
      if (pending?.dirty) await pending.save();
      return api.approve(stage!.artifact);
    },
    onSuccess: () => {
      invalidate();
      toast({ title: t("stage.approved"), description: stage!.label });
    },
  });
  const approved = stage?.status === "approved";
  return {
    curating,
    setCurating,
    wrote,
    markWrote: () => setWrote(true),
    pending,
    register,
    blocked: (pending?.dirty && pending.blocked) || null,
    closing: approve.isPending,
    // A closed stage with a draft in the browser is still a write: saving it withdraws the
    // approval on the server, so it has to be given again in the same breath.
    close: async () => {
      const writes = Boolean(pending?.dirty);
      if (writes || !approved) await approve.mutateAsync();
      if (writes) setWrote(true);
    },
  };
}

/**
 * A stage is visible before it is available, and says exactly why it is not.
 *
 * A disabled control with no explanation is the thing this screen exists to avoid. What the
 * stage IS belongs to the guide, linked under the title; what is wrong with it right now
 * stays on the page, because that is the part you act on.
 *
 * `headless` draws the stage without its header and way out: the bank's step is two stages,
 * each a part of it, and heads the part on screen itself (`features/bank/BankStep`). It hands
 * each part's `control` in, so the way out it draws reaches both.
 */
export function StageGate({
  stage,
  intro,
  livePreview,
  children,
  control,
  headless = false,
  staleAction,
}: {
  stage: StageState | undefined;
  /**
   * What this stage is, when the screen can say it better than a fixed sentence can.
   *
   * `WHAT` is the same paragraph whatever came out of the build, and "se han detectado tres
   * tipos de ejercicio: …" is worth more. Only the screen holds those numbers, so it passes
   * the sentence up rather than the header fetching data it has no business fetching.
   */
  intro?: ReactNode;
  /**
 * What the builder is writing NOW, under the bar. Not the artifact about to be replaced —
 * that stays hidden — but the one coming out.
 */
  livePreview?: ReactNode;
  children: ReactNode;
  /** The stage's state for this visit, when somebody above draws its way out. */
  control?: StageControl;
  /** Draw the body alone: no header, no way out. See above. */
  headless?: boolean;
  /**
   * The stale notice's action. Absent, the build button in its rebuild mode; `null`, none —
   * for a stage whose way out already offers the rebuild, so the screen keeps one coral.
   */
  staleAction?: ReactNode;
}) {
  const tr = useT();
  const { t, plural } = tr;
  const own = useStageControl(stage);
  const ctl = control ?? own;
  const { curating, setCurating, wrote, pending, register } = ctl;
  const rawMissing = useRawMissingFor(stage?.artifact);
  const busyRun = useArtifactRun(stage?.artifact);
  const lanes = useLanes();
  const split = useSplitEngine();
  const confirm = useConfirm();
  const { navigate } = useRouter();
  const asksReview = useAsksStageReview();
  // Whether the bar's "Guardar" has written once this visit: what lets it say "Cambios
  // guardados" over a clean draft instead of "todavía no has cambiado nada".
  const [savedOnce, setSavedOnce] = useState(false);
  const [saving, setSaving] = useState(false);
  useEffect(() => setSavedOnce(false), [stage?.artifact]);
  const [advanceFailed, setAdvanceFailed] = useState(false);
  const [curateFailed, setCurateFailed] = useState(false);

  if (!stage) {
    return (
      <div className="flex items-center gap-2 text-body text-muted-foreground">
        <Spinner /> {t("stage.loading")}
      </div>
    );
  }

  const blocked = Boolean(stage.blocked_reason);
  const building = stage.status === "building";
  const missing = stage.status === "missing";
  const ready = !building && !missing;
  const approved = stage.status === "approved";
  // Closed or not, the same door: "Quiero corregir algo" unlocks a closed stage too, and the
  // first write withdraws the approval on the server (see `StageLockReason`).
  const locked: StageLockReason = curating ? null : "reviewing";
  // "Building" covers a job that has not started, so a queued build is told apart here: a
  // bar over a job waiting its turn says work is happening that is not.
  const waitingJob = building && isQueued(busyRun?.job) ? busyRun!.job! : null;
  const wait = waitOf(waitingJob, lanes);
  // What the build is about to replace, which "building" hides: the hash is of the file on
  // disk and stays null through a first build, when there is nothing to replace at all.
  const hasPrevious = Boolean(stage.hash);
  // Where moving on goes, and what it is called there. Read from `STEPS` so the number on
  // the button and the screen it opens cannot drift apart.
  const next = nextStepOf(stage.artifact);

  // Moving on CLOSES the stage, or the one control the screen offers would lead to a step
  // that then refuses to build for want of an approval nobody was asked for.
  const advance = { blocked: ctl.blocked, running: ctl.closing, run: ctl.close };

  return (
    <StageScope locked={locked} register={register}>
      <div className="space-y-7">
        {headless ? null : (
        <StageHeader
          number={stepNumberOf(stage.artifact)}
          title={artifactName(stage.artifact, t, stage.label)}
          lead={
            intro ??
            (WHAT[stage.artifact] ? (
              <p className="max-w-[74ch] text-body text-muted-foreground">
                {t(WHAT[stage.artifact])}
                {asksReview && RATED_AFTER_WHAT.has(stage.artifact)
                  ? ` ${t("stage.what.rated")}`
                  : null}
              </p>
            ) : null)
          }
          guide={GUIDE[stage.artifact]}
          // Correcting is optional, and moving on asks nobody to understand the word
          // "aprobar". The build button is never here: it is the one thing to do on an
          // unbuilt stage, so it is drawn in the middle of the emptiness at a size that says
          // so. Nothing offers a rebuild over the SAME documents — a second pass gives no
          // different result and would throw the corrections away; the one rebuild offered
          // is the stale notice's, over documents the last build never read.
          //
          // Moving on CLOSES the stage, because the next step cannot be built without that.
          // Saving and closing are one operation: the pending write first, and no approval
          // at all if the write is refused.
          //
          // "Continuar" is the big coral button — it is the only control here that leads
          // anywhere. A CLOSED step offers both the same: correcting it reopens it with the
          // first saved change. What correcting changes is said where the pointer rests on
          // its button, and while correcting, what "Continuar" does with the draft.
          wayOn={
            ready && !blocked ? (
            <WayOn
              caption={t(
                curating
                  ? "stage.curate.editingTitle"
                  : approved
                    ? "stage.curate.closedTitle"
                    : "stage.curate.title",
              )}
              error={advanceFailed ? t("stage.continueFailed") : null}
            >
              {curating ? null : (
                <Button
                  variant="outline"
                  title={
                    approved
                      ? t("stage.curate.closed")
                      : t(CURATE_WHY[stage.artifact] ?? "stage.curate.body")
                  }
                  onClick={() => setCurating(true)}
                >
                  <Pencil />
                  {t("stage.curate.start")}
                </Button>
              )}
              <Button
                variant="attention"
                size="xl"
                disabled={advance.running || Boolean(advance.blocked)}
                title={advance.blocked ?? (curating ? t("stage.curate.editing") : undefined)}
                onClick={async () => {
                  setAdvanceFailed(false);
                  try {
                    await advance.run();
                  } catch {
                    setAdvanceFailed(true);
                    return;
                  }
                  navigate(next.path);
                }}
              >
                {advance.running ? <Spinner /> : null}
                {continueLabel(next, t)}
                {advance.running ? null : <ArrowRight />}
              </Button>
            </WayOn>
          ) : null
          }
        />
        )}

        {/* `attention` and not `danger`: stale is "the step above changed, close this one",
            a move to make — the same tone the badge, the status mark and a re-read document
            on `/raw` already give it. Red here said information had been lost.

            A cause about the DOCUMENTS names them — what was added, removed or rewritten
            since the build — and the notice's action is the build button in its rebuild
            mode, which draws nothing for a stage stale only because the step above moved. */}
        {stage.stale_because.length > 0 ? (
          <Alert
            tone="attention"
            title={t("stage.stale")}
            action={staleAction === undefined ? <BuildButton stage={stage} /> : staleAction}
          >
            {stage.stale_because.map((cause) => {
              const drift = rawDriftOf(cause);
              if (!drift) return <p key={cause.artifact ?? cause.label}>{cause.reason}</p>;
              return (
                <div key={`raw-${drift.slot}`}>
                  <p>{t("stage.staleRaw", { slot: slotLabelOf(drift.slot, t)! })}</p>
                  <ul className="mt-1 list-disc pl-5">
                    {rawDriftLines(drift, plural).map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                  <p>{t("stage.staleRaw.what")}</p>
                </div>
              );
            })}
          </Alert>
        ) : null}

        {blocked ? (
          <Alert tone="attention" title={t("stage.blocked")}>
            <p className="flex items-center gap-1.5">
              <Lock className="size-3.5" />
              {stage.blocked_reason}
            </p>
          </Alert>
        ) : null}

        {/* Only the notice that says something the header does not already say survives: that the
            raw material is missing, and where to upload it. The other was "Sin construir" plus a
            second build button, with the badge and the header's button a hand's width away — two
            blocks for one action. The header's button explains itself: with no corpus it is disabled
            and its tooltip says exactly that. */}
        {missing && rawMissing ? (
          <EmptyState
            icon={<UploadCloud />}
            title={t("stage.rawMissing")}
            action={
              <Link to="/raw">
                <Button variant="attention" size="xl">
                  <UploadCloud />
                  {t("stage.import")}
                </Button>
              </Link>
            }
          >
            {t("stage.rawMissingBody", {
              slot: slotLabelOf(rawMissing, t)!,
              stage: artifactName(stage.artifact, t, stage.label),
            })}
          </EmptyState>
        ) : null}

        {/* The one thing to do, in the middle of the screen. With the raw material missing
            the block above takes its place, "Importar" being the only way to make this one
            pressable: still one control per unbuilt stage. */}
        {missing && !rawMissing ? <BuildCall stage={stage} /> : null}

        {/* A stage that is not built has no content, and asking the screen for it is asking it to
            read a file that does not exist: the bank answered with a 404 and painted it as a red
            error, with the skeletons pulsing behind, while the graph and the profile simply painted
            nothing. Nothing is broken here — a step is missing — so the header, with its "Sin
            construir" badge and its button, is all there is to see.

            While rebuilding, the previous artifact disappears from the screen: what is on it would
            stop being what one is looking at as soon as the build ends, and editing it would be
            working on something about to be overwritten. Nothing is deleted — the file stays on
            disk until the builder replaces it — so cancelling brings it back as it was, which is why
            it is said here instead of left to be assumed. */}
        {building ? (
          <>
            {/* Three jobs land in the same "building" state and they are not the same thing.
                A rebuild throws the previous artifact away and cancelling brings it back
                untouched; a job that patches in place — tagging — rewrites the items one by
                one and saves after each, so "si cancelas, vuelve tal cual" was flatly false
                for it: what it had already decided stays decided. And a FIRST build has
                nothing behind it at all, so promising that "the one there now is still kept"
                was false on the one screen where it is read most: an empty stage. */}
            {waitingJob ? (
              <Alert tone="info" title={t("stage.queued")}>
                <p>
                  {t("stage.queuedBody", {
                    label: jobName(waitingJob.kind, t, waitingJob.label),
                    reason: wait ? ` ${waitReason(wait, split, tr)}` : "",
                  })}
                </p>
              </Alert>
            ) : !hasPrevious ? (
              <Alert tone="info" title={t("stage.buildingFirst")}>
                <p>{t("stage.buildingFirstBody", { label: artifactName(stage.artifact, t, stage.label) })}</p>
              </Alert>
            ) : isRebuild(busyRun?.job?.kind) ? (
              <Alert tone="info" title={t("stage.rebuilding")}>
                <p>{t("stage.rebuildingBody", { label: artifactName(stage.artifact, t, stage.label) })}</p>
              </Alert>
            ) : (
              <Alert tone="info" title={t("stage.patching")}>
                <p>{t("stage.patchingBody", { label: artifactName(stage.artifact, t, stage.label) })}</p>
              </Alert>
            )}
            {/* A bar drawn over a job that has not started is a claim that work is under
                way. It appears when the job does. */}
            {waitingJob ? null : <BuildProgress artifact={stage.artifact} />}
            {livePreview}
          </>
        ) : missing ? null : (
          /* Blocked and built at once — the step before it was reopened afterwards — reads
             exactly as open: what is there is on disk and is what gets judged. Dimming it
             would hide the questionnaire too; the notice above says what blocks it, and
             "Continuar" is simply not offered. */
          <div className="min-w-0 space-y-7">{children}</div>
        )}

        {/* The stage questionnaire, at the FOOT of the artifact: its button and the form
            that unfolds under it (`evaluation/StageReviewSlot`). Not drawn with the stage
            unbuilt, since there would be nothing to judge, nor for an account it is not
            asked of: the evaluation closed to it, or a role that cannot correct the subject
            and that the server would refuse the answers of. Its own boundary, so the screen
            never waits for it. */}
        {!missing && asksReview ? (
          <Suspense fallback={null}>
            <StageReviewSlot artifact={stage.artifact} curated={wrote} />
          </Suspense>
        ) : null}

        {/* The correction bar, pinned to the foot of the WINDOW while correcting: a
            syllabus is 131 rows, so the foot of the page is far from the row just touched.
            It carries three things and no more — the state of the changes, the way out, and
            "Guardar los cambios", drawn only where there is something to save, since the
            syllabus and the tagging write each change on the spot and a save button disabled
            for ever is a false promise. Leaving with an unsaved draft asks first: it is the
            only thing here that can lose anything. */}
        {ready && !blocked && curating ? (
          <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-inner bg-popover px-5 py-3 shadow-overlay">
            <Pencil aria-hidden className="size-4 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-body font-semibold">{t("stage.curate.bar")}</p>
              <p
                className={cn(
                  "text-small",
                  curateFailed || (pending?.dirty && pending.blocked)
                    ? "text-destructive"
                    : "text-muted-foreground",
                )}
              >
                {curateFailed
                  ? t("stage.curate.saveFailed")
                  : !pending
                    ? t("stage.curate.autosave")
                    : pending.dirty
                      ? (pending.blocked ?? t("stage.curate.unsaved"))
                      : savedOnce
                        ? t("stage.curate.saved")
                        : t("stage.curate.noChanges")}
              </p>
            </div>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                disabled={saving}
                onClick={async () => {
                  if (
                    pending?.dirty &&
                    !(await confirm({
                      title: t("stage.curate.discardConfirm"),
                      confirmLabel: t("stage.curate.discard"),
                      tone: "danger",
                    }))
                  )
                    return;
                  pending?.discard();
                  setCurateFailed(false);
                  setCurating(false);
                }}
              >
                <Eye />
                {t("stage.curate.stop")}
              </Button>
              {pending ? (
                <Button
                  variant={pending.dirty ? "attention" : "default"}
                  disabled={!pending.dirty || Boolean(pending.blocked) || saving}
                  title={pending.blocked ?? undefined}
                  onClick={async () => {
                    setCurateFailed(false);
                    setSaving(true);
                    try {
                      await pending.save();
                      ctl.markWrote();
                      setSavedOnce(true);
                    } catch {
                      setCurateFailed(true);
                    } finally {
                      setSaving(false);
                    }
                  }}
                >
                  {saving ? <Spinner /> : <Save />}
                  {t("stage.curate.save")}
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </StageScope>
  );
}

/**
 * The way out of a step, beside its title: one line of state, the controls under it, and
 * the failure if the move failed.
 *
 * Shared by the stages, the bank's step and `/raw`, which is what keeps the way out of the
 * construction's steps one shape instead of several that drift. It has no block around it: it
 * stands on the ground like the header it shares a line with, to the right from `lg` and
 * under the title below it. It never takes more than half the line: two controls too wide
 * for that go one under the other, so the explanation beside them keeps its measure.
 *
 * It hangs from the TOP of that line, so "Continuar" is at one height on every step
 * whatever the length of the explanation beside it; centred, it moved with every sentence.
 * The row wraps in reverse for the same reason: the last control — "Continuar" — keeps the
 * first line, and the one before it goes under.
 */
export function WayOn({
  caption,
  error,
  children,
}: {
  caption: ReactNode;
  error?: ReactNode | null;
  children: ReactNode;
}) {
  return (
    <div className="flex shrink-0 flex-col items-start gap-2 lg:max-w-[50%] lg:items-end">
      <p className="text-small text-muted-foreground">{caption}</p>
      <div className="flex flex-wrap-reverse items-center gap-3 lg:justify-end">{children}</div>
      {error ? (
        <p className="max-w-[44ch] text-small text-destructive lg:text-right">{error}</p>
      ) : null}
    </div>
  );
}

/**
 * What "Continuar" says: the next step's number, or — after the last — the door it opens,
 * named as the bar names it. «Ya está: crear mi primer ejercicio» said "first" on every
 * visit, the hundredth included (2026-10-08).
 */
export function continueLabel(
  next: { number: string | null },
  t: (key: Key, vars?: Record<string, string | number>) => string,
): string {
  return next.number === null ? t("nav.create") : t("stage.continue", { n: next.number });
}

export function StaleWarning({ children }: { children: ReactNode }) {
  return (
    <Alert tone="attention">
      <p className="flex items-start gap-1.5">
        <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
        <span>{children}</span>
      </p>
    </Alert>
  );
}

/**
 * What this step would build, in the middle of the empty screen.
 *
 * The sentence is the step's own (`lib/names.buildCall`): it names what does not exist yet
 * and which slot is read to make it, since the stages do not read the same one. The
 * trailing sentence about how long it takes is shared, which is why this is two keys.
 */
function BuildCall({ stage }: { stage: StageState }) {
  const { t } = useT();
  const call = buildCall(stage.artifact);
  return (
    <EmptyState
      icon={<Hammer />}
      title={call ? t(call.title) : t("build.callTitle")}
      action={<BuildButton stage={stage} />}
    >
      {call ? (
        <>
          <p>{t(call.body)}</p>
          <p className="mt-2">{t("build.callTakesTime")}</p>
        </>
      ) : (
        t("build.callBody", { label: artifactName(stage.artifact, t, stage.label) })
      )}
    </EmptyState>
  );
}

/** The line over a step's title that says where it sits. */
export const STAGE_KICKER = "text-micro text-muted-foreground";

/**
 * A step's header: where it sits in the path, its name, what it is, and its way out.
 *
 * The screens of the construction draw it, so a step cannot be headed one way here and
 * another there. The way out stands to the right from `lg` and under the title below it
 * (`WayOn`). The guide link goes UNDER the title, on a line of its own: beside it, it is one
 * more chip in a row of chips. No tag of any kind beside the title: the bar already says the
 * state under each step's name, and what a state ASKS is said by the notices below.
 *
 * A step drawn in parts (the bank's) is headed by the part on screen: its name is the title,
 * and its place joins the step's on the one line over it — «Paso 3 de 3 · Parte 1 de 2» —,
 * so the two places read as one path instead of two headings stacked.
 */
export function StageHeader({
  number,
  part,
  title,
  lead,
  guide,
  wayOn,
}: {
  /** The step's number in the bar, or null for a screen outside the path. */
  number: string | null;
  /** The part of the step on screen, for a step drawn in parts. */
  part?: { n: number; total: number };
  title: ReactNode;
  lead?: ReactNode;
  guide?: GuideSlug;
  wayOn?: ReactNode;
}) {
  const { t } = useT();
  return (
    <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between lg:gap-10">
      <header className="min-w-0 space-y-1.5">
        {number ? (
          <p className={STAGE_KICKER}>
            {t("nav.stepNumber", { n: number, total: STEPS.length })}
            {part ? ` · ${t("bank.part", part)}` : null}
          </p>
        ) : null}
        <h1 className="font-display font-expanded text-title">{title}</h1>
        {lead}
        {guide ? <GuideLink slug={guide} /> : null}
      </header>
      {wayOn}
    </div>
  );
}

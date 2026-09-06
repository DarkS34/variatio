import {
  ArrowRight,
  ChevronRight,
  ClipboardCheck,
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
import { slotLabelOf } from "@/lib/raw";
import { Link, useRouter } from "@/lib/router";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";
import { isRebuild } from "@/lib/progress";
import { nextStepOf, stepNumberOf } from "@/lib/steps";
import {
  useArtifactRun,
  useInvalidateChain,
  useLanes,
  useRawMissingFor,
  useSplitEngine,
} from "@/state/queries";
import { useMutation } from "@tanstack/react-query";
import { StageReview } from "@/evaluation/StageReview";
import { useStageReview } from "@/evaluation/queries";
import { questionCount } from "@/evaluation/types";
import { useT, type Key } from "@/lib/i18n";
import { artifactName, buildCall } from "@/lib/names";

// What the stage IS, in two sentences and without naming a single piece of the system.
// Visible under the title and not behind a glyph: the sentence that says what a screen is
// about cannot be the one thing hidden on it.
const WHAT: Record<string, Key> = {
  exemplars_profile: "stage.what.profile",
  knowledge_graph: "stage.what.graph",
  exemplars_bank: "stage.what.bank",
};

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
 * opens as a STATIC VIEW — closed or not — and one button at the foot unlocks it. What
 * closing means lives on the server: what is approved is the file's hash, and every hand
 * edit withdraws the approval by itself, so a corrected stage reads as open again.
 *
 * While viewing, a control that only corrects is HIDDEN rather than greyed: nothing is
 * wrong, it is simply not this moment's task. What does not rewrite the artifact stays
 * live in both states — the concept descriptions and the curriculum are separate files.
 */
export type StageLockReason = "reviewing" | null;

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

/** How long the questionnaire takes to unfold, and therefore when the page may scroll to it. */
const REVIEW_UNFOLD_MS = 300;

/**
 * A stage is visible before it is available, and says exactly why it is not.
 *
 * A disabled control with no explanation is the thing this screen exists to avoid. What the
 * stage IS belongs to the guide, linked under the title; what is wrong with it right now
 * stays on the page, because that is the part you act on.
 */
export function StageGate({
  stage,
  intro,
  livePreview,
  children,
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
}) {
  const tr = useT();
  const { t, plural } = tr;
  const invalidate = useInvalidateChain();
  const rawMissing = useRawMissingFor(stage?.artifact);
  const busyRun = useArtifactRun(stage?.artifact);
  const lanes = useLanes();
  const split = useSplitEngine();
  const toast = useToast();
  const confirm = useConfirm();
  const { navigate } = useRouter();
  // The questionnaire starts shut. Its button is at the FOOT of the artifact, which is the
  // only place "what you have just reviewed" is true.
  const [reviewOpen, setReviewOpen] = useState(false);
  // Correcting is an act and not the default state. It belongs to the visit and not to the
  // artifact: "estoy corrigiendo ahora" is nothing anything on disk records.
  const [curating, setCurating] = useState(false);
  const reviewPanel = useRef<HTMLDivElement>(null);
  // Whether this person corrected before judging, which is the evaluation's own contrast.
  // A WRITE counts, not merely having opened the controls, and it states what THIS visit
  // did: correcting, leaving without answering and coming back records a "no". The server
  // only ever lets the mark climb.
  const [curated, setCurated] = useState(false);
  // Whether the bar's "Guardar" has written once this visit: what lets it say "Cambios
  // guardados" over a clean draft instead of "todavía no has cambiado nada".
  const [savedOnce, setSavedOnce] = useState(false);
  const [saving, setSaving] = useState(false);
  // Another artifact is another stage: what was open for correcting was the one you left.
  useEffect(() => {
    setCurating(false);
    setCurated(false);
    setSavedOnce(false);
    setReviewOpen(false);
  }, [stage?.artifact]);
  // The WRAPPER — button and panel — is what is scrolled to, under the sticky header
  // (`scroll-mt-20`): the panel alone is 0 px tall at the instant it is asked to open, so
  // scrolling to it scrolls nowhere.
  useEffect(() => {
    if (!reviewOpen) return;
    // `scrollIntoView` does not honour the media query on its own, unlike a CSS transition.
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scroll = () =>
      reviewPanel.current?.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
    // AFTER the unfold and not at the click: the page is only as tall as its content, so a
    // scroll asked for before the panel has grown stops where the short page ends.
    if (still) {
      scroll();
      return;
    }
    const timer = window.setTimeout(scroll, REVIEW_UNFOLD_MS);
    return () => window.clearTimeout(timer);
  }, [reviewOpen]);
  const review = useStageReview(stage?.artifact);
  const answeredReview = review.data?.mine?.answered ?? false;
  // How many the form asks, from the form itself: a number written into the string promises
  // one thing and opens another as soon as an instrument changes.
  const reviewCount = review.data ? questionCount(review.data.instrument) : 0;
  // What the screen below is holding, if it holds anything. See `PendingEdit`.
  const [advanceFailed, setAdvanceFailed] = useState(false);
  const [curateFailed, setCurateFailed] = useState(false);
  const [pending, setPending] = useState<PendingEdit | null>(null);
  const register = useCallback((edit: PendingEdit | null) => setPending(edit), []);
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
  // that then refuses to build for want of an approval nobody was asked for. It reuses the
  // approve mutation rather than opening a second path to the same endpoint.
  const advance = {
    blocked: (pending?.dirty && pending.blocked) || null,
    running: approve.isPending,
    run: async () => {
      // A closed stage with a draft in the browser is still a write: saving it withdraws
      // the approval on the server, so it has to be given again in the same breath.
      const writes = Boolean(pending?.dirty);
      if (writes || !approved) await approve.mutateAsync();
      if (writes) setCurated(true);
    },
  };

  return (
    <StageScope locked={locked} register={register}>
      <div className="space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-4">
          {/* The guide link goes UNDER the title, on a line of its own: beside it, it is one
              more chip in a row of chips and the only one there not about the stage's state.
              It replaces an (i) — a paragraph behind a glyph can be neither read at length
              nor searched. */}
          <div className="min-w-0 space-y-1.5">
            {stepNumberOf(stage.artifact) ? (
              <p className="text-micro text-muted-foreground">
                {t("nav.stepNumber", { n: stepNumberOf(stage.artifact)! })}
              </p>
            ) : null}
            {/* No tag of any kind beside the title: the bar already says the state under
                each step's name, and what a state ASKS is said by the notices below. */}
            <h1 className="text-title">{artifactName(stage.artifact, t, stage.label)}</h1>
            {intro ?? (
              WHAT[stage.artifact] ? (
                <p className="max-w-[74ch] text-body text-muted-foreground">
                  {t(WHAT[stage.artifact])}
                </p>
              ) : null
            )}
            {GUIDE[stage.artifact] ? <GuideLink slug={GUIDE[stage.artifact]} /> : null}
          </div>

          {/* The header carries no control at all: the build button is the one thing to do
              on an unbuilt stage, so it is drawn in the middle of the emptiness at a size
              that says so, and correcting is one button at the foot. Nothing offers a
              rebuild — a second pass over the same documents gives no different result and
              would throw the corrections away. */}
        </header>

        {/* `attention` and not `danger`: stale is "the step above changed, close this one",
            a move to make — the same tone the badge, the status mark and a re-read document
            on `/raw` already give it. Red here said information had been lost. */}
        {stage.stale_because.length > 0 ? (
          <Alert tone="attention" title={t("stage.stale")}>
            {stage.stale_because.map((cause) => (
              <p key={cause.artifact}>{cause.reason}</p>
            ))}
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
              stage: artifactName(stage.artifact, t, stage.label).toLowerCase(),
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
                    label: waitingJob.label,
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
          <div className="min-w-0 space-y-5">{children}</div>
        )}

        {/* The button that opens the questionnaire, at the FOOT and never on entering:
            "questions about what you have just reviewed" over something nobody has looked at
            yet is a promise the screen cannot keep.

            This is where `--evaluation` is spent — the same token the navbar's "Comparar"
            pill carries. Filled while unanswered and quiet once answered, which is the only
            difference that matters. Not drawn with the stage unbuilt, since there would be
            nothing to judge, but DRAWN with the stage blocked: a built step whose
            predecessor was reopened still has something to judge, and the questionnaire is
            what is being measured.

            It unfolds directly under its button, as an accordion and at the button's own
            width. The reading order of a stage is view → verdict → correction, top to
            bottom, so a panel opening at the other end of the screen breaks it.

            It is always mounted and merely clipped: unmounting it would throw away whatever
            the person has typed into the box every time they close it. Button and panel are
            ONE block, or the container's `space-y` opens a gap under the button while the
            panel is shut. */}
        {!missing ? (
          <div ref={reviewPanel} className="scroll-mt-20">
            {review.data?.built ? (
          <button
            type="button"
            onClick={() => setReviewOpen((was) => !was)}
            aria-expanded={reviewOpen}
            className={cn(
              "group flex w-full items-center gap-3 border px-4 py-3.5 text-left transition-colors",
              answeredReview
                ? "border-[color-mix(in_oklch,var(--evaluation)_35%,transparent)] bg-[color-mix(in_oklab,var(--evaluation)_7%,var(--card))] text-foreground hover:bg-[color-mix(in_oklab,var(--evaluation)_12%,var(--card))]"
                : "border-evaluation bg-evaluation text-evaluation-foreground hover:bg-[color-mix(in_oklab,var(--evaluation)_88%,var(--evaluation-foreground))]",
            )}
          >
            <ClipboardCheck aria-hidden className="size-5 shrink-0" />
            <span className="min-w-0 flex-1">
              <span className="block text-heading font-semibold">{t("stageReview.openTitle")}</span>
              <span
                className={cn(
                  "block text-small",
                  answeredReview ? "text-muted-foreground" : "opacity-85",
                )}
              >
                {answeredReview
                  ? t("stageReview.openAnswered")
                  : plural("stageReview.openPending", reviewCount)}
              </span>
            </span>
            <ChevronRight
              aria-hidden
              className={cn(
                "size-5 shrink-0 transition-transform duration-300",
                reviewOpen && "rotate-90",
              )}
            />
          </button>
            ) : null}
            <div
              // `inert` and not only `aria-hidden`: clipped to zero height the panel is
              // still in the tab order, so tabbing off the button walked into a form nobody
              // can see. React 19 forwards it as the real attribute, which takes the
              // subtree out of focus AND out of the accessibility tree, and unlike
              // `visibility: hidden` it does not fight the closing transition.
              inert={!reviewOpen}
              className={cn(
                "overflow-hidden transition-[max-height,opacity] duration-300 ease-out motion-reduce:transition-none",
                reviewOpen ? "max-h-[400rem] opacity-100" : "max-h-0 opacity-0",
              )}
            >
              <div
                className={cn(
                  "pt-4 transition-transform duration-300 ease-out motion-reduce:transition-none",
                  reviewOpen ? "translate-y-0" : "-translate-y-3",
                )}
              >
                <StageReview
                  artifact={stage.artifact}
                  curated={curated}
                  onClose={() => setReviewOpen(false)}
                />
              </div>
            </div>
          </div>
        ) : null}

        {/* The two ways out, together and at the foot: correcting is optional, and moving
            on asks nobody to understand the word "aprobar". The whole screen reads view →
            verdict → do you want to correct anything? → correction.

            Moving on CLOSES the stage, because the next step cannot be built without that.
            Saving and closing are one operation: the pending write first, and no approval
            at all if the write is refused.

            "Continuar" is the big blue button — it is the only control here that leads
            anywhere. A CLOSED step offers both the same: correcting it reopens it with the
            first saved change. */}
        {ready && !blocked ? (
          <ClosingSection
            title={t(
              curating
                ? "stage.curate.editingTitle"
                : approved
                  ? "stage.curate.closedTitle"
                  : "stage.curate.title",
            )}
            body={
              curating
                ? t("stage.curate.editing")
                : approved
                  ? t("stage.curate.closed")
                  : t(CURATE_WHY[stage.artifact] ?? "stage.curate.body")
            }
            error={advanceFailed ? t("stage.continueFailed") : null}
          >
            {curating ? null : (
              <Button variant="outline" onClick={() => setCurating(true)}>
                <Pencil />
                {t("stage.curate.start")}
              </Button>
            )}
            <Button
              variant="attention"
              size="xl"
              disabled={advance.running || Boolean(advance.blocked)}
              title={advance.blocked ?? undefined}
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
          </ClosingSection>
        ) : null}

        {/* The correction bar, pinned to the foot of the WINDOW while correcting: a
            syllabus is 131 rows, so the foot of the page is far from the row just touched.
            It carries three things and no more — the state of the changes, the way out, and
            "Guardar los cambios", drawn only where there is something to save, since the
            syllabus and the tagging write each change on the spot and a save button disabled
            for ever is a false promise. Leaving with an unsaved draft asks first: it is the
            only thing here that can lose anything. */}
        {ready && !blocked && curating ? (
          <div className="sticky bottom-0 z-10 flex flex-wrap items-center gap-x-4 gap-y-2 border border-border border-l-[3px] border-l-primary bg-card px-4 py-3 shadow-overlay">
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
                      setCurated(true);
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
 * The block every step ends with, and the only shape it may have: a title, one sentence,
 * the failure if the move failed, and the controls.
 *
 * Shared by the three stages and `/raw`, which is what keeps the foot of the four steps of
 * the construction one block instead of four that drift.
 */
export function ClosingSection({
  title,
  body,
  error,
  children,
}: {
  title: ReactNode;
  body: ReactNode;
  error?: ReactNode | null;
  children: ReactNode;
}) {
  return (
    <section className="border border-border bg-card p-4 sm:p-5">
      <h2 className="text-heading font-semibold">{title}</h2>
      <p className="mt-1 max-w-[74ch] text-body text-muted-foreground">{body}</p>
      {error ? <p className="mt-2 text-body text-destructive">{error}</p> : null}
      <div className="mt-4 flex flex-wrap items-center gap-3">{children}</div>
    </section>
  );
}

/** What "Continuar" says: the next step's number, or the way into the testing phase after the last. */
export function continueLabel(
  next: { number: string | null },
  t: (key: Key, vars?: Record<string, string | number>) => string,
): string {
  return next.number === null
    ? t("stage.continueGenerate")
    : t("stage.continue", { n: next.number });
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
 * and which slot is read to make it, since the four steps do not read the same one. The
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

import {
  Check,
  ChevronRight,
  CircleCheck,
  ClipboardCheck,
  Eye,
  Lock,
  LockOpen,
  Pencil,
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

import { BuildButton, type BuildLabels } from "@/components/BuildButton";
import { BuildProgress } from "@/components/BuildProgress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { GuideLink } from "@/components/GuideLink";
import type { GuideSlug } from "@/features/guide/sections";
import { Alert, EmptyState, Spinner } from "@/components/ui/misc";
import { StatusMark } from "@/components/ui/status";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { ARTIFACT_STATUS } from "@/lib/format";
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
import { StageReview } from "@/study/StageReview";
import { useStageReview } from "@/study/queries";
import { questionCount } from "@/study/types";
import { useT, type Key } from "@/lib/i18n";
import { artifactName } from "@/lib/names";

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
 * WHY THE SCREEN BELOW MAY NOT BE WRITTEN TO RIGHT NOW.
 *
 * READ-ONLY STOPPED MEANING «APPROVED» (explicit user request). A stage used to open as a
 * form from top to bottom and ask, in the same breath, for a verdict on it — so the one
 * question a person could not answer was «what have I reviewed, if I have reviewed
 * nothing?». Viewing and correcting are two tasks, so they are two moments: the stage
 * opens as a STATIC VIEW, and correcting is what unlocks it.
 *
 * The two reasons are not interchangeable and the screens have to tell them apart: out of
 * `reviewing` the way is the «Quiero corregir algo» button at the foot of the page, and
 * out of `approved` it is «Reabrir» in the header. `reviewing` also means the control is
 * better HIDDEN than greyed — there is nothing wrong, it is simply not this moment's task
 * — while `approved` is a real refusal and says so.
 *
 * What is approved is the file's hash, so editing it underneath would silently revoke the
 * approval. What does NOT rewrite the artifact stays live in both states: the concept
 * descriptions and the curriculum are separate files and do not revoke anything.
 */
export type StageLockReason = "approved" | "reviewing" | null;

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
 * A key and not a sentence, because it is read by four screens and each one has its own
 * `t`. The two locked states name different ways out — «Reabrir» in the header, «Quiero
 * corregir algo» at the foot — so one sentence for both would send half the readers to a
 * button that is not on their screen.
 *
 * Preferably nothing reads this in the `reviewing` state at all: a control that exists
 * only to correct the artifact is HIDDEN while the stage is being looked at, because
 * nothing is wrong and greying it out claims something is.
 */
// The `approved` half, for a call site that has not moved to the hook yet. Prefer the
// hook: this one is only right in one of the two states.
export const LOCKED_HINT: Key = "stage.lockedHint";

export function useStageLockedHint(): Key {
  return useStageLockReason() === "approved" ? "stage.lockedHint" : "stage.viewHint";
}

/**
 * What a screen is holding that the artifact on disk does not have yet.
 *
 * «APROBAR» GUARDA (2026-09-01, explicit user request). «Tipos de ejercicio» has no
 * «Guardar» of its own any more: one press commits the edit and closes the stage. The
 * order is forced rather than preferred — what is approved is the file's HASH, so
 * approving while a change sits in the browser would stamp the artifact that is about to
 * be replaced, and the very next write would revoke the approval just given.
 *
 * It is a REGISTRATION and not a prop because the draft lives in the editor, under the
 * header that draws the button: passing it down would mean lifting a whole artifact's
 * state into `ProfileScreen` so that one button could read one boolean off it. The mirror
 * of `StageLock`, which travels the other way through the same children.
 */
export interface PendingEdit {
  /** Whether the screen is holding something the file does not have. */
  dirty: boolean;
  /** Why it cannot be written right now — the validator's own sentence, or null. */
  blocked: string | null;
  /** Write it. `approve` awaits this and never approves if it rejects. */
  save: () => Promise<unknown>;
}

const StagePending = createContext<((edit: PendingEdit | null) => void) | null>(null);

/**
 * The two contexts every stage screen sits in, as ONE element.
 *
 * They compose here rather than nesting around the header's JSX so that adding the second
 * one did not re-indent three hundred lines of it. The lock travels down (what may be
 * edited) and the pending edit travels up (what is not written yet).
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
 * Offer this screen's unsaved edit to the «Aprobar» button above it.
 *
 * `save` is a fresh closure over the draft on every render, so it is kept in a ref and the
 * effect re-runs only when `dirty` or `blocked` actually change: registering on every
 * keystroke would re-render the header for each character typed.
 */
export function useRegisterPendingEdit({ dirty, blocked, save }: PendingEdit) {
  const register = useContext(StagePending);
  const latest = useRef(save);
  latest.current = save;
  useEffect(() => {
    register?.({ dirty, blocked, save: () => latest.current() });
    return () => register?.(null);
  }, [register, dirty, blocked]);
}

export function StageBadge({ stage }: { stage: StageState }) {
  const { t } = useT();
  // A status the table does not know comes from an API newer than the bundle, and a badge
  // showing the raw word is worth more than a crash: this is read on every stage screen.
  const meta = ARTIFACT_STATUS[stage.status];
  // The mark carries the shape, the text carries the name, and neither depends on the
  // other: this was the third of the three different drawings the same concept had.
  return (
    <Badge
      variant={meta?.tone ?? "outline"}
      mark={<StatusMark status={stage.status} blocked={Boolean(stage.blocked_reason)} />}
    >
      {meta ? t(meta.labelKey) : stage.status}
    </Badge>
  );
}

/**
 * A stage is visible before it is available, and says exactly why it is not.
 * A disabled control with no explanation is the thing this screen exists to avoid.
 *
 * What the stage *is* is the guide's (`GuideLink`, under the title): the (i) that used to
 * hold a paragraph beside the heading is gone (2026-08-31, explicit user request), and with
 * it the `description` the three screens passed in. What is wrong with the stage right now
 * stays on the page, because that is the part you have to act on.
 */
export function StageGate({
  stage,
  actions,
  intro,
  buildLabels,
  livePreview,
  children,
}: {
  stage: StageState | undefined;
  actions?: ReactNode;
  /**
   * What this stage is, when the screen can say it better than a fixed sentence can.
   *
   * `WHAT` below is the same paragraph whatever came out of the build, and «se han
   * detectado tres tipos de ejercicio: …» is worth more than any wording that cannot
   * count. Only the screen holds those numbers, so it passes the sentence up rather than
   * the header reaching down for data it has no business fetching.
   */
  intro?: ReactNode;
  buildLabels?: BuildLabels;
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
  // EL CUESTIONARIO EMPIEZA CERRADO Y SE ABRE DESDE ARRIBA (2026-09-01, explicit user
  // request). Vivía siempre desplegado en la columna derecha, que es donde sigue
  // abriéndose; lo que cambia es que ahora hay que pedirlo, y que el botón que lo pide
  // está pegado a «Reconstruir» donde se ve al entrar.
  const [reviewOpen, setReviewOpen] = useState(false);
  // CORREGIR ES UN ACTO, NO EL ESTADO POR DEFECTO. The stage opens as a static view and
  // this is what opens it for writing. It belongs to the visit and not to the artifact:
  // it is «estoy corrigiendo ahora», which nothing on disk records.
  const [curating, setCurating] = useState(false);
  const reviewPanel = useRef<HTMLDivElement>(null);
  // WHETHER THIS PERSON CORRECTED BEFORE JUDGING, which is the study's own contrast:
  // «cómo lo valoran los que curaron y cómo lo valoran los que no». It is the header that
  // knows — the verdict panel only sees its own form — and it is a WRITE that counts, not
  // merely having opened the controls.
  //
  // It states what THIS visit did, which is what the contrast asks and not quite the same
  // as what the person ever did: correcting, leaving without answering and coming back
  // records a «no». The server only ever lets the mark climb, so any verdict given after
  // a correction in the same visit settles it for good.
  const [curated, setCurated] = useState(false);
  // Another artifact is another stage: what was open for correcting was the one you left.
  useEffect(() => {
    setCurating(false);
    setCurated(false);
    setReviewOpen(false);
  }, [stage?.artifact]);
  // ASKED FOR AT THE FOOT, DRAWN BESIDE THE ARTIFACT. The two are far apart above `xl`,
  // where the panel is a right-hand column starting at the top of the content while the
  // button that opens it is below all of it — so a press could look like nothing happened.
  useEffect(() => {
    if (!reviewOpen) return;
    // `scrollIntoView` does not honour the media query on its own, unlike a CSS transition.
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    reviewPanel.current?.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "nearest" });
  }, [reviewOpen]);
  const review = useStageReview(stage?.artifact);
  const answeredReview = review.data?.mine?.answered ?? false;
  // How many the form asks, from the form itself. It was «Cinco» written into the string
  // for all three stages while the graph asks six, so the button promised one thing and
  // opened another.
  const reviewCount = review.data ? questionCount(review.data.instrument) : 0;
  // What the screen below is holding, if it holds anything. See `PendingEdit`.
  const [advanceFailed, setAdvanceFailed] = useState(false);
  const [curateFailed, setCurateFailed] = useState(false);
  const [pending, setPending] = useState<PendingEdit | null>(null);
  const register = useCallback((edit: PendingEdit | null) => setPending(edit), []);
  // The verb is kept: the button says «Aprobar», the notice says «Aprobado». Both of these
  // changed the state of the whole chain and said nothing, and invalidating a query does
  // not always change anything visible on the screen you pressed the button from.
  const approve = useMutation({
    // SAVE FIRST, AND ONLY THEN APPROVE — and never approve if the write fails, which is
    // what awaiting it buys: an approval over the previous file is worse than no approval,
    // because it reads as done.
    mutationFn: async () => {
      if (pending?.dirty) await pending.save();
      return api.approve(stage!.artifact);
    },
    onSuccess: () => {
      invalidate();
      toast({ title: t("stage.approved"), description: stage!.label });
    },
  });
  const reopen = useMutation({
    mutationFn: () => api.reopen(stage!.artifact),
    onSuccess: () => {
      invalidate();
      toast({ title: t("stage.reopened"), description: stage!.label });
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
  // Approved outranks curating: closing the stage seals a hash, and the way back to it is
  // «Reabrir» and not a button that quietly reopens what somebody signed off.
  const locked: StageLockReason = approved ? "approved" : curating ? null : "reviewing";
  // «Building» covers a job that has not started: a queued build already marks the
  // artifact, which is right — it is about to be rewritten — but a bar and «se está
  // construyendo» over a job waiting its turn says work is happening that is not.
  const waitingJob = building && isQueued(busyRun?.job) ? busyRun!.job! : null;
  const wait = waitOf(waitingJob, lanes);
  // What the build is about to replace, which «building» hides: the hash is of the file on
  // disk and stays null through a first build, when there is nothing to replace at all.
  const hasPrevious = Boolean(stage.hash);
  // Where moving on goes, and what it is called there. Read from `STEPS` so the number on
  // the button and the screen it opens cannot drift apart.
  const next = nextStepOf(stage.artifact);

  // MOVING ON CLOSES THE STAGE. The verdict panel's forward button used to navigate and
  // nothing else, so the one control the screen offers led to a step that then refused to
  // build for want of an approval nobody had been asked for. Closing is the same operation
  // «Aprobar» performs — the pending write first, and no approval at all if it is refused
  // — so it is that mutation and not a second path to the same endpoint.
  const advance = {
    closed: approved,
    blocked: (pending?.dirty && pending.blocked) || null,
    running: approve.isPending,
    run: async () => {
      const writes = Boolean(pending?.dirty) && !approved;
      if (!approved) await approve.mutateAsync();
      if (writes) setCurated(true);
    },
  };

  return (
    <StageScope locked={locked} register={register}>
      <div className="space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-4">
          {/* The guide link goes UNDER the title, on a line of its own. Beside it, it was one
              more chip in a row of chips — badge, (i), link — and the one thing there that
              is not about this stage's state read as though it were. The (i) itself left on
              2026-08-31: a link to the guide says the same thing where the whole answer is,
              instead of a paragraph nobody can search hidden behind a glyph. Under the title it is
              plainly what it is: where to go and read about this screen.

              The «autogenerado» badge is gone from all three stages. Where the file being
              read comes from is a fact about the pipeline, not about the work: it said
              nothing a person acts on, and it sat in the row that reports whether the stage
              is built, approved or stale — which is what that row is for. */}
          <div className="min-w-0 space-y-1.5">
            {stepNumberOf(stage.artifact) ? (
              <p className="text-micro text-muted-foreground">
                {t("nav.stepNumber", { n: stepNumberOf(stage.artifact)! })}
              </p>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-title">{artifactName(stage.artifact, t, stage.label)}</h1>
              <StageBadge stage={stage} />
            </div>
            {intro ?? (
              WHAT[stage.artifact] ? (
                <p className="max-w-[74ch] text-body text-muted-foreground">
                  {t(WHAT[stage.artifact])}
                </p>
              ) : null
            )}
            {GUIDE[stage.artifact] ? <GuideLink slug={GUIDE[stage.artifact]} /> : null}
          </div>

          {/* A stage that is not built offers ONE button and nothing else. What the screens hang
              from `actions` — the graph's tabs, its taggability review — are things done ON the
              artifact, and with no artifact there is nothing to do them on: they rendered anyway,
              disabled, so the first step of the chain presented itself as three controls of which only
              one could be pressed. They come back as soon as something is built. */}
          {/* `shrink-0` only once there is a second column to shrink against: below `sm`
              the header is one column and these are the whole of it, so they wrap among
              themselves instead of pushing the page sideways. */}
          {/* The controls in a row, and the lock notice UNDER that row rather than inside
              it. Inside, it was a flex item like any other: a wide one, vertically centred
              by the row, so it came to rest beside «Reconstruir» instead of under the one
              control it is about. A column around the row puts it where it reads as the
              row's own footnote, right-aligned to the button it answers. */}
          <div className="flex flex-col gap-1.5 sm:shrink-0 sm:items-end">
            <div className="flex flex-wrap items-center gap-2">
              {missing ? null : actions}
              {building ? null : <BuildButton stage={stage} labels={buildLabels} />}
              {/* NO «APROBAR» IN THE HEADER (explicit user request). «¿Y aprobar? ¿Pero qué
                  es aprobar? Es que esto no le va a quedar claro…» — it was a word nobody
                  could act on, and it sat beside the build button as though replacing an
                  artifact and signing one off were the same kind of thing. Closing the
                  stage is what moving on does now, at the foot of the page, next to the
                  offer to correct it: two exits, both named after what they do. What stays
                  here is the way BACK out of a closed stage. */}
              {ready && !blocked && approved ? (
                  <Button
                    variant="outline"
                    // ASKED FOR, LIKE «Reconstruir» ALREADY IS. This one undoes a human
                    // decision and deletes the stage's `approvals` row, and it did it on one
                    // unguarded click while the button that merely replaces an artifact
                    // confirmed. The label does not help either — «Reabrir» sounds like
                    // opening something, not like withdrawing an approval.
                    onClick={async () => {
                      if (
                        await confirm({
                          title: t("stage.reopenConfirm", { stage: stage.label }),
                          confirmLabel: t("stage.reopen"),
                        })
                      )
                        reopen.mutate();
                    }}
                    disabled={reopen.isPending}
                    title={t("stage.reopenHint")}
                  >
                    <LockOpen />
                    {t("stage.reopen")}
                  </Button>
              ) : null}
            </div>

            {ready && !blocked && approved ? (
              <p className="flex max-w-[24rem] items-start gap-1.5 text-small text-muted-foreground sm:justify-end sm:text-right">
                <Lock aria-hidden className="mt-0.5 size-3.5 shrink-0" />
                {t("stage.locked")}
              </p>
            ) : null}
          </div>
        </header>

        {stage.stale_because.length > 0 ? (
          <Alert tone="danger" title={t("stage.stale")}>
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
            raw material is missing, and where to upload it. The other was «Sin construir» plus a
            second build button, with the badge and the header's button a hand's width away — two
            blocks for one action. The header's button explains itself: with no corpus it is disabled
            and its tooltip says exactly that. */}
        {missing && rawMissing ? (
          <EmptyState
            icon={<UploadCloud />}
            title={t("stage.rawMissing")}
            action={
              // «Datos en bruto» and NOT the panel. This pointed at «/» for as long as the
              // raw material was the panel's last card; now it is a screen of its own, and
              // sending somebody to the panel to look for it is sending them to look.
              <Link to="/raw">
                <Button variant="attention">
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

        {/* A stage that is not built has no content, and asking the screen for it is asking it to
            read a file that does not exist: the bank answered with a 404 and painted it as a red
            error, with the skeletons pulsing behind, while the graph and the profile simply painted
            nothing. Nothing is broken here — a step is missing — so the header, with its «Sin
            construir» badge and its button, is all there is to see.

            While rebuilding, the previous artifact disappears from the screen: what is on it would
            stop being what one is looking at as soon as the build ends, and editing it would be
            working on something about to be overwritten. Nothing is deleted — the file stays on
            disk until the builder replaces it — so cancelling brings it back as it was, which is why
            it is said here instead of left to be assumed. */}
        {building ? (
          <>
            {/* Three jobs land in the same «building» state and they are not the same thing.
                A rebuild throws the previous artifact away and cancelling brings it back
                untouched; a job that patches in place — tagging — rewrites the items one by
                one and saves after each, so «si cancelas, vuelve tal cual» was flatly false
                for it: what it had already decided stays decided. And a FIRST build has
                nothing behind it at all, so promising that «el que hay ahora sigue guardado»
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
          /* REVISAR A LA IZQUIERDA, VALORAR A LA DERECHA. Una sola tarea partida en dos
             mitades que se miran: el cuestionario pregunta por lo que está al lado, y
             cobrarlo en otra pantalla sería preguntar por un recuerdo.

             Una sola columna por debajo de `xl`, y no de `lg`: a 1024 las dos mitades
             quedan en 560 y 400, y el listado de conceptos del temario no cabe en 560 sin
             partir cada fila. Debajo de ese ancho el formulario baja entero, que es lo que
             ya hace la barra con su propia franja.

             Bloqueada no: con la etapa bloqueada por sus upstreams no hay nada construido
             que juzgar, y el formulario lo diría él mismo — pero atenuado junto al resto
             sería un control apagado sin explicación, que es justo lo que esta pantalla
             existe para no hacer. */
          /* UNA FILA, NO UNA REJILLA, porque lo que se anima es un ANCHO y una rejilla de
             `fr` no interpola de forma fiable entre «hay columna» y «no la hay». El panel
             es una columna de ancho fijo en `xl` que va de 0 a 26rem, con `overflow-hidden`
             recortándolo mientras viaja, y su contenido entra desplazado desde la derecha:
             eso es «que se abra de lado». Por debajo de `xl` no hay dos columnas que valgan,
             así que lo que se abre es el alto.

             Se monta siempre y sólo se recorta: desmontarlo perdería lo que la persona
             lleve escrito en el cuadro de texto cada vez que cierre el cajón. */
          <div className="flex flex-col items-start gap-5 xl:flex-row">
            <div
              className={cn(
                "min-w-0 flex-1 space-y-5",
                blocked && "pointer-events-none select-none opacity-45",
              )}
            >
              {children}
            </div>
            {blocked ? null : (
              <div
                ref={reviewPanel}
                // `inert` and not only `aria-hidden`: clipped to zero height the panel is
                // still in the tab order, so tabbing off the last control of the screen
                // walked into a form nobody can see. React 19 forwards it as the real
                // attribute, which takes the subtree out of focus AND out of the
                // accessibility tree, and unlike `visibility: hidden` it does not fight
                // the closing transition.
                inert={!reviewOpen}
                className={cn(
                  "w-full shrink-0 overflow-hidden",
                  "transition-[max-height,width,opacity] duration-300 ease-out motion-reduce:transition-none",
                  reviewOpen
                    ? "max-h-[400rem] opacity-100 xl:w-[26rem]"
                    : "max-h-0 opacity-0 xl:w-0",
                )}
              >
                <div
                  className={cn(
                    "transition-transform duration-300 ease-out motion-reduce:transition-none",
                    reviewOpen ? "translate-x-0" : "translate-x-8",
                  )}
                >
                  <StageReview
                    artifact={stage.artifact}
                    curated={curated}
                    onClose={() => setReviewOpen(false)}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* EL BOTÓN QUE ABRE LA VALORACIÓN, AL FINAL Y NO AL ENTRAR (explicit user
            request, revoking the placement of 2026-09-01). Arriba decía «preguntas sobre
            lo que acabas de revisar» encima de algo que todavía no se había mirado, y la
            objeción fue literal: «le doy aquí, pero ¿qué he revisado, si yo no he revisado
            nada?». Debajo del artefacto la frase es cierta.

            Aquí es donde se gasta `--study`: es el token de la evaluación en toda la
            aplicación — la píldora «Comparar» del navbar se dibuja en él. Relleno mientras
            no se ha contestado y sobrio en cuanto se contesta, que es la única diferencia
            que importa. No se dibuja con la etapa sin construir ni bloqueada — no habría
            nada que juzgar. */}
        {!missing && !blocked && review.data?.built ? (
          <button
            type="button"
            onClick={() => setReviewOpen((was) => !was)}
            aria-expanded={reviewOpen}
            className={cn(
              "group flex w-full items-center gap-3 border px-4 py-3.5 text-left transition-colors",
              answeredReview
                ? "border-[color-mix(in_oklch,var(--study)_35%,transparent)] bg-[color-mix(in_oklab,var(--study)_7%,var(--card))] text-foreground hover:bg-[color-mix(in_oklab,var(--study)_12%,var(--card))]"
                : "border-study bg-study text-study-foreground hover:bg-[color-mix(in_oklab,var(--study)_88%,var(--study-foreground))]",
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

        {/* LAS DOS SALIDAS, JUNTAS Y AL FINAL (explicit user request). «Pulsa aquí para
            curar, o pulsa para pasar al siguiente paso sin curar»: corregir es opcional y
            avanzar no exige entender la palabra «aprobar», que es lo que este bloque
            sustituye. El orden de toda la pantalla queda vista → valoración → ¿quieres
            corregir algo? → corrección.

            Avanzar CIERRA la etapa, porque el paso siguiente no se puede construir sin eso
            y quedarse a medias era el callejón que traía a la gente de vuelta. Guardar y
            cerrar son la misma operación de siempre: primero la escritura pendiente, y
            ninguna aprobación si la escritura se rechaza. */}
        {ready && !blocked ? (
          <section className="border border-border bg-card p-4 sm:p-5">
            <h2 className="text-heading font-semibold">
              {t(approved ? "stage.curate.closedTitle" : "stage.curate.title")}
            </h2>
            <p className="mt-1 max-w-[74ch] text-body text-muted-foreground">
              {approved
                ? t("stage.curate.closed")
                : curating
                  ? t("stage.curate.editing")
                  : t(CURATE_WHY[stage.artifact] ?? "stage.curate.body")}
            </p>
            {advanceFailed ? (
              <p className="mt-2 text-body text-destructive">{t("stage.continueFailed")}</p>
            ) : null}
            {curateFailed ? (
              <p className="mt-2 text-body text-destructive">{t("stage.curate.saveFailed")}</p>
            ) : null}
            <div className="mt-3.5 flex flex-wrap items-center gap-2">
              {approved ? null : curating ? (
                // ONE BUTTON, TWO STATES, AND NEITHER CAN LOSE ANYTHING. While there is
                // something unwritten it saves; once there is not, it is the way back to
                // the view. Offering «dejar de corregir» over an unsaved draft would be
                // offering to throw it away, and the screen has no «Guardar» of its own.
                <Button
                  variant="outline"
                  disabled={approve.isPending || Boolean(pending?.dirty && pending.blocked)}
                  title={(pending?.dirty && pending.blocked) || undefined}
                  onClick={async () => {
                    if (!pending?.dirty) {
                      setCurating(false);
                      return;
                    }
                    setCurateFailed(false);
                    // A refused write rejects, and an unhandled rejection here would leave
                    // the button looking as though it had worked.
                    try {
                      await pending.save();
                    } catch {
                      setCurateFailed(true);
                      return;
                    }
                    setCurated(true);
                  }}
                >
                  {pending?.dirty ? <Check /> : <Eye />}
                  {t(pending?.dirty ? "stage.curate.save" : "stage.curate.stop")}
                </Button>
              ) : (
                <Button variant="outline" onClick={() => setCurating(true)}>
                  <Pencil />
                  {t("stage.curate.start")}
                </Button>
              )}
              <Button
                // `--attention` goes to the move that is left: while the verdict is
                // unanswered the loud thing on the screen is the button above, and this one
                // waits its turn. One `--attention` per screen.
                variant={answeredReview ? "attention" : "default"}
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
                {advance.running ? <Spinner /> : <CircleCheck />}
                {next.number === null
                  ? t("stage.continueGenerate")
                  : t("stage.continue", { n: next.number })}
              </Button>
            </div>
          </section>
        ) : null}
      </div>
    </StageScope>
  );
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

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
import { StageReview } from "@/study/StageReview";
import { useStageReview } from "@/study/queries";
import { questionCount } from "@/study/types";
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
 * WHY THE SCREEN BELOW MAY NOT BE WRITTEN TO RIGHT NOW.
 *
 * READ-ONLY STOPPED MEANING «APPROVED» (explicit user request). A stage used to open as a
 * form from top to bottom and ask, in the same breath, for a verdict on it — so the one
 * question a person could not answer was «what have I reviewed, if I have reviewed
 * nothing?». Viewing and correcting are two tasks, so they are two moments: the stage
 * opens as a STATIC VIEW, and correcting is what unlocks it.
 *
 * ONE REASON, ONE WAY OUT (2026-09-02, explicit user request). A closed stage used to be
 * a second lock with a door of its own — «Reabrir» in the header — and having to press it
 * before being allowed to press «Quiero corregir algo» was a click nobody could explain.
 * Closed or not, the stage opens as a view and the same button at the foot unlocks it.
 * What closing still means lives on the SERVER: what is approved is the file's hash, and
 * every hand edit withdraws the approval by itself (`review.invalidate`), so a corrected
 * stage reads as open again and «Continuar» closes it once more. While viewing, a control
 * that only corrects is HIDDEN rather than greyed — nothing is wrong, it is simply not this
 * moment's task.
 *
 * What does NOT rewrite the artifact stays live in both states: the concept descriptions
 * and the curriculum are separate files and do not revoke anything.
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
 * A key and not a sentence, because it is read by four screens and each one has its own
 * `t`. Preferably nothing reads it at all: a control that exists only to correct the
 * artifact is HIDDEN while the stage is being looked at, because nothing is wrong and
 * greying it out claims something is. What survives is the one way out, which every screen
 * names the same: «Quiero corregir algo», at the foot of the page.
 */
export function useStageLockedHint(): Key {
  return "stage.viewHint";
}

/**
 * What a screen is holding that the artifact on disk does not have yet.
 *
 * TWO BUTTONS WRITE IT AND NEITHER IS THE SCREEN'S OWN: «Guardar los cambios» in the
 * correction bar pinned to the foot of the window (2026-09-02, explicit user request — a
 * save button somewhere it can be seen), and «Continuar», which saves first and closes
 * after. That order is forced rather than preferred — what is approved is the file's HASH,
 * so closing while a change sits in the browser would stamp the artifact that is about to
 * be replaced, and the very next write would revoke the approval just given.
 *
 * It is a REGISTRATION and not a prop because the draft lives in the editor, under the
 * header that draws the buttons: passing it down would mean lifting a whole artifact's
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
  /** Drop it, back to what the file holds — what «Dejar de corregir» does once it has asked. */
  discard: () => void;
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
 * A disabled control with no explanation is the thing this screen exists to avoid.
 *
 * What the stage *is* is the guide's (`GuideLink`, under the title): the (i) that used to
 * hold a paragraph beside the heading is gone (2026-08-31, explicit user request), and with
 * it the `description` the three screens passed in. What is wrong with the stage right now
 * stays on the page, because that is the part you have to act on.
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
   * `WHAT` below is the same paragraph whatever came out of the build, and «se han
   * detectado tres tipos de ejercicio: …» is worth more than any wording that cannot
   * count. Only the screen holds those numbers, so it passes the sentence up rather than
   * the header reaching down for data it has no business fetching.
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
  // EL CUESTIONARIO EMPIEZA CERRADO Y SE ABRE DESDE SU BOTÓN (2026-09-01, explicit user
  // request). Vivía siempre desplegado; lo que cambia es que ahora hay que pedirlo, y el
  // botón que lo pide está al pie del artefacto, donde «lo que acabas de revisar» es
  // cierto.
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
  // Whether the bar's own «Guardar» has written once this visit — what lets it say «Cambios
  // guardados» over a draft that is clean again, instead of «todavía no has cambiado nada».
  const [savedOnce, setSavedOnce] = useState(false);
  const [saving, setSaving] = useState(false);
  // Another artifact is another stage: what was open for correcting was the one you left.
  useEffect(() => {
    setCurating(false);
    setCurated(false);
    setSavedOnce(false);
    setReviewOpen(false);
  }, [stage?.artifact]);
  // The panel opens directly under the button that asks for it, and the button is at the
  // foot of the artifact, so what is under it is below the fold: the WRAPPER — button and
  // panel — is brought to the top of the window, under the sticky header (`scroll-mt-20`),
  // and the form unfolds beneath. Measured before: `block: "nearest"` on the panel alone
  // scrolled nothing, because the panel is 0 px tall at the instant it is asked to open.
  useEffect(() => {
    if (!reviewOpen) return;
    // `scrollIntoView` does not honour the media query on its own, unlike a CSS transition.
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scroll = () =>
      reviewPanel.current?.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
    // AFTER the unfold, not at the click: the panel grows over `REVIEW_UNFOLD_MS` and the
    // page is only as tall as its content, so a scroll asked for at the click stops where
    // the short page ends — measured, the button landed at y=630 instead of at the top.
    if (still) {
      scroll();
      return;
    }
    const timer = window.setTimeout(scroll, REVIEW_UNFOLD_MS);
    return () => window.clearTimeout(timer);
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
  // Closed or not, the same door: «Quiero corregir algo» unlocks a closed stage too, and the
  // first write withdraws the approval on the server (see `StageLockReason`).
  const locked: StageLockReason = curating ? null : "reviewing";
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
            {/* NO TAG OF ANY KIND BESIDE THE TITLE (2026-09-03, explicit user request).
                The state badge — «Aprobado», «Borrador», «Obsoleto» — is gone from the
                four steps' headers: the bar at the top already says the state under each
                step's name, and what a state ASKS of the person is said by the notices
                below (stale, blocked). A word that names a state a person cannot act on
                from here was one more chip in the row. */}
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

          {/* THE HEADER CARRIES NO CONTROL AT ALL (2026-09-02, explicit user request). The
              build button lived here, small, in the top-right corner of a screen whose whole
              body was empty — it is the one thing to do on an unbuilt stage, so it is drawn in
              the middle of that emptiness and at a size that says so. «Reabrir» lived here too
              and is gone: a closed stage is corrected through the same button as an open one,
              at the foot. And nothing offers a rebuild any more — a second pass over the same
              documents does not give a different result, so the control was a way to throw
              away corrections for nothing. */}
        </header>

        {/* `attention` and not `danger`: stale is «lo de arriba cambió, vuelve a cerrarlo»,
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

        {/* THE ONE THING TO DO, IN THE MIDDLE OF THE SCREEN (2026-09-02, explicit user
            request). With nothing built the body was blank and the button sat in the
            header's corner; the emptiness is now where it is said what building does, and
            the button is the size of the decision. With the raw material missing the block
            above takes its place, because «Importar» is the only way to make this one
            pressable — still one control per unbuilt stage. */}
        {missing && !rawMissing ? <BuildCall stage={stage} /> : null}

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
          /* Bloqueada y construida a la vez — el paso anterior se reabrió después — se lee
             igual que abierta: lo que hay está en el disco y es lo que se valora. Se
             atenuaba entera hasta el 2026-09-03, y con ella se escondía el cuestionario;
             lo que la bloquea lo dice el aviso de arriba, y «Continuar» no se ofrece. */
          <div className="min-w-0 space-y-5">{children}</div>
        )}

        {/* EL BOTÓN QUE ABRE LA VALORACIÓN, AL FINAL Y NO AL ENTRAR (explicit user
            request, revoking the placement of 2026-09-01). Arriba decía «preguntas sobre
            lo que acabas de revisar» encima de algo que todavía no se había mirado, y la
            objeción fue literal: «le doy aquí, pero ¿qué he revisado, si yo no he revisado
            nada?». Debajo del artefacto la frase es cierta.

            Aquí es donde se gasta `--study`: es el token de la evaluación en toda la
            aplicación — la píldora «Comparar» del navbar se dibuja en él. Relleno mientras
            no se ha contestado y sobrio en cuanto se contesta, que es la única diferencia
            que importa. No se dibuja con la etapa sin construir — no habría nada que
            juzgar — pero SÍ con la etapa bloqueada (2026-09-03, explicit user request:
            «los formularios tienen que aparecer en todos los constructores
            independientemente de si se ha enviado el anterior o no»): un paso ya
            construido cuyo anterior se reabrió sigue teniendo algo que valorar, y el
            cuestionario es lo que se está midiendo. */}
        {/* Y EL CUESTIONARIO SE ABRE DEBAJO DEL BOTÓN, COMO UN ACORDEÓN (2026-09-02,
            explicit user request: «que se abran de manera natural y en la posición
            correcta; ahora mismo se abren al lado y rompe todo el flow»). Fue una columna a
            la derecha que arrancaba arriba del todo, así que pulsar al pie abría algo en
            la otra punta de la pantalla y había que desplazar la página hasta ello. La
            lectura de la etapa es vista → valoración → corrección, de arriba abajo, y el
            formulario cae ahora donde está el botón que lo pide, con el ancho del botón.
            El chevrón ya giraba hacia abajo al abrirse: prometía esto.

            Se monta siempre y sólo se recorta: desmontarlo perdería lo que la persona
            lleve escrito en el cuadro de texto cada vez que cierre. Un solo bloque para el
            botón y el panel, o el `space-y` del contenedor abriría un hueco bajo el botón
            con el panel cerrado. */}
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

        {/* LAS DOS SALIDAS, JUNTAS Y AL FINAL (explicit user request). «Pulsa aquí para
            curar, o pulsa para pasar al siguiente paso sin curar»: corregir es opcional y
            avanzar no exige entender la palabra «aprobar», que es lo que este bloque
            sustituye. El orden de toda la pantalla queda vista → valoración → ¿quieres
            corregir algo? → corrección.

            Avanzar CIERRA la etapa, porque el paso siguiente no se puede construir sin eso
            y quedarse a medias era el callejón que traía a la gente de vuelta. Guardar y
            cerrar son la misma operación de siempre: primero la escritura pendiente, y
            ninguna aprobación si la escritura se rechaza.

            «CONTINUAR» ES EL BOTÓN GRANDE Y AZUL (2026-09-02, explicit user request): es el
            único movimiento que lleva a algún sitio, y era un botón de tinta del tamaño de
            «Quiero corregir algo», que no lleva a ninguno. Un paso CERRADO ofrece los dos
            igual: corregirlo lo vuelve a abrir con el primer cambio guardado. */}
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

        {/* LA BARRA DE CORRECCIÓN, PEGADA AL BORDE DE ABAJO MIENTRAS SE CORRIGE (2026-09-02,
            explicit user request: «un botón de Guardar en algún sitio vistoso»). Un temario
            tiene 131 filas y el pie de la página queda lejos de la fila que se acaba de
            tocar; una barra fija al borde inferior de la ventana está siempre a la vista,
            que es la única definición de «vistoso» que sirve. Lleva las tres cosas que hacen
            falta mientras se corrige y ninguna más: cómo están los cambios, la salida, y
            «Guardar los cambios» — solo donde hay algo que guardar, porque el temario y el
            etiquetado escriben cada cambio al momento y un «Guardar» apagado para siempre es
            una promesa falsa. Dejar de corregir con cambios sin guardar pregunta antes de
            descartarlos: es lo único aquí que puede perder algo. */}
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
 * THE BLOCK EVERY STEP ENDS WITH, and the only shape it may have.
 *
 * A title, one sentence, the failure if the move failed, and the controls — with the big
 * blue «Continuar» among them. `/raw` used to copy the markup by hand and had already
 * drifted (no failure line, no spinner); one component is what keeps the foot of the four
 * steps of the construction the same block (2026-09-02, explicit user request).
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

/** What «Continuar» says: the next step's number, or the way into the testing phase after the last. */
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
 * WHAT THIS STEP WOULD BUILD, IN THE MIDDLE OF THE EMPTY SCREEN.
 *
 * The block is the same one every unbuilt stage has opened with since 2026-09-02 — a
 * dashed frame, the hammer, the `xl` button — and what changed is the sentence: it is the
 * step's own now (`lib/names.buildCall`), so it says what does not exist yet and what is
 * read to make it instead of interpolating the step's name into one generic line. The
 * trailing sentence about how long it takes is shared by the three and is the only reason
 * this is two keys rather than one.
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

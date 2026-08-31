import { Clock, Hammer, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { isQueued, prospectNote, queuedLabel, waitOf, waitReason } from "@/lib/queue";
import { slotLabelOf } from "@/lib/raw";
import type { StageState } from "@/lib/types";
import { useCanEdit } from "@/state/auth";
import {
  useEngineOffline,
  useJobRun,
  useLanes,
  usePipeline,
  useRawMissingFor,
  useSplitEngine,
  useSubmitJob,
} from "@/state/queries";
import { useT } from "@/lib/i18n";
import { artifactName } from "@/lib/names";
import { useConfirm } from "@/components/ui/confirm";
import { InfoHint } from "@/components/ui/hint";
import { cn } from "@/lib/utils";

/** What the two halves of the action are called on a given screen, when the generic
 *  "Construir / Reconstruir" is not what that artifact's build is actually called. */
export interface BuildLabels {
  create: string;
  redo: string;
  /** Shown before a redo that would throw away work. Absent means no confirmation. */
  confirmRedo?: string;
}

/**
 * The one way to launch a build, wherever it is pressed.
 *
 * The panel and each stage screen offer the same action, so the rules for *not* offering
 * it — an unapproved upstream, an empty raw slot, no engine, this build already waiting —
 * live here once. A disabled button always says why in its tooltip; that is the whole
 * point of centralising it.
 *
 * Creating and redoing are the same job with opposite consequences — the first fills an
 * empty slot, the second discards what is in it — so they never share a label, an icon
 * or a variant. A screen may rename the pair (the bank *extracts*; it does not "build"),
 * but the distinction itself is not a screen's to drop.
 *
 * A busy engine is NOT one of those reasons and never was: the job queues behind whatever
 * is there, so what the button owes the person is how many jobs it goes behind. What
 * changed with two lanes is which jobs count. «El motor está ocupado» used to mean the one
 * GPU; now the hosted API is a second queue, and a build that needs neither the busy one
 * nor a slot behind it must not be told to wait — that claim was the defect.
 */
export function BuildButton({
  stage,
  variant,
  size = "sm",
  className,
  labels,
}: {
  stage: StageState;
  variant?: "default" | "outline" | "ghost";
  size?: "sm" | "default";
  className?: string;
  labels?: BuildLabels;
}) {
  const { t } = useT();
  const tr = useT();
  const submit = useSubmitJob();
  const pipeline = usePipeline();
  const lanes = useLanes();
  const split = useSplitEngine();
  const offline = useEngineOffline();
  const rawMissing = useRawMissingFor(stage.artifact);
  const canEdit = useCanEdit();
  const confirm = useConfirm();
  // This artifact's own build, if one is already in the queue. Once it exists the server
  // has assigned its lanes, so from here on the wait is a measurement and not a guess.
  const own = useJobRun(stage.build_job);

  const missing = stage.status === "missing";
  const waiting = isQueued(own?.job) ? own!.job! : null;
  const wait = waitOf(waiting, lanes);

  // Before the job exists nobody knows which lane it will take, so with two engines the
  // tooltip reports the machine instead of promising a wait. With one — or against an API
  // that does not split the queue — the flat count is exact and it still predicts.
  const queueNote = prospectNote(lanes, split, pipeline.data?.queue_length ?? 0, tr) ?? "";

  // The permission goes first: a viewer being told that a raw slot is empty would be
  // reading advice about a button they could not press even after fixing it.
  //
  // APPROVED CLOSES THE STAGE, AND THAT INCLUDES REBUILDING IT (2026-08-31, explicit user
  // request). The rule was already written — «while approved, the screen offers no control
  // that rewrites the artifact, and the only way back to it is Reabrir» — and the screen
  // says it out loud in the notice under this row, but the button that discards the whole
  // artifact stayed live two centimetres to its left. Measured on all three stages: banco
  // «Volver a extraer», grafo and perfil «Reconstruir», every one of them enabled beside
  // its own «Bloqueado para editar». The two cannot both be true, so the control goes and
  // the sentence stands.
  const reason = ((): string | null => {
    if (!canEdit) return t("build.readOnly");
    if (stage.status === "approved") return t("build.approved");
    if (stage.blocked_reason) return stage.blocked_reason;
    if (rawMissing) return t("build.rawMissing", { slot: slotLabelOf(rawMissing, t)! });
    if (offline) return offline;
    if (submit.isPending) return t("build.sending");
    // Already launched and waiting its turn: pressing again would only queue a second
    // copy of the same build behind the first.
    if (waiting)
      return t("build.alreadyQueued", {
        label: waiting.label,
        reason: wait ? ` ${waitReason(wait, split, tr)}` : "",
      });
    return null;
  })();

  const launch = async () => {
    if (
      !missing &&
      labels?.confirmRedo &&
      !(await confirm({
        title: labels.confirmRedo,
        confirmLabel: labels.redo,
        tone: "danger",
      }))
    )
      return;
    submit.mutate({ kind: stage.build_job });
  };

  return (
    // THE REASON NOT TO BUILD, REACHABLE WITHOUT A MOUSE. It lives in `title`, and a
    // `<button disabled>` is not focusable — so with a keyboard there was no way to land on
    // it, and on a touch screen a `title` never shows. The (i) beside it carries the same
    // sentence and answers to focus and to a tap. Only while there IS a reason: an offer
    // that can be taken needs no footnote.
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <Button
        size={size}
        variant={variant ?? (missing ? "default" : "outline")}
        disabled={Boolean(reason)}
        title={
          reason ??
          (missing
            ? t("build.create", { stage: artifactName(stage.artifact, t, stage.label).toLowerCase(), note: queueNote })
            : t("build.redo", { stage: artifactName(stage.artifact, t, stage.label).toLowerCase(), note: queueNote }))
        }
        onClick={launch}
      >
        {submit.isPending ? <Spinner /> : waiting ? <Clock /> : missing ? <Hammer /> : <RefreshCw />}
        {waiting
          ? queuedLabel(wait, tr)
          : missing
            ? (labels?.create ?? t("build.createDefault"))
            : (labels?.redo ?? t("build.redoDefault"))}
      </Button>
      {reason ? <InfoHint label={t("build.whyNot")}>{reason}</InfoHint> : null}
    </span>
  );
}

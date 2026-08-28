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
  const reason = !canEdit
    ? t("build.readOnly")
    : stage.blocked_reason
      ? stage.blocked_reason
      : rawMissing
        ? t("build.rawMissing", { slot: slotLabelOf(rawMissing, t)! })
        : offline
          ? offline
          : submit.isPending
            ? t("build.sending")
            : waiting
              ? // Already launched and waiting its turn: pressing again would only queue a
                // second copy of the same build behind the first.
                t("build.alreadyQueued", {
                  label: waiting.label,
                  reason: wait ? ` ${waitReason(wait, split, tr)}` : "",
                })
              : null;

  const launch = () => {
    if (!missing && labels?.confirmRedo && !window.confirm(labels.confirmRedo)) return;
    submit.mutate({ kind: stage.build_job });
  };

  return (
    <Button
      size={size}
      variant={variant ?? (missing ? "default" : "outline")}
      className={className}
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
  );
}

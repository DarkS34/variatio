import { Hammer, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Spinner } from "@/components/ui/misc";
import { isQueued, prospectNote, waitOf, waitReason } from "@/lib/queue";
import { rawDriftOf, slotLabelOf } from "@/lib/raw";
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
import { InfoHint } from "@/components/ui/hint";
import { cn } from "@/lib/utils";

/**
 * The one way to launch a build, offered while there is nothing built and — since the
 * documents became an upstream — while the stage is stale FOR ITS DOCUMENTS.
 *
 * The reasons for NOT offering it — an unapproved upstream, an empty raw slot, a
 * transcription of that slot still running, no engine, this build already waiting — live
 * here once, and a disabled button always says why in its tooltip and in the (i) beside it.
 *
 * A rebuild over the SAME documents is still not offered: a second pass gives no different
 * result, so the control would only throw a person's corrections away. What is offered is
 * a build over documents the last one never read (`rawDriftOf` on a stale cause), and it
 * asks first, because the corrections do go. One label for the four steps, at `xl`, on an
 * unbuilt stage, where this is the whole screen's decision; `lg` inside the stale notice,
 * beside the sentence that explains it.
 *
 * A busy engine is NOT one of the reasons: the job queues behind whatever is there, so what
 * the button owes the person is how many jobs it goes behind. With two lanes that depends
 * on a lane the server assigns at submit, so the tooltip reports the machine and only
 * predicts with one engine (`prospectNote`).
 */
export function BuildButton({ stage, className }: { stage: StageState; className?: string }) {
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

  const waiting = isQueued(own?.job) ? own!.job! : null;
  const wait = waitOf(waiting, lanes);
  const queueNote = prospectNote(lanes, split, pipeline.data?.queue_length ?? 0, tr) ?? "";
  const stageName = artifactName(stage.artifact, t, stage.label).toLowerCase();

  // Stale for its documents, and only for them: a stage stale because the step above
  // changed is closed again by continuing, and nothing here rebuilds it.
  const drift =
    stage.status === "stale"
      ? (stage.stale_because.map(rawDriftOf).find((d) => d !== null) ?? null)
      : null;

  // Two states offer it: nothing built, and built from documents that have since changed.
  // A queued build already marks the stage as building, and everything past that has
  // nothing left for this button to do.
  if (stage.status !== "missing" && drift === null) return null;

  // The permission goes first: a viewer being told that a raw slot is empty would be
  // reading advice about a button they could not press even after fixing it.
  const reason = ((): string | null => {
    if (!canEdit) return t("build.readOnly");
    if (stage.blocked_reason) return stage.blocked_reason;
    if (rawMissing) return t("build.rawMissing", { slot: slotLabelOf(rawMissing, t)! });
    // The slot this build reads is being transcribed: both would write the same page
    // cache, and the server refuses the submit for the same reason.
    if (stage.transcribing_slot)
      return t("build.transcribing", { slot: slotLabelOf(stage.transcribing_slot, t)! });
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
    if (drift) {
      // The corrections go with the rebuild, which is what the old rebuild button was
      // deleted for: here it is asked, once, with what is lost and what is kept.
      const ok = await confirm({
        title: t("build.rebuildTitle", { stage: stageName }),
        body: t("build.rebuildBody", { slot: slotLabelOf(drift.slot, t)! }),
        confirmLabel: t("build.rebuild"),
      });
      if (!ok) return;
    }
    submit.mutate({ kind: stage.build_job });
  };

  return (
    // THE REASON NOT TO BUILD, REACHABLE WITHOUT A MOUSE. It lives in `title`, and a
    // `<button disabled>` is not focusable — so with a keyboard there was no way to land on
    // it, and on a touch screen a `title` never shows. The (i) beside it carries the same
    // sentence and answers to focus and to a tap. Only while there IS a reason: an offer
    // that can be taken needs no footnote.
    <span className={cn("inline-flex flex-wrap items-center gap-2", className)}>
      <Button
        size={drift ? "lg" : "xl"}
        variant="attention"
        disabled={Boolean(reason)}
        title={
          reason ??
          t(drift ? "build.rebuildTip" : "build.create", { stage: stageName, note: queueNote })
        }
        onClick={() => void launch()}
      >
        {submit.isPending ? <Spinner /> : drift ? <RefreshCw /> : <Hammer />}
        {t(drift ? "build.rebuild" : "build.start")}
      </Button>
      {reason ? <InfoHint label={t("build.whyNot")}>{reason}</InfoHint> : null}
      {/* A refused submit (the server's 409, say) used to vanish: the mutation failed and
          nothing on the screen said so. */}
      {submit.isError ? (
        <span className="text-small text-destructive">
          {t("build.failed", { error: (submit.error as Error).message })}
        </span>
      ) : null}
    </span>
  );
}

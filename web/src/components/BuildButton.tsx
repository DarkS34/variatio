import { Hammer } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { isQueued, prospectNote, waitOf, waitReason } from "@/lib/queue";
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
import { InfoHint } from "@/components/ui/hint";
import { cn } from "@/lib/utils";

/**
 * The one way to launch a build, and it is offered ONLY while there is nothing built.
 *
 * The reasons for NOT offering it — an unapproved upstream, an empty raw slot, a
 * transcription of that slot still running, no engine, this build already waiting — live
 * here once, and a disabled button always says why in its tooltip and in the (i) beside it.
 *
 * There is no REBUILD: a second pass over the same documents gives no different result, so
 * the control was only a way to throw a person's corrections away. One label for the four
 * steps, at `xl`, because on an unbuilt stage this is the whole screen's decision.
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
  // This artifact's own build, if one is already in the queue. Once it exists the server
  // has assigned its lanes, so from here on the wait is a measurement and not a guess.
  const own = useJobRun(stage.build_job);

  const waiting = isQueued(own?.job) ? own!.job! : null;
  const wait = waitOf(waiting, lanes);
  const queueNote = prospectNote(lanes, split, pipeline.data?.queue_length ?? 0, tr) ?? "";

  // Nothing built is the only state that offers it: a queued build already marks the
  // stage as building, and everything past that has nothing left for this button to do.
  if (stage.status !== "missing") return null;

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

  return (
    // THE REASON NOT TO BUILD, REACHABLE WITHOUT A MOUSE. It lives in `title`, and a
    // `<button disabled>` is not focusable — so with a keyboard there was no way to land on
    // it, and on a touch screen a `title` never shows. The (i) beside it carries the same
    // sentence and answers to focus and to a tap. Only while there IS a reason: an offer
    // that can be taken needs no footnote.
    <span className={cn("inline-flex items-center gap-2", className)}>
      <Button
        size="xl"
        variant="attention"
        disabled={Boolean(reason)}
        title={
          reason ??
          t("build.create", {
            stage: artifactName(stage.artifact, t, stage.label).toLowerCase(),
            note: queueNote,
          })
        }
        onClick={() => submit.mutate({ kind: stage.build_job })}
      >
        {submit.isPending ? <Spinner /> : <Hammer />}
        {t("build.start")}
      </Button>
      {reason ? <InfoHint label={t("build.whyNot")}>{reason}</InfoHint> : null}
    </span>
  );
}

import { Ban } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";
import type { RunView } from "@/state/runStore";
import { useCancelJob } from "@/state/queries";

/**
 * THE STOP, AND THE FACT THAT IT WAS HEARD.
 *
 * Cancelling is cooperative: `runner.cancel` publishes `job.cancelling` at once, but the
 * job only notices at its next `progress.checkpoint()` — between two pages of a
 * transcription that is a whole model call away, and on this corpus that measured ~40 s.
 * Every screen used to disable the button for the length of the POST alone, so for those
 * forty seconds the screen was indistinguishable from one where nothing had been pressed:
 * same badge, same moving bar, button pressable again. The only trace was a line in the run
 * drawer, which is closed.
 *
 * One component rather than the same four lines in seven files, because that is exactly the
 * shape a fix drifts out of: the sites differ only in the word they use for it.
 */
export function CancelButton({
  run,
  word = "cancel",
  hint,
  label,
  size = "sm",
  className,
}: {
  run: RunView | null | undefined;
  /** «Cancelar» for a job you launched, «Detener» for one that is chewing through a slot. */
  word?: "cancel" | "stop";
  /** What stopping costs, where that is worth saying before the click rather than after. */
  hint?: string;
  /** Overrides `word` where the screen names what it is cancelling. */
  label?: string;
  size?: "sm" | "default";
  className?: string;
}) {
  const { t } = useT();
  const cancel = useCancelJob();
  const jobId = run?.job?.id ?? run?.jobId;
  if (!run || !jobId) return null;

  const stopping = run.cancelling || cancel.isPending || cancel.isSuccess;
  return (
    <Button
      variant="outline"
      size={size}
      className={className}
      disabled={stopping}
      title={stopping ? t("common.stoppingHint") : hint}
      onClick={() => cancel.mutate(jobId)}
    >
      {stopping ? <Spinner /> : <Ban />}
      {stopping ? t("common.stopping") : (label ?? t(word === "stop" ? "common.stop" : "common.cancel"))}
    </Button>
  );
}

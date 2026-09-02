import { RunTimeline } from "@/components/RunTimeline";
import { TechnicalDetails } from "@/components/TechnicalDetails";
import { TokenStream } from "@/components/TokenStream";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/misc";
import type { ExemplarsProfile } from "@/lib/types";
import type { RunView } from "@/state/runStore";

import { FewShotPanel } from "./FewShotPanel";
import { useT } from "@/lib/i18n";

/**
 * What «Detalle» opens, and it is the BODY of the strip rather than a card under it.
 *
 * It was a `Card` of its own until 2026-09-02, so pressing a disclosure on one block
 * produced a second block below it — with its own title and its own copy of the job's
 * name, both of which the strip a centimetre above was already saying.
 *
 * It is also the one place the model's reasoning is read. The result cards carried a
 * «Razonamiento» fold of their own and the two were on screen at once; what survives is
 * this one, which shows the reasoning of the item being written (the store resets it at
 * every prompt), the token stream beside it, the timeline, the exemplars the few-shot
 * used and the prompt that went out.
 */
export function RunPanel({
  run,
  running,
  waiting,
  profile,
}: {
  run: RunView;
  running: boolean;
  /** Why it has not started, when it has not. A job in the queue has no steps yet, and a
   *  timeline with nothing in it reads as a run that has stalled. */
  waiting?: string | null;
  profile: ExemplarsProfile | null;
}) {
  const { t } = useT();
  return (
    <div className="space-y-3 p-3">
      {run.guardrail && !run.guardrail.checked ? (
        <Badge variant="attention">{t("run.uncheckedInstructions")}</Badge>
      ) : null}
      {waiting ? <p className="text-small text-muted-foreground">{waiting}</p> : null}
      <RunTimeline
        steps={run.steps}
        slots={{
          generate: run.fewShot ? (
            <FewShotPanel exemplars={run.fewShot} profile={profile} />
          ) : null,
        }}
      />
      {running || run.thinking ? (
        <>
          <Separator />
          <TokenStream
            answer={run.answer}
            thinking={run.thinking}
            phase={run.phase}
            active={running}
            height="14rem"
          />
        </>
      ) : null}
      <TechnicalDetails run={run} />
    </div>
  );
}

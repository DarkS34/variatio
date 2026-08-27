import { ActivityFeed } from "@/components/ActivityFeed";
import { RunTimeline } from "@/components/RunTimeline";
import { TechnicalDetails } from "@/components/TechnicalDetails";
import { TokenStream } from "@/components/TokenStream";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/misc";
import type { ExemplarsProfile } from "@/lib/types";
import type { RunView } from "@/state/runStore";

import { FewShotPanel } from "./FewShotPanel";
import { useT } from "@/lib/i18n";

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
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <CardTitle className="flex-1">{t("run.title")}</CardTitle>
          {run.guardrail && !run.guardrail.checked ? (
            <Badge variant="attention">{t("run.uncheckedInstructions")}</Badge>
          ) : null}
          {run.job ? <Badge variant={running ? "default" : "outline"}>{run.job.label}</Badge> : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
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
        {run.activity.length > 0 ? (
          <details className="rounded-lg border border-border">
            <summary className="cursor-pointer px-3 py-2 text-small font-medium text-muted-foreground">
              {t("run.whatHappened")} ({run.activity.length})
            </summary>
            <div className="thin-scroll max-h-56 overflow-y-auto border-t border-border p-3">
              <ActivityFeed lines={run.activity} />
            </div>
          </details>
        ) : null}
      </CardContent>
    </Card>
  );
}

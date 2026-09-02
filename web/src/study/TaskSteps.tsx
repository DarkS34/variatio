import { StepCounter } from "@/components/AppShell";
import type { StepState } from "@/lib/steps";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

import { letterFor } from "./arms";
import type { EvaluationSessionHead } from "./types";

/**
 * The three stops of a comparison, in the app's own frontier encoding.
 *
 * A session is one task with a fixed order — value each proposal, choose one, and only
 * then learn who wrote what — and the order used to be something the screen hoped the
 * reader would infer from which button was disabled. The counters are the navbar's
 * (`StepCounter`), so the row spends no colour the bar was not already spending: a tick
 * behind you, `--attention` where you act, a dashed outline on what is not reachable yet.
 *
 * The rule between stops is solid once the stop before it is done and dashed otherwise,
 * which is what the retired rail encoded and the register still asks for wherever a
 * sequence has real dependencies.
 */
export function TaskSteps({
  session,
  answered,
  answerable,
}: {
  session: EvaluationSessionHead;
  answered: number;
  answerable: number;
}) {
  const { t } = useT();
  const triaged = answerable > 0 && answered === answerable;
  const decided = session.chosen_at !== null || session.declined_at !== null;
  const revealed = session.revealed;

  const stops: { state: StepState; label: string }[] = [
    {
      state: triaged || decided ? "done" : "now",
      label: triaged || decided ? t("steps.triage.done") : t("steps.triage.todo"),
    },
    {
      state: decided ? "done" : triaged ? "now" : "later",
      label: !decided
        ? t("steps.choose.todo")
        : session.declined_at !== null
          ? t("steps.choose.declined")
          : session.choice === null
            ? t("steps.choose.none")
            : t("steps.choose.done", { letter: letterFor(session.choice) }),
    },
    {
      state: revealed ? "now" : "later",
      label: revealed ? t("steps.reveal.done") : t("steps.reveal.todo"),
    },
  ];

  return (
    <ol className="flex flex-wrap items-center gap-x-3 gap-y-2" aria-label={t("steps.aria")}>
      {stops.map((stop, index) => (
        <li key={index} className="flex items-center gap-3">
          {index > 0 ? (
            <span
              aria-hidden
              className={cn(
                "w-8 border-t",
                stops[index - 1].state === "done" ? "border-border" : "border-dashed border-border",
              )}
            />
          ) : null}
          <span
            className={cn(
              "flex items-center gap-2",
              stop.state === "done" && "text-settled",
              stop.state === "now" && "font-semibold",
              stop.state === "later" && "text-muted-foreground",
            )}
            aria-current={stop.state === "now" ? "step" : undefined}
          >
            <StepCounter state={stop.state} n={String(index + 1)} />
            <span className="text-body">{stop.label}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

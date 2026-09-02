import { ArrowRight, Lock } from "lucide-react";

import { Alert } from "@/components/ui/misc";
import { buttonVariants } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { Link } from "@/lib/router";
import { STEPS, stepNumberOf } from "@/lib/steps";
import type { StageState } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * WHY THE THING YOU CAME FOR IS NOT AVAILABLE, AND THE WAY OUT OF IT.
 *
 * Generating and comparing are both gated on the whole chain being approved, and both
 * screens used to say so with a sentence and nothing else — «Comparación bloqueada · Sin
 * aprobar: Tus ejercicios». That is true and it is a dead end: it names a state without
 * naming a move, so what a person concludes is that the screen is broken, which is
 * exactly what was reported (2026-09-01, «no me deja hacer la evaluación por cuenta
 * propia»). The machinery was fine — a real comparison ran end to end from this same
 * state once the bank was approved.
 *
 * The common case is not «you have not built it» but «it went stale»: approving the
 * syllabus after the bank leaves the bank pointing at an older upstream, and putting that
 * right is one press of «Continuar» on a screen the person has already seen. So the gate
 * links straight to the first stage in the way, by artifact and never by a hand-written
 * path — `STEPS` is the same list the bar draws, so this offer cannot promise a
 * destination the navigation does not have.
 */
export function ChainGate({ title, stages }: { title: string; stages: StageState[] }) {
  const { t } = useT();
  const pending = stages.filter((stage) => stage.status !== "approved");
  if (pending.length === 0) return null;

  const first = pending[0];
  const step = STEPS.find((s) => s.artifact === first.artifact);
  // The number is `STEPS`' own and not computed here, so the button cannot promise a
  // step the bar numbers differently.
  const at = stepNumberOf(first.artifact);

  return (
    <Alert tone="attention" title={title}>
      <p className="flex items-center gap-1.5">
        <Lock className="size-3.5" />
        {t("chain.pending", { stages: pending.map((s) => s.label).join(", ") })}
      </p>
      {step ? (
        <div className="mt-2.5">
          <Link
            to={step.path}
            className={cn(buttonVariants({ variant: "attention", size: "sm" }))}
          >
            {t("chain.goFix", { n: at ?? "", label: first.label })}
            <ArrowRight />
          </Link>
        </div>
      ) : null}
    </Alert>
  );
}

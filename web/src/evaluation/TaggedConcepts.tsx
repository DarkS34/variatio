import { ShieldAlert, ShieldCheck } from "lucide-react";

import { ConceptChip } from "@/components/ui/concept-chip";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

import type { ProposalTagging } from "./types";

/**
 * What the graph makes of one proposal, and whether it went where it was told not to.
 *
 * It is the SAME tagger the bank is read with, run over the three proposals alike once
 * they are all in, so the concepts under a card are the system's own reading of that
 * exercise and not a second instrument invented for the evaluation. The primary one — the
 * concept the exercise PRACTISES — is drawn as the bank draws it, and a concept out of
 * bounds carries its reason as text and not only as a colour.
 *
 * THE LINE IS DRAWN IN BOTH STATES, unlike the checks box, which is only drawn when
 * something is flagged. This is a comparison: three cards side by side, two carrying a
 * warning and one carrying nothing, and the silent one reads as missing data rather than
 * as a clean proposal.
 *
 * It carries no chrome of its own — the card wraps it in its own foot and the reading
 * dialog drops it into a stack — and it is deliberately NOT drawn beside the rubric: the
 * `prerequisites` scale asks the evaluator almost exactly what `off_limits` answers
 * («¿se resuelve con lo que va antes en el temario?»), and putting the machine's answer
 * against the scale would stop the two from being independent readings of one exercise.
 */
export function TaggedConcepts({ tagging }: { tagging: ProposalTagging }) {
  const { t, plural } = useT();
  const trespasses = tagging.off_limits;
  // What the line SAYS follows the rule the pass applied: «usa» when a curriculum made the
  // closure untaught, «practica» when nobody said where the class stands and only the
  // practised concept was held against the proposal. An older record has no rule and was
  // read under the first.
  const practises = tagging.rule === "practises";
  const out = new Set(trespasses);
  const concepts = [...tagging.concepts].sort(
    (a, b) => Number(b === tagging.primary) - Number(a === tagging.primary),
  );

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-micro font-condensed uppercase text-muted-foreground">
          {t("bank.concepts")}
        </span>
        {concepts.length === 0 ? (
          <span className="text-small text-muted-foreground">{t("reveal.tagging.none")}</span>
        ) : (
          concepts.map((concept) => (
            <ConceptChip
              key={concept}
              tone={
                out.has(concept) ? "attention" : concept === tagging.primary ? "primary" : "default"
              }
              title={
                out.has(concept)
                  ? t("reveal.tagging.offLimits")
                  : concept === tagging.primary
                    ? t("concept.isPrimary")
                    : undefined
              }
            >
              {concept}
            </ConceptChip>
          ))
        )}
      </div>

      <p
        className={cn(
          "flex items-start gap-1.5 text-small",
          trespasses.length ? "text-attention" : "text-muted-foreground",
        )}
      >
        {trespasses.length ? (
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" />
        ) : (
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
        )}
        <span>
          {trespasses.length
            ? practises
              ? t("reveal.tagging.practised", { list: trespasses.join(", ") })
              : plural("reveal.tagging.trespass", trespasses.length, {
                  list: trespasses.join(", "),
                })
            : practises
              ? t("reveal.tagging.cleanPractised")
              : t("reveal.tagging.clean")}
        </span>
      </p>
    </div>
  );
}

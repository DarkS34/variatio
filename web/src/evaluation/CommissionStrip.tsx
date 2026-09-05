import { ConceptChip } from "@/components/ui/concept-chip";
import { readableValue } from "@/lib/text";
import { difficultyFieldOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

import type { EvaluationSessionHead } from "./types";

/**
 * What was asked for, in one line: the modality, the concepts, and the level if one was
 * pinned.
 *
 * It is the same for the three proposals, so it gives none of them away — and it is the
 * one thing a reader needs that is inside none of the cards: «practica de verdad los
 * conceptos pedidos» cannot be judged without knowing which they were. It sits OUTSIDE
 * the cards for the same reason, once rather than three times.
 *
 * The level is drawn only when the commission pinned one. With «Cualquiera» the whole
 * group goes, separator included: a row reading «Nivel: cualquiera» reports the absence
 * of a decision as though it were one. The free-text instructions are deliberately not
 * here — they are the judge's business, not the reader's.
 */
export function CommissionStrip({
  session,
  profile,
  className,
}: {
  session: EvaluationSessionHead;
  profile: ExemplarsProfile | null;
  className?: string;
}) {
  const { t } = useT();
  const spec = profile?.item_types[session.item_type] ?? null;
  const difficulty = difficultyFieldOf(spec);
  const level = difficulty ? session.fixed?.[difficulty] : undefined;
  const pinned = typeof level === "string" && level.trim() !== "";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-2.5 gap-y-1.5 border border-border bg-muted px-3.5 py-2",
        className,
      )}
    >
      <span className="text-micro font-condensed text-muted-foreground uppercase">
        {t("commission.label")}
      </span>
      <span className="font-medium">{typeLabel(profile, session.item_type, t)}</span>

      <Rule />
      <span className="text-micro font-condensed text-muted-foreground uppercase">
        {t("commission.topics")}
      </span>
      <span className="flex flex-wrap items-center gap-1.5">
        {session.concepts.map((concept) => (
          <ConceptChip key={concept}>{concept}</ConceptChip>
        ))}
      </span>

      {pinned ? (
        <>
          <Rule />
          <span className="text-micro font-condensed text-muted-foreground uppercase">
            {t("commission.level")}
          </span>
          <span className="font-medium">{readableValue(level)}</span>
        </>
      ) : null}
    </div>
  );
}

function Rule() {
  return <span aria-hidden className="h-3.5 w-px bg-border" />;
}

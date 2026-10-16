import { useRadioGroup, type RadioProps } from "@/components/ui/radio";
import { splitCriterion } from "@/lib/difficulty";
import { readableValue } from "@/lib/text";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { ChoiceMark } from "@/components/ui/choice";
import { CHOICE_CARD, CHOICE_CHOSEN } from "./FormStep";

/**
 * Which rung of the ladder the exercise being commissioned should sit on.
 *
 * It is NOT one more `DecisionField`, and the difference is the reason it has a step of
 * its own. Every modality carries this field — that is a closed decision — so on the many
 * profiles built before the rule it is there without `decided_by: "user"`, and reading it
 * through `userDecidedFields` would offer it on some instances and not on others. And it
 * is the only field whose values come with a written criterion per rung, which is worth
 * reading beside the option it describes rather than as one paragraph above four chips.
 *
 * `undefined` means unpinned, and that is what "Cualquiera" sets: silently pinning the
 * first rung because it happens to be first would put a decision in the prompt that
 * nobody made.
 */
export function DifficultyChoice({
  levels,
  description,
  value,
  onChange,
}: {
  levels: string[];
  description?: string | null;
  value: unknown;
  onChange: (next: string | undefined) => void;
}) {
  const { t } = useT();
  const { lead, rungs } = splitCriterion(description, levels);
  const detail = new Map(rungs.map((rung) => [rung.level, rung.text]));
  // «Cualquiera» is the last radio, and null stands for it: an arrow that reaches it unpins.
  const chosen = levels.find((level) => level === value) ?? null;
  const radios = useRadioGroup<string | null>([...levels, null], chosen, (level) =>
    onChange(level ?? undefined),
  );

  return (
    <div className="space-y-2.5">
      {/* The axis, once. A criterion nobody could take apart lands here whole, which is
          the honest degradation: it still says what the three mean, only not per option. */}
      {lead ? <p className="text-small text-muted-foreground">{lead}</p> : null}

      {/* A LIST, one rung under the next, and every box the same height. The order is the
          ladder's, so it is read down; what the fixed height fixes is that «Cualquiera»,
          whose hint is one line, no longer sits in a box half the size of «Intermedio». */}
      <div
        role="radiogroup"
        aria-label={t("form.difficulty.title")}
        className="grid gap-4 p-1"
        {...radios.group}
      >
        {levels.map((level) => (
          <Rung
            key={level}
            radio={radios.radio(level)}
            label={readableValue(level)}
            detail={detail.get(level)}
            active={value === level}
            onClick={() => onChange(value === level ? undefined : level)}
          />
        ))}
        <Rung
          radio={radios.radio(null)}
          label={t("decision.any")}
          detail={t("form.difficulty.anyHint")}
          active={value === undefined || value === null || value === ""}
          onClick={() => onChange(undefined)}
        />
      </div>
    </div>
  );
}

function Rung({
  radio,
  label,
  detail,
  active,
  onClick,
}: {
  /** Its place in the group's keyboard (`useRadioGroup`). */
  radio: RadioProps;
  label: string;
  detail?: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      {...radio}
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={cn(
        CHOICE_CARD,
        active && CHOICE_CHOSEN,
      )}
    >
      <span className="flex items-center gap-2 text-body font-medium text-foreground">
        <ChoiceMark chosen={active} />
        {label}
      </span>
      {/* Clamped at three lines, like a modality's description, and never `block` beside
          `line-clamp-3`: the clamp sets `display: -webkit-box` and `block` wins over it in
          silence. The whole criterion is read and corrected in step 2, where a rung is
          defined; here the clause is what tells one rung from the next. */}
      {detail ? (
        <span className="mt-1 line-clamp-3 text-body text-muted-foreground">{detail}</span>
      ) : null}
    </button>
  );
}

import { splitCriterion } from "@/lib/difficulty";
import { readableValue } from "@/lib/text";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

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
 * `undefined` means unpinned, and that is what «Cualquiera» sets: silently pinning the
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

  return (
    <div className="space-y-2.5">
      {/* The axis, once. A criterion nobody could take apart lands here whole, which is
          the honest degradation: it still says what the three mean, only not per option. */}
      {lead ? <p className="text-small text-muted-foreground">{lead}</p> : null}

      <div role="radiogroup" aria-label={t("form.difficulty.title")} className="grid gap-1.5">
        {levels.map((level) => (
          <Rung
            key={level}
            label={readableValue(level)}
            detail={detail.get(level)}
            active={value === level}
            onClick={() => onChange(value === level ? undefined : level)}
          />
        ))}
        <Rung
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
  label,
  detail,
  active,
  onClick,
}: {
  label: string;
  detail?: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      onClick={onClick}
      className={cn(
        "rounded-lg border px-3 py-2 text-left transition-colors",
        active
          ? "border-primary bg-primary/10"
          : "border-border hover:bg-accent",
      )}
    >
      <span className={cn("text-body font-medium", active ? "text-primary" : "text-foreground")}>
        {label}
      </span>
      {detail ? (
        <span className="mt-0.5 block text-body text-muted-foreground">{detail}</span>
      ) : null}
    </button>
  );
}

import { Check } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { cn } from "@/lib/utils";

import type { EvaluationRating, Instruments } from "./types";
import { useT } from "@/lib/i18n";

/**
 * Four questions about OUR variant, after the reveal, and deliberately OPTIONAL.
 *
 * Every dimension answers to a clause the system's prompt claims to enforce — "practicar no
 * es usar" is `concept_fit`, self-sufficiency is `soundness`, the prerequisite scaffolding
 * is `prerequisites`, calibration is `complexity` — which is what connects the numbers to
 * the design chapter rather than to a generic quality survey. A scale with no clause behind
 * it does not belong here.
 *
 * The WORDING comes from the server: a teacher and a student are asked the same four things
 * in different words, and the wording IS the instrument — one edit in
 * `evaluation/api/instruments.py`, never two copies drifting apart.
 *
 * One scale per row, at full measure, in a track of its own beside the exercise it rates.
 *
 * Optional is the point: everything blind was collected before the reveal, so somebody in a
 * hurry has already left a complete datum. Usability is not asked here — it is the blind
 * per-card triage, and asking it twice in one session asks somebody to contradict
 * themselves.
 */
function Scale({
  value,
  onChange,
  ends,
  target,
}: {
  value: number | undefined;
  onChange: (next: number) => void;
  ends: [string, string];
  target?: number | null;
}) {
  const { t } = useT();
  return (
    <div className="space-y-1">
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((score) => (
          <button
            key={score}
            type="button"
            onClick={() => onChange(score)}
            aria-label={t("rubric.scoreOf", { n: score })}
            aria-pressed={value === score}
            className={cn(
              "h-9 flex-1 border text-body nums transition-colors",
              value === score
                ? "border-primary bg-primary text-primary-foreground font-medium"
                : "border-input hover:bg-accent/60",
              // The target of `complexity` is 3, not 5. Marking it is the only way the
              // scale reads as "aim for the middle" instead of "more is better" — and it
              // disappears once 3 IS the answer, because then there is nothing to point out.
              target === score && value !== score && "border-dashed border-attention",
            )}
          >
            {score}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-small text-muted-foreground">
        <span>{ends[0]}</span>
        {target ? <span className="text-attention">{t("rubric.target", { target })}</span> : null}
        <span>{ends[1]}</span>
      </div>
    </div>
  );
}

export function RubricForm({
  rating,
  instruments,
  onSave,
  onSkip,
  pending,
}: {
  rating: EvaluationRating | null;
  instruments: Instruments;
  onSave: (rating: Partial<EvaluationRating>) => void;
  onSkip: () => void;
  pending: boolean;
}) {
  const { t } = useT();
  const [draft, setDraft] = useState<Partial<EvaluationRating>>(rating ?? {});
  const saved = Boolean(rating);
  const patch = (fields: Partial<EvaluationRating>) => setDraft({ ...draft, ...fields });
  const key = (name: string) => name as keyof EvaluationRating;
  const complete = instruments.rubric.every((scale) => draft[key(scale.key)] !== undefined);

  return (
    <section className="space-y-4 border border-border bg-card p-5 shadow-sm">
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 className="text-heading font-semibold">{t("rubric.title")}</h2>
          <span className="rounded-full bg-muted px-2 py-0.5 text-micro font-condensed text-muted-foreground uppercase">
            {t("common.optional")}
          </span>
          {saved ? (
            <span className="ml-auto flex items-center gap-1 text-small text-settled">
              <Check className="size-3.5" />
              {t("rubric.saved")}
            </span>
          ) : null}
        </div>
      </header>

      <div className="space-y-4">
        {instruments.rubric.map((scale) => (
          <div key={scale.key} className="space-y-2">
            <div>
              <p className="text-body font-semibold">{scale.label}</p>
              <p className="text-small text-muted-foreground">{scale.question}</p>
            </div>
            <Scale
              value={draft[key(scale.key)] as number | undefined}
              onChange={(next) =>
                patch({ [scale.key]: next } as unknown as Partial<EvaluationRating>)
              }
              ends={scale.ends}
              target={scale.target}
            />
          </div>
        ))}
      </div>

      <Textarea
        aria-label={t("rubric.commentAria")}
        value={draft.comment ?? ""}
        onChange={(event) => patch({ comment: event.target.value })}
        placeholder={t("rubric.commentPlaceholder")}
        className="min-h-[4.5rem]"
      />

      <div className="flex flex-wrap items-center gap-3">
        <p className="flex-1 text-small text-muted-foreground">{t("rubric.skippable")}</p>
        <Button variant="outline" onClick={onSkip}>
          {t("rubric.skip")}
        </Button>
        <Button disabled={!complete || pending} onClick={() => onSave(draft)}>
          {pending ? <Spinner /> : null}
          {saved ? t("rubric.update") : t("rubric.save")}
        </Button>
      </div>
    </section>
  );
}

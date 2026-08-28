import { Check, CircleSlash } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { ItemFields } from "@/features/run/ResultCard";
import { itemTypeOf } from "@/lib/profile";
import type { ExemplarsProfile } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ARM_META, letterFor } from "./arms";
import type { EvaluationPosition, Instruments, TriageValue } from "./types";
import { useT } from "@/lib/i18n";

/**
 * Three proposals, told apart by nothing but a letter.
 *
 * Everything here exists to keep the cards indistinguishable until the evaluator has
 * committed: identical height so a longer statement cannot read as "more complete"
 * before it is read, identical field order, no colour, no ids, no reasoning, no JSON —
 * only the system's arm produces interesting reasoning, which makes it a perfect tell.
 *
 * The LETTER CARRIES NO STATE, and that is not an oversight. It is the handle somebody
 * uses to say «la B»; filling it to mean «ya respondida» would make it a signal, which is
 * the one thing the blinding exists to keep it from being — and «respondida» is already
 * said twice over, by the card's own border and by the option that is pressed.
 */
function ProposalCard({
  position,
  profile,
  itemType,
  revealed,
  chosen,
  triage,
  instruments,
  onTriage,
  pending,
}: {
  position: EvaluationPosition;
  profile: ExemplarsProfile;
  itemType: string;
  revealed: boolean;
  chosen: boolean;
  triage: TriageValue | undefined;
  instruments: Instruments;
  onTriage: (value: TriageValue) => void;
  pending: boolean;
}) {
  const { t } = useT();
  const letter = letterFor(position.position);
  const meta = revealed && position.arm ? ARM_META[position.arm] : null;
  const hasItem = Boolean(position.item);
  const answered = Boolean(triage);

  return (
    <article
      className={cn(
        "flex h-full flex-col overflow-hidden border bg-card shadow-sm transition-colors",
        chosen ? "border-transparent ring-2 ring-[var(--ring)]" : answered ? "border-input" : "border-border",
      )}
      style={meta ? { borderColor: `color-mix(in oklch, ${meta.colour} 45%, transparent)` } : undefined}
    >
      <header className="flex items-center gap-2.5 border-b border-border px-3 py-2.5">
        <span
          className={cn(
            "flex size-8 shrink-0 items-center justify-center font-mono text-heading transition-colors",
            meta ? "text-background" : "bg-muted text-muted-foreground",
          )}
          style={meta ? { backgroundColor: meta.colour, color: "var(--background)" } : undefined}
        >
          {letter}
        </span>
        <div className="min-w-0">
          <p className="truncate text-body font-medium">
            {meta ? t(meta.labelKey) : t("grid.proposal", { letter })}
          </p>
          {meta ? (
            <p className="truncate font-mono text-[11px] text-muted-foreground">
              {position.model}
            </p>
          ) : null}
        </div>
        {/* Which card still owes an answer is said at the card's own edge, not by an alert
            elsewhere on the screen. */}
        {!revealed && hasItem && !answered ? (
          <span className="ml-auto shrink-0 text-micro font-condensed text-attention uppercase">
            {t("grid.missing")}
          </span>
        ) : null}
        {chosen ? (
          <span className="ml-auto flex shrink-0 items-center gap-1 text-small font-medium text-primary">
            <Check className="size-3.5" />
            {t("grid.yourChoice")}
          </span>
        ) : null}
      </header>

      <div className="thin-scroll max-h-[30rem] flex-1 space-y-3 overflow-y-auto p-3">
        {hasItem ? (
          <ItemFields item={position.item!} spec={itemTypeOf(profile, { item_type: itemType })} />
        ) : (
          <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 text-center">
            <CircleSlash className="size-5 text-muted-foreground/60" />
            <p className="max-w-56 text-body text-muted-foreground">{t("grid.noValidItem")}</p>
            {revealed && position.error ? (
              <p className="max-w-64 text-small text-muted-foreground/80">{position.error}</p>
            ) : null}
          </div>
        )}
      </div>

      {/* THE TRIAGE. One question, one click, before anything is revealed — which is what
          gives the study a quality signal for all THREE architectures instead of a score
          for one of them written by somebody who already knew which it was. */}
      {hasItem && !revealed ? (
        <footer className="flex gap-1 border-t border-border bg-muted p-2.5">
          {instruments.triage.options.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={pending}
              onClick={() => onTriage(option.value)}
              aria-pressed={triage === option.value}
              aria-label={t("grid.triageOption", {
                question: instruments.triage.question,
                option: option.label,
              })}
              className={cn(
                "h-8 flex-1 border text-small font-medium transition-colors disabled:opacity-60",
                triage === option.value
                  ? "border-primary bg-primary text-primary-foreground"
                  : answered
                    ? "border-input bg-card hover:bg-accent/60"
                    : "border-dashed border-attention bg-card text-attention hover:bg-accent/60",
              )}
            >
              {option.label}
            </button>
          ))}
        </footer>
      ) : null}

      {/* After the reveal the answer is shown back: it is what makes the reveal informative
          rather than a bare name. */}
      {hasItem && revealed && triage ? (
        <footer className="flex items-center justify-between gap-2 border-t border-border bg-muted px-3 py-2">
          <span className="text-small text-muted-foreground">{t("grid.youSaid")}</span>
          <span className="text-small font-semibold">
            {instruments.triage.options.find((option) => option.value === triage)?.label}
          </span>
        </footer>
      ) : null}
    </article>
  );
}

export function ComparisonGrid({
  positions,
  profile,
  itemType,
  revealed,
  choice,
  triage,
  instruments,
  onChoose,
  onTriage,
  onDecline,
  pending,
}: {
  positions: EvaluationPosition[];
  profile: ExemplarsProfile;
  itemType: string;
  revealed: boolean;
  choice: number | null;
  triage: Record<string, TriageValue>;
  instruments: Instruments;
  onChoose: (choice: number | null, comment?: string) => void;
  onTriage: (position: number, value: TriageValue) => void;
  onDecline: () => void;
  pending: boolean;
}) {
  const { t } = useT();
  const [note, setNote] = useState("");

  // A card with no item cannot be triaged, so it cannot be what is being waited for.
  const answerable = positions.filter((position) => Boolean(position.item));
  const answered = answerable.filter((position) => triage[String(position.position)]);
  const complete = answerable.length > 0 && answered.length === answerable.length;
  const missing = answerable.length - answered.length;

  return (
    <div className="space-y-4">
      {/* THE QUESTION, ASKED ONCE. The answers are per card, but the wording belongs to
          the task rather than to the card, so three copies of it would only be noise. */}
      {!revealed ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border border-border border-l-[3px] border-l-primary bg-card px-4 py-3">
          <p className="text-body">
            <strong>
              {t("grid.forEach", { question: instruments.triage.question.toLowerCase() })}
            </strong>{" "}
            <span className="text-muted-foreground">{instruments.triage.hint}</span>
          </p>
          <p className="ml-auto text-small nums text-muted-foreground">
            {t("grid.answered", { answered: answered.length, total: answerable.length })}
          </p>
        </div>
      ) : null}

      <div className="grid items-stretch gap-4 xl:grid-cols-3">
        {positions.map((position) => (
          <ProposalCard
            key={position.position}
            position={position}
            profile={profile}
            itemType={itemType}
            revealed={revealed}
            chosen={choice === position.position}
            triage={triage[String(position.position)]}
            instruments={instruments}
            onTriage={(value) => onTriage(position.position, value)}
            pending={pending}
          />
        ))}
      </div>

      {/* THE CHOICE. Drawn from the first second so the shape of the task is visible, and
          inert until the three are answered so the order is not a rule anybody has to be
          told. Forcing a pick between three bad ones turns noise into signal. */}
      {!revealed ? (
        <div className="animate-slide-up space-y-3 border border-border bg-muted p-3">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-body">
              <strong>{t("grid.whichWouldYouUse")}</strong>{" "}
              {!complete ? (
                <span className="text-muted-foreground">
                  {missing === 1
                    ? t("grid.answerMissingOne")
                    : t("grid.answerMissing", { n: missing })}
                </span>
              ) : null}
            </p>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              {positions.map((position) => (
                <Button
                  key={position.position}
                  variant={complete ? "default" : "outline"}
                  disabled={!complete || !position.item || pending}
                  onClick={() => onChoose(position.position, note)}
                  aria-label={t("grid.chooseAria", { letter: letterFor(position.position) })}
                >
                  {pending ? <Spinner /> : null}
                  {position.item
                    ? t("grid.choose", { letter: letterFor(position.position) })
                    : t("grid.noExercise")}
                </Button>
              ))}
            </div>
          </div>

          {complete ? (
            <div className="flex flex-wrap items-center gap-3">
              <Input
                aria-label={t("grid.whyAria")}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder={t("grid.whyPlaceholder")}
                className="h-9 min-w-48 flex-1"
              />
              <Button variant="ghost" disabled={pending} onClick={() => onChoose(null, note)}>
                {t("grid.noneConvinces")}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* The way out for somebody outside this subject: quiet, at the edge, never competing
          with the task, and never dressed as a failure. With evaluators drawn from
          different subjects it is a real answer, and the study wants it told. */}
      {!revealed ? (
        <div className="flex justify-end">
          <button
            type="button"
            disabled={pending}
            onClick={onDecline}
            title={instruments.decline.hint}
            className="border-b border-input pb-px text-small text-muted-foreground transition-colors hover:text-foreground disabled:opacity-60"
          >
            {instruments.decline.label}
          </button>
        </div>
      ) : null}
    </div>
  );
}

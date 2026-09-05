import { ChevronLeft, ChevronRight, CircleSlash } from "lucide-react";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ItemChecks, ItemFields } from "@/features/run/ResultCard";
import { itemTypeOf } from "@/lib/profile";
import type { ExemplarsProfile } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

import { ARM_META, letterFor } from "./arms";
import { CommissionStrip } from "./CommissionStrip";
import { TaggedConcepts } from "./TaggedConcepts";
import type { EvaluationPosition, EvaluationSessionHead, Instruments, TriageValue } from "./types";

/**
 * One proposal at reading size, over the comparison.
 *
 * The three cards share a row, so each gets a third of the window — and an exercise with
 * a grammar and a table in it does not read at a third of a window. This is the one
 * surface in the app that is a READING surface rather than dense chrome, so the body
 * steps up from 14 to 15 px and the measure is capped at about 62 characters.
 *
 * Answering from here is the point: reading it in full and judging it are the same
 * moment, so the question comes with it in the footer instead of waiting behind the
 * close button. ←/→ page through the three, because the three are read against each
 * other and closing to open the next one is three clicks per comparison.
 *
 * Before the reveal it knows nothing the card did not: a letter, the commission, the
 * fields. After it the header names the arm, in its colour, the footer shows the answer
 * back instead of asking again, and a foot under the exercise says where it came from —
 * the arm's own description, what the checks raised and the fragments it was handed. That
 * foot is what the card's «Detalle» used to unfold (2026-09-04, explicit user request:
 * one button per card), minus the exact prompt and the retry count, which went with it.
 */
export function ProposalDialog({
  position,
  positions,
  session,
  profile,
  instruments,
  triage,
  pending,
  onTriage,
  onMove,
  onClose,
}: {
  position: EvaluationPosition | null;
  positions: EvaluationPosition[];
  session: EvaluationSessionHead;
  profile: ExemplarsProfile;
  instruments: Instruments;
  triage: Record<string, TriageValue>;
  pending: boolean;
  onTriage: (position: number, value: TriageValue) => void;
  onMove: (position: number) => void;
  onClose: () => void;
}) {
  const { t, plural } = useT();
  const open = position !== null;
  const index = position ? positions.findIndex((p) => p.position === position.position) : -1;
  const previous = index > 0 ? positions[index - 1] : null;
  const next = index >= 0 && index < positions.length - 1 ? positions[index + 1] : null;

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft" && previous) onMove(previous.position);
      if (event.key === "ArrowRight" && next) onMove(next.position);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, previous, next, onMove]);

  if (!position) return null;

  const letter = letterFor(position.position);
  const meta = session.revealed && position.arm ? ARM_META[position.arm] : null;
  const answer = triage[String(position.position)];
  const answered = Boolean(answer);
  const hasItem = Boolean(position.item);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="sm:max-w-4xl"
      title={
        <span className="flex items-center gap-3">
          <span
            className={cn(
              "flex size-8 shrink-0 items-center justify-center font-mono text-heading",
              meta ? "" : "bg-muted text-muted-foreground",
            )}
            style={meta ? { backgroundColor: meta.colour, color: "var(--background)" } : undefined}
          >
            {letter}
          </span>
          <span>{meta ? t(meta.labelKey) : t("grid.proposal", { letter })}</span>
          <span className="font-mono text-small font-normal nums text-muted-foreground">
            {t("focus.of", { n: index + 1, total: positions.length })}
          </span>
        </span>
      }
      actions={
        <>
          <Button
            variant="outline"
            size="icon-sm"
            disabled={!previous}
            onClick={() => previous && onMove(previous.position)}
            aria-label={t("common.previous")}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            disabled={!next}
            onClick={() => next && onMove(next.position)}
            aria-label={t("common.next")}
          >
            <ChevronRight />
          </Button>
        </>
      }
      footer={
        hasItem && !session.revealed ? (
          <div className="flex w-full flex-wrap items-center gap-3">
            <p className="font-semibold">{instruments.triage.question}</p>
            <div className="ml-auto flex flex-wrap gap-1.5">
              {instruments.triage.options.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  disabled={pending}
                  onClick={() => onTriage(position.position, option.value)}
                  aria-pressed={answer === option.value}
                  aria-label={t("grid.triageOption", {
                    question: instruments.triage.question,
                    option: option.label,
                  })}
                  className={cn(
                    "h-9 min-w-28 border px-4 text-body font-medium transition-colors disabled:opacity-60",
                    answer === option.value
                      ? "border-primary bg-primary text-primary-foreground"
                      : answered
                        ? "border-input bg-card hover:bg-accent/60"
                        : "border-dashed border-attention bg-card text-attention hover:bg-accent/60",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        ) : hasItem && answer ? (
          <p className="text-small text-muted-foreground">
            {t("grid.youSaid")}{" "}
            <strong className="font-semibold text-foreground">
              {instruments.triage.options.find((option) => option.value === answer)?.label}
            </strong>
          </p>
        ) : undefined
      }
    >
      <CommissionStrip
        session={session}
        profile={profile}
        className="-mx-3 -mt-3 mb-5 border-x-0 border-t-0 sm:-mx-4 sm:-mt-4"
      />

      {hasItem ? (
        // The same `ItemFields` as the card, one size up: the fields are rendered by the
        // same code on every screen, and a comparison must not measure layout.
        <div className="mx-auto max-w-[62ch] space-y-4 py-2">
          <ItemFields
            item={position.item!}
            spec={itemTypeOf(profile, { item_type: session.item_type })}
            reading
          />
          {meta ? (
            <div className="space-y-3 border-t border-border pt-4">
              <p className="text-small leading-relaxed text-muted-foreground">
                {t(meta.descriptionKey)}
              </p>
              {position.tagging ? <TaggedConcepts tagging={position.tagging} /> : null}
              {position.error ? <p className="text-small text-attention">{position.error}</p> : null}
              {position.checks ? <ItemChecks checks={position.checks} /> : null}
              {position.exemplar_ids && position.exemplar_ids.length > 0 ? (
                <p className="font-mono text-small text-muted-foreground">
                  {plural("reveal.examplesFromBank", position.exemplar_ids.length)} ·{" "}
                  {position.exemplar_ids.join(" · ")}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="flex min-h-40 flex-col items-center justify-center gap-2 text-center">
          <CircleSlash className="size-5 text-muted-foreground/60" />
          <p className="max-w-64 text-body text-muted-foreground">{t("grid.noValidItem")}</p>
          {session.revealed && position.error ? (
            <p className="max-w-72 text-small text-muted-foreground/80">{position.error}</p>
          ) : null}
        </div>
      )}
    </Dialog>
  );
}

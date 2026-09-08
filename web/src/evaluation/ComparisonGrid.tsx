import { ArrowDown, CircleSlash, Maximize2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { ItemFields } from "@/features/generate/ResultCard";
import { itemTypeOf } from "@/lib/profile";
import type { ExemplarsProfile } from "@/lib/types";
import { cn } from "@/lib/utils";

import { letterFor } from "./arms";
import type { EvaluationPosition, Instruments, TriageValue } from "./types";
import { useT } from "@/lib/i18n";

/**
 * Two proposals — the system's and one rival's — told apart by nothing but a letter.
 *
 * Everything here exists to keep the cards indistinguishable until the evaluator has
 * committed: identical height so a longer statement cannot read as "more complete"
 * before it is read, identical field order, no colour, no ids, no reasoning, no JSON —
 * only the system's arm produces interesting reasoning, which makes it a perfect tell.
 * Which rival this session holds is a tell too, so nothing here knows it either.
 *
 * THE CARD HAS NO SCROLLBAR OF ITS OWN. It used to clip at 30rem and scroll inside, so an
 * exercise with a grammar and a table in it was read through a slot a third of the window
 * wide and half a window tall, once per card. The page scrolls once and the cards stay
 * the same height, which keeps the blinding intent; what half a window cannot hold
 * is read through "Leer en grande", at reading size, over the comparison.
 *
 * The LETTER CARRIES NO STATE, and that is not an oversight. It is the handle somebody
 * uses to say "la B"; filling it to mean "ya respondida" would make it a signal, which is
 * the one thing the blinding exists to keep it from being — and "respondida" is already
 * said twice over, by the card's own border and by the option that is pressed.
 */
// How much of a proposal a card shows before the fade. Measured against the reference
// exercises: a statement plus the head of its solution, which is what tells two
// proposals apart at a glance; the whole thing is one press away.
const CLIP = "max-h-[22rem]";

/** How many cards a session prepared from now on holds: the system's and one rival's. */
export const CARDS = 2;

/**
 * One column per card, at the width the session HOLDS: two since 2026-09-08, three on a
 * session recorded before. Literal class names, because Tailwind only emits what it can
 * read in the source.
 */
export const columnsFor = (cards: number) => (cards >= 3 ? "xl:grid-cols-3" : "xl:grid-cols-2");

function ProposalCard({
  position,
  profile,
  itemType,
  triage,
  instruments,
  onTriage,
  onRead,
  pending,
}: {
  position: EvaluationPosition;
  profile: ExemplarsProfile;
  itemType: string;
  triage: TriageValue | undefined;
  instruments: Instruments;
  onTriage: (value: TriageValue) => void;
  onRead: () => void;
  pending: boolean;
}) {
  const { t } = useT();
  const letter = letterFor(position.position);
  const hasItem = Boolean(position.item);
  const answered = Boolean(triage);

  return (
    <article
      className={cn(
        "flex h-full flex-col border bg-card shadow-sm transition-colors",
        answered ? "border-input" : "border-border",
      )}
    >
      <header className="flex items-center gap-2.5 border-b border-border px-3 py-2.5">
        <span className="flex size-8 shrink-0 items-center justify-center bg-muted font-mono text-heading text-muted-foreground">
          {letter}
        </span>
        <p className="min-w-0 truncate text-body font-medium">{t("grid.proposal", { letter })}</p>
        {/* Which card still owes an answer is said at the card's own edge, not by an alert
            elsewhere on the screen. */}
        {hasItem && !answered ? (
          <span className="ml-auto flex shrink-0 items-center gap-1 text-micro font-condensed text-attention uppercase">
            {t("grid.missing")}
            {/* An ARROW and not a chevron: a bare "v" beside a label reads as a disclosure
                — "this opens" — where what it does is point at the triage buttons under
                the card. The shaft is what makes it a direction. */}
            <ArrowDown className="size-3.5" strokeWidth={2.5} aria-hidden />
          </span>
        ) : null}
        {hasItem ? (
          <Button
            variant="ghost"
            size="icon-sm"
            className={cn("shrink-0 text-muted-foreground", answered && "ml-auto")}
            onClick={onRead}
            aria-label={t("focus.read", { letter })}
            title={t("focus.read", { letter })}
          >
            <Maximize2 />
          </Button>
        ) : null}
      </header>

      {/* The body is CLIPPED and never scrolled: two whole exercises side by side run to
          several screens, and what a card shows is enough to tell them apart. The rest is
          read through "Leer en grande", and the fade says there is more rather than
          pretending the statement ends where the box does. The cards still share ONE
          height, so a longer proposal cannot read as "more complete" before it is read. */}
      <div className={cn("relative flex-1 overflow-hidden", hasItem && CLIP)}>
        {hasItem ? (
          <>
            <div className="space-y-3 p-4">
              <ItemFields item={position.item!} spec={itemTypeOf(profile, { item_type: itemType })} />
            </div>
            <div
              aria-hidden
              className="pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-card to-transparent"
            />
          </>
        ) : (
          <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 p-4 text-center">
            <CircleSlash className="size-5 text-muted-foreground/60" />
            <p className="max-w-56 text-body text-muted-foreground">{t("grid.noValidItem")}</p>
          </div>
        )}
      </div>

      {/* THE TRIAGE. One question, one click, before anything is revealed — which is what
          gives the evaluation a quality signal for BOTH cards instead of a score for one of
          them written by somebody who already knew which it was. */}
      {hasItem ? (
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
    </article>
  );
}

/**
 * The blind half of a session: the question, the two cards, the choice.
 *
 * It draws nothing after the reveal — that is `RevealPanel`'s — so nothing in here can
 * know an arm, and the only colour it spends is `--attention` on what is still owed.
 */
export function ComparisonGrid({
  positions,
  profile,
  itemType,
  triage,
  instruments,
  onChoose,
  onTriage,
  onDecline,
  onRead,
  pending,
}: {
  positions: EvaluationPosition[];
  profile: ExemplarsProfile;
  itemType: string;
  triage: Record<string, TriageValue>;
  instruments: Instruments;
  onChoose: (choice: number | null, comment?: string) => void;
  onTriage: (position: number, value: TriageValue) => void;
  onDecline: () => void;
  onRead: (position: number) => void;
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
          the task rather than to the card, so one copy per card would only be noise. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border border-border border-l-[3px] border-l-primary bg-card px-4 py-3 shadow-sm">
        <p className="text-body">
          <strong>
            {t("grid.forEach", { question: instruments.triage.question.toLowerCase() })}
          </strong>{" "}
          <span className="text-muted-foreground">{instruments.triage.hint}</span>
        </p>
        <p className="ml-auto text-small nums whitespace-nowrap text-muted-foreground">
          {t("grid.answered", { answered: answered.length, total: answerable.length })}
        </p>
      </div>

      <div className={cn("grid grid-cols-1 items-stretch gap-4", columnsFor(positions.length))}>
        {positions.map((position) => (
          <ProposalCard
            key={position.position}
            position={position}
            profile={profile}
            itemType={itemType}
            triage={triage[String(position.position)]}
            instruments={instruments}
            onTriage={(value) => onTriage(position.position, value)}
            onRead={() => onRead(position.position)}
            pending={pending}
          />
        ))}
      </div>

      {/* THE CHOICE. Sticky to the foot of the window, so it stays reachable however tall
          the cards grow now that they do not scroll inside. Drawn from the first second so
          the shape of the task is visible, and inert until both are answered so the order
          is not a rule anybody has to be told. Forcing a pick between two bad ones turns
          noise into signal. */}
      <div className="sticky bottom-0 z-10 space-y-3 border border-border bg-card p-3.5 shadow-overlay">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-heading font-semibold">
            {t("grid.whichWouldYouUse")}
            {!complete ? (
              <span className="ml-2 text-body font-normal text-muted-foreground">
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

      {/* The way out for somebody outside this subject: quiet, at the edge, never competing
          with the task, and never dressed as a failure. With evaluators drawn from
          different subjects it is a real answer, and the evaluation wants it told. */}
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
    </div>
  );
}

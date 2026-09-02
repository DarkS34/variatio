import { Check, ChevronRight, CircleSlash, Maximize2 } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ItemChecks, ItemFields } from "@/features/run/ResultCard";
import { duration } from "@/lib/format";
import { itemTypeOf } from "@/lib/profile";
import type { ExemplarsProfile } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ARM_META, letterFor } from "./arms";
import { RubricForm } from "./RubricForm";
import type {
  EvaluationDetail,
  EvaluationPosition,
  EvaluationRating,
  Instruments,
  TriageValue,
} from "./types";
import { useT } from "@/lib/i18n";

/**
 * The moment the screen goes from grey to colour.
 *
 * The reveal is irreversible by design: being able to re-choose after seeing the origins
 * would mean the datum was never blind. So this panel only tells; it never offers a way
 * back.
 *
 * ONE ROW PER PROPOSAL, AND ONLY ONE. The old screen kept the three full cards on screen
 * and drew a second set of three under them — the identity, the description, the checks,
 * the prompt — so every proposal was on screen twice and the rubric was squeezed into the
 * half column left over. Here the identity is a row: the letter in its arm's colour, what
 * you said about it, the model and the time, a way to read it in full and a fold for the
 * technical detail. What is being RATED, the system's, gets a card of its own beside the
 * questions about it.
 */
function OriginRow({
  position,
  chosen,
  said,
  onRead,
}: {
  position: EvaluationPosition;
  chosen: boolean;
  said: string | undefined;
  onRead: () => void;
}) {
  const { t, plural } = useT();
  const [open, setOpen] = useState(false);
  const meta = position.arm ? ARM_META[position.arm] : null;
  if (!meta) return null;

  return (
    <div
      className="border bg-card"
      style={{ borderColor: `color-mix(in oklch, ${meta.colour} 40%, transparent)` }}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 py-2">
        <span
          className="flex size-7 shrink-0 items-center justify-center font-mono text-body font-semibold"
          style={{ backgroundColor: meta.colour, color: "var(--background)" }}
        >
          {letterFor(position.position)}
        </span>
        <span className="text-body font-medium">{t(meta.labelKey)}</span>
        {chosen ? (
          <Badge variant="default" mark={<Check />}>
            {t("reveal.chosen")}
          </Badge>
        ) : null}
        {position.status !== "ok" ? (
          <Badge variant={position.status === "unavailable" ? "outline" : "attention"}>
            {position.status === "unavailable" ? t("reveal.unavailable") : t("reveal.noValidItem")}
          </Badge>
        ) : null}
        {said ? (
          <span className="text-small text-muted-foreground">
            {t("grid.youSaid")} <strong className="font-semibold text-foreground">{said}</strong>
          </span>
        ) : null}
        <span className="ml-auto flex items-center gap-3 font-mono text-small text-muted-foreground">
          <span className="hidden sm:inline">{position.model || "—"}</span>
          <span className="nums">{duration(position.elapsed_ms)}</span>
        </span>
        {position.item ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground"
            onClick={onRead}
            aria-label={t("focus.read", { letter: letterFor(position.position) })}
          >
            <Maximize2 />
            {t("reveal.read")}
          </Button>
        ) : null}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex items-center gap-1.5 text-small font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
          {t("reveal.detail")}
        </button>
      </div>

      {open ? (
        <div className="space-y-3 border-t border-border bg-muted/30 p-3">
          <p className="text-small leading-relaxed text-muted-foreground">
            {t(meta.descriptionKey)}
          </p>
          <p className="font-mono text-small text-muted-foreground sm:hidden">
            {position.model || "—"}
          </p>
          {position.error ? <p className="text-small text-attention">{position.error}</p> : null}
          <TechnicalDetail position={position} />
          {position.exemplar_ids && position.exemplar_ids.length > 0 ? (
            <p className="font-mono text-small text-muted-foreground">
              {plural("reveal.examplesFromBank", position.exemplar_ids.length)} ·{" "}
              {position.exemplar_ids.join(" · ")}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** The checks and the exact prompt, folded: what a proposal was given and what the
 *  pipeline could verify about what came back. Shared by the row and the system's card. */
function TechnicalDetail({ position }: { position: EvaluationPosition }) {
  const { t, plural } = useT();
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-2">
      {position.checks ? (
        <ItemChecks checks={position.checks} retried={position.retried} detail />
      ) : null}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 text-left text-small font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        {t("reveal.seePrompt")}
        <span className="ml-auto font-mono nums">
          {position.exemplar_ids && position.exemplar_ids.length > 0
            ? plural("reveal.examplesFromBank", position.exemplar_ids.length)
            : t("reveal.noExamples")}
        </span>
      </button>
      {open ? <CodeBlock code={position.prompt || t("reveal.noPrompt")} maxHeight="20rem" /> : null}
    </div>
  );
}

/**
 * What the rubric is about, beside the rubric.
 *
 * The four scales describe the system's proposal whichever one was chosen, and the old
 * screen asked them three screens below the exercise they were about. The technical
 * detail sits at the foot of this one card, because it is about this one proposal.
 */
function SystemCard({
  position,
  profile,
  itemType,
  onRead,
}: {
  position: EvaluationPosition;
  profile: ExemplarsProfile;
  itemType: string;
  onRead: () => void;
}) {
  const { t } = useT();
  const meta = ARM_META.system;
  return (
    <section
      className="flex flex-col border bg-card shadow-sm"
      style={{ borderColor: `color-mix(in oklch, ${meta.colour} 40%, transparent)` }}
    >
      <header className="flex items-center gap-2.5 border-b border-border px-4 py-3">
        <span
          className="flex size-7 shrink-0 items-center justify-center font-mono text-body font-semibold"
          style={{ backgroundColor: meta.colour, color: "var(--background)" }}
        >
          {letterFor(position.position)}
        </span>
        <h2 className="text-heading font-semibold">{t("reveal.systemWrote")}</h2>
        {position.item ? (
          <Button
            variant="ghost"
            size="icon-sm"
            className="ml-auto text-muted-foreground"
            onClick={onRead}
            aria-label={t("focus.read", { letter: letterFor(position.position) })}
            title={t("focus.read", { letter: letterFor(position.position) })}
          >
            <Maximize2 />
          </Button>
        ) : null}
      </header>
      <div className="flex-1 space-y-3 p-4">
        {position.item ? (
          <ItemFields item={position.item} spec={itemTypeOf(profile, { item_type: itemType })} />
        ) : (
          <div className="flex min-h-32 flex-col items-center justify-center gap-2 text-center">
            <CircleSlash className="size-5 text-muted-foreground/60" />
            <p className="max-w-56 text-body text-muted-foreground">{t("grid.noValidItem")}</p>
            {position.error ? (
              <p className="max-w-64 text-small text-muted-foreground/80">{position.error}</p>
            ) : null}
          </div>
        )}
      </div>
      <div className="border-t border-border bg-muted px-4 py-3">
        <TechnicalDetail position={position} />
      </div>
    </section>
  );
}

export function RevealPanel({
  detail,
  profile,
  instruments,
  pending,
  onSave,
  onSkip,
  onRead,
}: {
  detail: EvaluationDetail;
  profile: ExemplarsProfile;
  instruments: Instruments;
  pending: boolean;
  onSave: (rating: Partial<EvaluationRating>) => void;
  onSkip: () => void;
  onRead: (position: number) => void;
}) {
  const { t } = useT();
  const { session, positions } = detail;
  const chosenMeta = session.choice_arm ? ARM_META[session.choice_arm] : null;
  const system = positions.find((position) => position.arm === "system") ?? null;
  const labelOf = (value: TriageValue | undefined) =>
    instruments.triage.options.find((option) => option.value === value)?.label;

  return (
    <div className="animate-fade-in space-y-5">
      {/* THE RESULT, IN ONE LINE. `--study` is the evaluation's own token, and this band
          is the one place on the screen that is about the study rather than about an
          exercise. */}
      <section className="flex flex-wrap items-center gap-x-4 gap-y-2 border border-border border-l-[3px] border-l-study bg-card px-4 py-3 shadow-sm">
        <div className="min-w-0">
          <p className="text-micro font-condensed text-muted-foreground uppercase">
            {t("reveal.title")}
          </p>
          <h2 className="text-title">
            {session.choice === null ? (
              t("reveal.choseNone")
            ) : (
              <>
                {t("reveal.choseLetter", { letter: letterFor(session.choice) })} —{" "}
                <span style={{ color: chosenMeta?.colour }}>
                  {chosenMeta ? t(chosenMeta.labelKey) : ""}
                </span>
              </>
            )}
          </h2>
          {/* Said after choosing, never before: it is identical for the three proposals, so
              it gives none away, but knowing it beforehand changes how what is on screen is
              read — and the draw existed precisely to measure without that bias. */}
          <p className="mt-1 text-small text-muted-foreground">
            {session.think ? t("reveal.reasoningBody") : t("reveal.noReasoningBody")}
          </p>
        </div>
        <p className="ml-auto font-mono text-small text-muted-foreground">
          {session.think ? t("reveal.withReasoning") : t("reveal.withoutReasoning")} ·{" "}
          {t("reveal.seed", { seed: session.seed ?? "—" })}
        </p>
      </section>

      <div className="space-y-2">
        {positions.map((position) => (
          <OriginRow
            key={position.position}
            position={position}
            chosen={session.choice === position.position}
            said={labelOf(session.triage[String(position.position)])}
            onRead={() => onRead(position.position)}
          />
        ))}
      </div>

      {/* TWO TRACKS: what is being rated, beside the questions about it. A session nobody
          could judge has nothing for the rubric to describe, so the pair is not drawn. */}
      {session.declined_at || !system ? null : (
        <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-2">
          <SystemCard
            position={system}
            profile={profile}
            itemType={session.item_type}
            onRead={() => onRead(system.position)}
          />
          <RubricForm
            rating={session.rating}
            instruments={instruments}
            pending={pending}
            onSave={onSave}
            onSkip={onSkip}
          />
        </div>
      )}
    </div>
  );
}

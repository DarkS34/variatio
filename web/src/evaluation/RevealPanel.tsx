import { Check, CircleSlash, Maximize2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ItemChecks, ItemFields } from "@/features/generate/ResultCard";
import { duration } from "@/lib/format";
import { itemTypeOf } from "@/lib/profile";
import type { ExemplarsProfile } from "@/lib/types";

import { ARM_META, letterFor } from "./arms";
import { RubricForm } from "./RubricForm";
import { TaggedConcepts } from "./TaggedConcepts";
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
 * ONE CARD PER PROPOSAL, AND ONLY ONE. The old screen kept the three full cards on screen
 * and drew a second set of three under them — the identity, the description, the checks,
 * the prompt — so every proposal was on screen twice and the rubric was squeezed into the
 * half column left over. Here the identity is a card, COLLAPSED: the letter in its arm's
 * colour, what you said about it, the model and the time, and ONE way to read it in full —
 * the reading dialog, which after the reveal also says where the proposal came from. What
 * is being RATED, the system's, gets a card of its own beside the questions about it.
 *
 * THEY ARE THREE COLUMNS AND NOT THREE ROWS (2026-09-04, explicit user request: «lo mismo
 * pero en columnas, para que no se diferencie tanto»). The blind half draws three columns
 * and the reveal is the same three proposals a second later; turning them on their side at
 * that exact moment made the screen look like it had become something else, when all that
 * happened is that each card lost its body and gained a name.
 */
function OriginCard({
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
  const { t } = useT();
  const meta = position.arm ? ARM_META[position.arm] : null;
  if (!meta) return null;

  return (
    <div
      className="flex h-full flex-col border bg-card"
      style={{ borderColor: `color-mix(in oklch, ${meta.colour} 40%, transparent)` }}
    >
      <div className="space-y-2 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
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
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {said ? (
            <span className="text-small text-muted-foreground">
              {t("grid.youSaid")} <strong className="font-semibold text-foreground">{said}</strong>
            </span>
          ) : null}
          <span className="ml-auto flex items-center gap-3 font-mono text-small text-muted-foreground">
            <span className="truncate">{position.model || "—"}</span>
            <span className="nums">{duration(position.elapsed_ms)}</span>
          </span>
        </div>

        {/* ONE BUTTON, BOTTOM RIGHT (2026-09-04, explicit user request). «Leer» opened the
            reading dialog and «Detalle» unfolded the arm's description, the checks and the
            retrieved fragments in place; the dialog carries all of that now once the
            session is revealed, so the two doors were one door with two names. */}
        <div className="flex justify-end">
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
        </div>
      </div>

      {/* THE GRAPH'S OWN READING OF THIS PROPOSAL, at the foot of the card it is about. It
          is the third thing the reveal uncovers, after which arm wrote the exercise and
          with which model: what the exercise turned out to be ABOUT, and whether it went
          where the commission said not to.

          A rule and NOT the muted band the system's checks sit on: `--secondary` and
          `--muted` are the same value, so a `secondary` badge — the one the bank draws a
          non-primary concept with — paints itself invisible on it. On the card's own
          ground the three variants read as the bank's three. */}
      {position.tagging ? (
        <div className="mt-auto border-t border-border px-3 py-2.5">
          <TaggedConcepts tagging={position.tagging} />
        </div>
      ) : null}
    </div>
  );
}

/**
 * What the rubric is about, beside the rubric.
 *
 * The four scales describe the system's proposal whichever one was chosen, and the old
 * screen asked them three screens below the exercise they were about. A check the
 * pipeline raised sits at the foot of this one card, because it is about this one
 * proposal; with nothing raised the foot is not drawn.
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
      {position.checks && position.checks.flags.length > 0 ? (
        <div className="border-t border-border bg-muted px-4 py-3">
          <ItemChecks checks={position.checks} />
        </div>
      ) : null}
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
      {/* THE THREE, IN THE ORDER THE BLIND HALF DREW THEM. What each one was is the answer
          to the question the cards above just asked, so it comes first and the verdict
          comes after — it was the other way round until 2026-09-04 (explicit user
          request), which put the result of the choice above the things it was a choice
          between.

          They STRETCH to one height, and that is what puts the three tagging feet on one
          line: with `items-start` a card carrying four concepts pushed its own foot down
          and the row read as three unrelated blocks rather than as one comparison. */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {positions.map((position) => (
          <OriginCard
            key={position.position}
            position={position}
            chosen={session.choice === position.position}
            said={labelOf(session.triage[String(position.position)])}
            onRead={() => onRead(position.position)}
          />
        ))}
      </div>

      {/* THE RESULT, IN ONE LINE. `--evaluation` is the evaluation's own token, and this band
          is the one place on the screen that is about the evaluation rather than about an
          exercise. It is the verdict and nothing else (2026-09-04, explicit user request):
          the eyebrow «De dónde salió cada propuesta» named what the three cards above had
          just said, and «sin razonamiento · semilla N» is provenance of the draw — it is
          still stored on the row and read by the panel, and it told the evaluator nothing
          they could use. */}
      <section className="border border-border border-l-[3px] border-l-evaluation bg-card px-4 py-3 shadow-sm">
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
      </section>

      {/* A SECOND SECTION, WITH A TITLE OF ITS OWN (2026-09-04, explicit user request:
          «necesito que separes aún más»). What is above is the comparison and what is
          below is the rating of ONE proposal — a different question, asked after the
          reveal and optional — and a rule alone did not say so. The head carries the
          sentence the rubric card used to open with, so the card no longer repeats it. */}
      {session.declined_at || !system ? null : (
        <div className="border-t border-border pt-5">
          <h2 className="text-title">{t("reveal.rubricSection.title")}</h2>
          <p className="mt-1 text-body text-muted-foreground">{t("reveal.rubricSection.body")}</p>
        </div>
      )}

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

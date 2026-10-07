import { ArrowRight, ScanText } from "lucide-react";

import { GuideLink } from "@/components/GuideLink";
import { continueLabel, WayOn } from "@/components/StageGate";
import { Button } from "@/components/ui/button";
import { Alert, EmptyState, Skeleton, Spinner } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";
import { Link } from "@/lib/router";
import { nextStepOf, stepNumber } from "@/lib/steps";
import type { RawKind } from "@/lib/types";
import { useCanEdit } from "@/state/auth";
import { useEngineOffline, useRaw } from "@/state/queries";

import { useStartAllTranscriptions, useTranscriptionSummary } from "./queries";
import { SlotCard } from "./SlotCard";

/**
 * The raw material, as a destination of its own: a document is one row with its state and
 * the two operations on it, and the transcription is a first-class step.
 *
 * It is drawn like the other three steps of the construction — the work starts from the
 * same `EmptyState` with the same `xl` button, the running state is the same progress card
 * with the stop inside it, and the way on is the same `WayOn` beside the title. What has
 * no equivalent on a stage is not invented for it: the empty subject says so through the
 * two dropzones, which are the only "Importar" this screen has.
 *
 * What it must NOT become is a GATE. Transcribing is an accelerator — every builder keeps
 * its own conversion phase — and the copy says so where a person reads it before pressing.
 * That is also why the header offers "Continuar" with documents still unread: withholding
 * it makes the button behave like the gate the copy under it denies.
 */
export function RawScreen() {
  const { t, plural } = useT();
  const raw = useRaw();
  const canEdit = useCanEdit();
  const offline = useEngineOffline();
  const startAll = useStartAllTranscriptions();

  const slots = raw.data?.slots ?? [];
  const summary = useTranscriptionSummary(slots);

  if (raw.isLoading) {
    return (
      <div className="space-y-7">
        <Skeleton className="h-24" />
        <div className="grid gap-7 lg:grid-cols-2">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </div>
    );
  }

  if (!raw.data) {
    return (
      <Alert tone="danger" title={t("raw.unreadable")}>
        <p>{t("raw.noApi")}</p>
      </Alert>
    );
  }

  // Only the origins that hold something: an empty slot has nothing to transcribe, and one
  // already at work answers 409 — which `useStartAllTranscriptions` swallows per slot so
  // the other still starts.
  const stocked: RawKind[] = slots
    .filter((slot) => slot.files.length > 0)
    .map((slot) => slot.kind);

  const blocked = !canEdit ? t("build.readOnly") : offline ? offline : null;

  return (
    <div className="space-y-7">
      {/* The header and the way on, on one line: the title on the left, and on the right —
          where the header left half the screen empty — the button that leaves the step,
          under the eye on arrival and not below every document. It stands on the ground
          like the title beside it, with no block of its own. Below `lg` it goes under the
          title, still above the origins. */}
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between lg:gap-10">
        <header className="min-w-0 space-y-2">
          {/* The same header as the other three: ordinal, title, explanation, guide link.
              This screen does not go through `StageGate` — it writes no artifact and nobody
              approves it — so it repeats the shape by hand, and the ORDINAL is what puts it
              on the path: it is step 1 even though it is not a stage. The title is
              deliberately not `text-display`, or one of the four steps would be the only one
              shouting. */}
          <p className="text-micro text-muted-foreground">{t("nav.stepNumber", { n: stepNumber(0) })}</p>
          <h1 className="font-display font-expanded text-title">{t("nav.step.raw")}</h1>
          <p className="max-w-[74ch] text-body text-muted-foreground">{t("raw.screenIntro")}</p>
          <GuideLink slug="raw" />
        </header>

        {/* `stocked` holds back until both readings have landed, so this does not flash
            during the first second of a load and then change its mind. Not while something
            runs: a building stage offers no way on either. */}
        {summary.stocked && !summary.running ? <RawClosing done={summary.done} /> : null}
      </div>

      {/* THE ONE THING TO DO, IN THE SAME BLOCK A STAGE STARTS FROM. A notice with no
          control while it runs — the stop button is in each origin's progress card, as a
          build's is — and the big button in the middle of an empty block while there is
          something to read. With the subject empty there is nothing here at all: the two
          dropzones below are the action, and a block above them repeating "suelta los
          documentos" said what they already say. */}
      {summary.running ? (
        <Alert tone="info" title={t("transcribe.runningTitle")}>
          <p>{t("transcribe.runningNote")}</p>
        </Alert>
      ) : summary.todo > 0 ? (
        <EmptyState
          icon={<ScanText />}
          title={plural("transcribe.todoTitle", summary.todo)}
          action={
            <Button
              size="xl"
              variant="attention"
              disabled={Boolean(blocked) || startAll.isPending}
              title={blocked ?? undefined}
              onClick={() => startAll.mutate(stocked)}
            >
              {startAll.isPending ? <Spinner /> : <ScanText />}
              {t("transcribe.startAll")}
            </Button>
          }
        >
          {t("transcribe.notAGate")}
        </EmptyState>
      ) : null}

      {startAll.isError ? (
        <p className="text-small text-destructive">{(startAll.error as Error).message}</p>
      ) : null}

      {/* Stretched cells on purpose: an empty origin's dropzone grows to the height of the
          stocked one beside it, which is what makes "importa aquí" the whole card rather
          than a strip at the top of a blank one.

          `grid-cols-1` IS LOAD-BEARING BELOW `lg`, and it is not the same as declaring
          nothing. With no column declared the single implicit track is sized `auto`, whose
          floor is the min-content of the item in it, and a card is a grid item — so it
          carries `min-width: auto` and never shrinks below that floor. Measured on the
          reference subject: the track computed 507.5 px inside a 366 px container, and the
          BODY scrolled sideways by 200 px at 320, 130 at 390 and 90 at 430, which is every
          phone held upright. Tailwind's `grid-cols-1` is `repeat(1, minmax(0, 1fr))`, and
          the 0 is the whole fix. Nothing is lost by it: the card's real min-content is
          247 px, so the content fits and it is the track that was refusing to. */}
      {/* Each origin as tall as what it holds (user's request, 2026-10-08): stretched to the
          taller one, the shorter card ended in a band of nothing under its last document. An
          empty origin keeps the drop zone's own floor (`SlotDropzone`'s `fill`). */}
      <div className="grid grid-cols-1 items-start gap-7 lg:grid-cols-2">
        {slots.map((slot) => (
          <SlotCard key={slot.kind} slot={slot} extensions={raw.data.supported_extensions} />
        ))}
      </div>
    </div>
  );
}

/**
 * The way on: one line of state and "Continuar", beside the title.
 *
 * Two lines for two states — everything read, or something still unread — and the same
 * "Continuar" under both, because reading is not a gate. It is the coral only once
 * everything is read: with documents unread the block under the header holds the screen's
 * one coral button, a hand's width away, and two of them asked for two things at once.
 * No sentence of explanation: the origins' ticks say the documents are read, and the block
 * with the reading button says a step reads on its own what it lacks. There is no "Quiero
 * corregir algo" here: a document is corrected on its own row, and the step as a whole has
 * nothing to unlock.
 */
function RawClosing({ done }: { done: boolean }) {
  const { t } = useT();
  const next = nextStepOf(null);
  return (
    <WayOn caption={t(done ? "raw.done.title" : "raw.next.title")}>
      <Link to={next.path}>
        <Button variant={done ? "attention" : "outline"} size="xl">
          {continueLabel(next, t)}
          <ArrowRight />
        </Button>
      </Link>
    </WayOn>
  );
}

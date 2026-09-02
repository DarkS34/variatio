import { ArrowRight, ScanText } from "lucide-react";

import { GuideLink } from "@/components/GuideLink";
import { ClosingSection, continueLabel } from "@/components/StageGate";
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
 * THE RAW MATERIAL, AS A DESTINATION OF ITS OWN.
 *
 * It was the last card of the panel until now, and that placement was a compromise between
 * two true things: the raw documents are touched once at the start of an instance's life,
 * and they are also the thing that decides how long every build takes. Folded into a card
 * it could only serve the first. As a screen it can serve both — a document is one row
 * with its state and the two operations on it, and the transcription is a first-class step
 * rather than a disclosure inside a disclosure.
 *
 * IT IS DRAWN LIKE THE OTHER THREE STEPS (2026-09-02, explicit user request: one
 * convention for buttons, notices and blocks across the whole construction). The work of
 * the step — reading the documents — used to be a small button in the corner of a notice,
 * where a stage draws its «Comenzar construcción» as a big button in the middle of an
 * empty block; it is that block now. The running state is a notice with no control plus
 * the same progress card a build draws, with the stop button inside the card; and the
 * foot is `ClosingSection`, the block every stage ends with. What has NO equivalent on a
 * stage is not invented for it: the empty subject says so through the two dropzones, which
 * are the only «Importar» this screen has.
 *
 * What this screen must NOT become is a gate. Transcribing is an accelerator: every
 * builder keeps its own conversion phase, so nothing here is ever a precondition for
 * anything, and the copy says so where a person can read it before pressing. That is also
 * why the foot offers «Continuar» with documents still unread — the way on is offered on a
 * stage whatever its state, and hiding it here until everything was read made the foot
 * behave like the gate the copy above it denies.
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
      <div className="space-y-6">
        <Skeleton className="h-24" />
        <div className="grid gap-4 lg:grid-cols-2">
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
    <div className="space-y-6">
      <header className="space-y-2">
        {/* LA MISMA CABECERA QUE LAS OTRAS TRES: ordinal, título, explicación, enlace a
            la guía. Esta pantalla no pasa por `StageGate` — no escribe artefacto y nadie
            la aprueba — así que la repite a mano, y el ordinal es lo que la mete en el
            recorrido: es el Paso 1 aunque no sea una etapa. El título deja de ser
            `text-display`: cuatro pasos con la misma pinta, y este era el único que
            gritaba. */}
        <p className="text-micro text-muted-foreground">{t("nav.stepNumber", { n: stepNumber(0) })}</p>
        <h1 className="text-title">{t("nav.step.raw")}</h1>
        <p className="max-w-[74ch] text-body text-muted-foreground">{t("raw.screenIntro")}</p>
        <GuideLink slug="raw" />
      </header>

      {/* THE ONE THING TO DO, IN THE SAME BLOCK A STAGE STARTS FROM. A notice with no
          control while it runs — the stop button is in each origin's progress card, as a
          build's is — and the big button in the middle of an empty block while there is
          something to read. With the subject empty there is nothing here at all: the two
          dropzones below are the action, and a block above them repeating «suelta los
          documentos» said what they already say. */}
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
          stocked one beside it, which is what makes «importa aquí» the whole card rather
          than a strip at the top of a blank one. */}
      <div className="grid items-stretch gap-4 lg:grid-cols-2">
        {slots.map((slot) => (
          <SlotCard key={slot.kind} slot={slot} extensions={raw.data.supported_extensions} />
        ))}
      </div>

      {/* `stocked` holds back until both readings have landed, so this does not flash during
          the first second of a load and then change its mind. Not while something runs: a
          building stage has no closing block either. */}
      {summary.stocked && !summary.running ? <RawClosing done={summary.done} /> : null}
    </div>
  );
}

/**
 * The way on, in the block every step closes with.
 *
 * Two sentences for two states — everything read, or something still unread — and the same
 * «Continuar» under both, because reading is not a gate. There is no «Quiero corregir algo»
 * here: a document is corrected on its own row, and the step as a whole has nothing to
 * unlock.
 */
function RawClosing({ done }: { done: boolean }) {
  const { t } = useT();
  const next = nextStepOf(null);
  return (
    <ClosingSection
      title={t(done ? "raw.done.title" : "raw.next.title")}
      body={
        done ? t("raw.done.body", { next: t(next.labelKey) }) : t("raw.next.body")
      }
    >
      <Link to={next.path}>
        <Button variant="attention" size="xl">
          {continueLabel(next, t)}
          <ArrowRight />
        </Button>
      </Link>
    </ClosingSection>
  );
}

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
 * The raw material, as a destination of its own: a document is one row with its state and
 * the two operations on it, and the transcription is a first-class step.
 *
 * It is drawn like the other three steps of the construction — the work starts from the
 * same `EmptyState` with the same `xl` button, the running state is the same progress card
 * with the stop inside it, and the foot is `ClosingSection`. What has no equivalent on a
 * stage is not invented for it: the empty subject says so through the two dropzones, which
 * are the only "Importar" this screen has.
 *
 * What it must NOT become is a GATE. Transcribing is an accelerator — every builder keeps
 * its own conversion phase — and the copy says so where a person reads it before pressing.
 * That is also why the foot offers "Continuar" with documents still unread: withholding it
 * makes the foot behave like the gate the copy above it denies.
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
        {/* The same header as the other three: ordinal, title, explanation, guide link.
            This screen does not go through `StageGate` — it writes no artifact and nobody
            approves it — so it repeats the shape by hand, and the ORDINAL is what puts it on
            the path: it is step 1 even though it is not a stage. The title is deliberately
            not `text-display`, or one of the four steps would be the only one shouting. */}
        <p className="text-micro text-muted-foreground">{t("nav.stepNumber", { n: stepNumber(0) })}</p>
        <h1 className="text-title">{t("nav.step.raw")}</h1>
        <p className="max-w-[74ch] text-body text-muted-foreground">{t("raw.screenIntro")}</p>
        <GuideLink slug="raw" />
      </header>

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
 * "Continuar" under both, because reading is not a gate. There is no "Quiero corregir algo"
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

import { ArrowRight, ScanText } from "lucide-react";

import { GuideLink } from "@/components/GuideLink";
import { Button } from "@/components/ui/button";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";
import { Link } from "@/lib/router";
import { nextStepOf } from "@/lib/steps";
import type { RawKind } from "@/lib/types";
import { useCanEdit } from "@/state/auth";
import { useEngineOffline, useRaw } from "@/state/queries";

import { useStartAllTranscriptions, useTranscribeRun, useTranscriptionSummary } from "./queries";
import { SlotCard } from "./SlotCard";
import { CancelButton } from "@/components/CancelButton";

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
 * The colour budget is one `--attention`, and it is the alert at the top: import, or
 * transcribe, or nothing. Everything else on the screen reports, achromatically.
 *
 * What this screen must NOT become is a gate. Transcribing is an accelerator: every
 * builder keeps its own conversion phase, so nothing here is ever a precondition for
 * anything, and the copy says so where a person can read it before pressing.
 *
 * What it does say, at the foot and only once there is nothing left to do here, is WHERE
 * TO GO (2026-09-02, explicit user request): the same block every stage closes with, with
 * the same big «Continuar». It is not a «todo leído» notice — that was deleted and stays
 * deleted — because what it reports is the next move, not the state.
 */
export function RawScreen() {
  const { t, plural } = useT();
  const raw = useRaw();
  const canEdit = useCanEdit();
  const offline = useEngineOffline();
  const startAll = useStartAllTranscriptions();

  const slots = raw.data?.slots ?? [];
  const summary = useTranscriptionSummary(slots);
  const corpusRun = useTranscribeRun("corpus");
  const exemplarsRun = useTranscribeRun("exemplars");

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

  // BOTH of them, not the first that is alive: «Transcribir todo» starts one job per
  // origin, so a stop that reached one of the two left the other running and the person
  // pressed «Detener» twice for one press of «Transcribir todo».
  const live = [corpusRun, exemplarsRun].filter(
    (run) => run?.job?.status === "running" || run?.job?.status === "queued",
  );

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
        <p className="text-micro text-muted-foreground">{t("nav.stepNumber", { n: 1 })}</p>
        <h1 className="text-title">{t("nav.step.raw")}</h1>
        <p className="max-w-[74ch] text-body text-muted-foreground">{t("raw.screenIntro")}</p>
        <GuideLink slug="raw" />
      </header>

      {/* THE ONE BLUE THING ON THE SCREEN, and only when there is something to press. */}
      {summary.running ? (
        <Alert
          tone="info"
          title={t("transcribe.runningTitle")}
          action={live.length > 0 ? <CancelButton run={live} word="stop" /> : undefined}
        >
          <p>{t("transcribe.runningNote")}</p>
        </Alert>
      ) : summary.empty ? (
        <Alert tone="attention" title={t("raw.nothingYet")}>
          <p>{t("raw.nothingYetBody")}</p>
        </Alert>
      ) : summary.todo > 0 ? (
        <Alert
          tone="attention"
          title={plural("transcribe.todoTitle", summary.todo)}
          action={
            <Button
              size="sm"
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
          <p>{t("transcribe.notAGate")}</p>
        </Alert>
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

      {/* `done` holds back until both readings have landed, so this does not flash during
          the first second of a load and then vanish. */}
      {summary.done ? <RawDone /> : null}
    </div>
  );
}

/** The way on: both origins hold something and every document is read. */
function RawDone() {
  const { t } = useT();
  const next = nextStepOf(null);
  return (
    <section className="border border-border bg-card p-4 sm:p-5">
      <h2 className="text-heading font-semibold">{t("raw.done.title")}</h2>
      <p className="mt-1 max-w-[74ch] text-body text-muted-foreground">
        {t("raw.done.body", { next: t(next.labelKey) })}
      </p>
      <div className="mt-4">
        <Link to={next.path}>
          <Button variant="attention" size="xl">
            {next.number === null
              ? t("stage.continueGenerate")
              : t("stage.continue", { n: next.number })}
            <ArrowRight />
          </Button>
        </Link>
      </div>
    </section>
  );
}

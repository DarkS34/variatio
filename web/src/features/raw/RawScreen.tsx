import { ScanText } from "lucide-react";

import { GuideLink } from "@/components/GuideLink";
import { Button } from "@/components/ui/button";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";
import type { RawKind } from "@/lib/types";
import { useCanEdit } from "@/state/auth";
import { useEngineOffline, useRaw } from "@/state/queries";

import { ContextCard } from "@/features/context/ContextCard";
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
 * with its size, its pages, its state and the two operations on it, and the transcription
 * is a first-class step rather than a disclosure inside a disclosure.
 *
 * The colour budget is one `--attention`, and it is the alert at the top: import, or
 * transcribe, or nothing. Everything else on the screen reports, achromatically. The
 * per-origin buttons are therefore `default` — the global one in the alert is the frontier
 * action, and two ultramarine buttons would be none.
 *
 * What this screen must NOT become is a gate. Transcribing is an accelerator: every
 * builder keeps its own conversion phase, so nothing here is ever a precondition for
 * anything, and the copy says so where a person can read it before pressing.
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
      ) : summary.known && summary.files > 0 ? (
        <Alert tone="settled" title={t("transcribe.allUpToDate")}>
          <p>{plural("transcribe.allUpToDateBody", summary.done)}</p>
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

      {/* WHAT THIS SUBJECT IS ABOUT, IN PROSE — and this screen is where it belongs.
          Its home was the panel, and it went down with it when the bar became the chain,
          which left the one paragraph every prompt interpolates with nowhere to be read or
          corrected. Here it keeps every property it had: it is not a stage, nobody
          approves it, and it is upstream of more than one thing at once — the same three
          reasons the raw documents are on a screen rather than on the rail. Last on the
          page, because the two builds are what write it. */}
      <ContextCard />
    </div>
  );
}

import { Ban, EyeOff, Lock, Plus, Scale } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useActiveRun } from "@/components/RunDrawer";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Alert, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { EMPTY_FORM, type FormState } from "@/features/run/commission";
import { GenerateForm } from "@/features/run/GenerateForm";
import { ApiError } from "@/lib/api";
import { duration } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useCancelJob, useElapsed, useKg, useKgGraph, usePipeline, useProfile } from "@/state/queries";

import { toEvaluationParams } from "./commission";
import { ComparisonGrid } from "./ComparisonGrid";
import { FairnessTable } from "./FairnessTable";
import { QueueTab } from "./QueueTab";
import { RevealPanel } from "./RevealPanel";
import { RubricForm } from "./RubricForm";
import { SessionsTable } from "./SessionsTable";
import { letterFor } from "./arms";
import {
  useChooseProposal,
  useDeclineSession,
  useEvaluation,
  useEvaluations,
  useLaunchEvaluation,
  useRateSession,
  useTriageProposal,
} from "./queries";

const GUARDRAIL_ERROR = "no han pasado la revisión";

/**
 * While it runs, the screen deliberately says less than the Generate screen does.
 *
 * The run drawer would give the blinding away — the token stream, the few-shot, the
 * logs — so the server does not publish any of it during an evaluation. Saying so out
 * loud matters: silence that is not explained reads as an app that has frozen.
 */
function Running({ onCancel, cancelling }: { onCancel: () => void; cancelling: boolean }) {
  const run = useActiveRun();
  const step = useMemo(() => run?.steps.find((s) => s.id === "eval.arms"), [run]);
  const elapsed = useElapsed(run?.job?.started_at ?? null, true);
  const done = step?.current ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-3 shadow-sm">
        <Spinner />
        <div className="min-w-0 flex-1">
          <p className="text-body font-medium">
            Preparando las tres propuestas
            <span className="ml-2 nums text-muted-foreground">{done} de 3</span>
          </p>
          <p className="text-small nums text-muted-foreground">{duration(elapsed)}</p>
        </div>
        <Progress value={done} max={3} className="hidden w-40 sm:block" />
        <Button variant="outline" size="sm" onClick={onCancel} disabled={cancelling}>
          <Ban />
          Cancelar
        </Button>
      </div>

      <p className="flex items-start gap-1.5 text-small text-muted-foreground">
        <EyeOff className="mt-0.5 size-3.5 shrink-0" />
        Durante una comparación se ocultan el registro y el detalle técnico: dirían de qué
        arquitectura sale cada propuesta antes de que la leas.
      </p>

      <div className="grid items-stretch gap-4 xl:grid-cols-3">
        {[1, 2, 3].map((position) => (
          <div
            key={position}
            className="flex h-64 flex-col overflow-hidden rounded-xl border border-border bg-card"
          >
            <div className="flex items-center gap-2.5 border-b border-border px-3 py-2.5">
              <span className="flex size-8 items-center justify-center rounded-lg bg-muted font-mono text-heading text-muted-foreground">
                {letterFor(position)}
              </span>
              <span className="text-body text-muted-foreground">Propuesta {letterFor(position)}</span>
            </div>
            <div className="flex-1 space-y-2 p-3">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-11/12" />
              <Skeleton className="h-3 w-4/5" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * The three sub-tabs, in the order the work happens in.
 *
 * The queue comes first because that is what somebody handed this evaluator; asking for an
 * exercise yourself is the second thing, and a student never sees it — the form speaks the
 * system's vocabulary (concepts of the graph, modalities, a curriculum), which is not
 * theirs to know.
 */
type Tab = "queue" | "compose" | "history";

export function EvaluationScreen() {
  const pipeline = usePipeline();
  const profileQuery = useProfile();
  const kg = useKg();
  const kgGraph = useKgGraph();
  const listing = useEvaluations();
  const launch = useLaunchEvaluation();
  const choose = useChooseProposal();
  const triage = useTriageProposal();
  const decline = useDeclineSession();
  const rate = useRateSession();
  const cancel = useCancelJob();
  const run = useActiveRun();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("queue");
  const detail = useEvaluation(sessionId);

  const profile = profileQuery.data?.profile ?? null;
  const unlocked = pipeline.data?.generation_unlocked ?? false;
  const external = listing.data?.external;

  // ONLY A COMPARISON THIS PERSON HAS TO JUDGE. The run drawer is global, so a batch an
  // administrator ordered from the panel arrives here as the active job like any other —
  // and this screen used to take it: it showed «Preparando las tres propuestas», then
  // opened the finished session for answering. Stock is nobody's to judge until it is
  // assigned, so the flag the panel stamps on the job is what this screen filters on.
  const isEvaluation = run?.job?.kind === "evaluate" && run?.job?.params?.stock !== true;
  const running = isEvaluation && (run?.job?.status === "running" || run?.job?.status === "queued");

  // The job result carries the session id and nothing else — the proposals are fetched
  // separately, from the endpoint that knows what it is allowed to show.
  const producedId = isEvaluation ? (run?.job?.result?.session_id as string | undefined) : undefined;

  useEffect(() => {
    if (producedId) {
      setSessionId(producedId);
    }
  }, [producedId]);

  const blocked = useMemo(() => {
    if (!isEvaluation || run?.job?.status !== "failed") return null;
    const error = run?.job?.error ?? "";
    return error.includes(GUARDRAIL_ERROR) ? error.replace(/^\w+Error:\s*/, "") : null;
  }, [isEvaluation, run]);

  // Instructions the judge refused come back to the form that wrote them, not to the queue:
  // the message is about text that is still on screen there and nowhere else.
  useEffect(() => {
    if (blocked) setTab("compose");
  }, [blocked]);

  const gone = detail.error instanceof ApiError && detail.error.status === 404;
  useEffect(() => {
    if (gone) {
      setSessionId(null);
    }
  }, [gone]);

  if (profileQuery.isLoading || kg.isLoading || pipeline.isLoading) {
    return <Skeleton className="h-96" />;
  }

  const session = detail.data?.session ?? null;
  const positions = detail.data?.positions ?? [];
  const showComparison = Boolean(sessionId) && !running && positions.length > 0;
  const instruments = listing.data?.instruments;
  const queue = listing.data?.queue;
  // A student never gets the commission form: it asks for concepts of the graph and a
  // modality, which is the system's vocabulary and not theirs.
  const canCompose = instruments?.profile !== "student";

  const closeSession = () => {
    setSessionId(null);
  };

  // Straight on to the next thing somebody handed over, which is what keeps a queue a
  // queue. Falls back to the list when there is nothing left.
  const openNext = () => {
    const next = (queue?.items ?? []).find(
      (item) => !item.decided && !item.declined && item.id !== sessionId,
    );
    setSessionId(next ? next.id : null);
    if (!next) setTab("queue");
  };

  const typeLabel = (key: string) => profile?.item_types?.[key]?.label || key;

  const TABS: { id: Tab; label: string; count?: number; attention?: boolean }[] = [
    { id: "queue", label: "Asignadas", count: queue?.pending ?? 0, attention: true },
    ...(canCompose ? [{ id: "compose" as Tab, label: "Encargo propio" }] : []),
    { id: "history", label: "Mis sesiones", count: listing.data?.total ?? 0 },
  ];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="font-display font-expanded text-display">Evaluación</h1>
        <InfoHint label="Para qué sirve">
          El mismo encargo se resuelve de tres formas: un modelo comercial con un prompt
          corriente, una búsqueda por similitud sobre el banco, y este sistema con el grafo.
          Eliges a ciegas y solo después se revela cuál era cuál.
        </InfoHint>
        {showComparison ? (
          <Button variant="outline" size="sm" className="ml-auto" onClick={closeSession}>
            <Plus />
            Volver a la lista
          </Button>
        ) : null}
      </header>

      {/* The tabs disappear while a session is open, and that is deliberate: a comparison
          is one task with one way out, and offering three destinations beside three cards
          invites leaving it half judged. */}
      {!showComparison && !running ? (
        <div className="flex border-b border-border">
          {TABS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              role="tab"
              aria-selected={tab === entry.id}
              onClick={() => setTab(entry.id)}
              className={cn(
                "-mb-px flex items-center gap-2 border-b-2 px-4 pt-2.5 pb-3 text-body transition-colors",
                tab === entry.id
                  ? "border-primary font-semibold text-foreground"
                  : "border-transparent font-medium text-muted-foreground hover:text-foreground",
              )}
            >
              {entry.label}
              {entry.count ? (
                <span
                  className={cn(
                    "inline-grid h-[18px] min-w-5 place-items-center px-1.5 text-[11px] font-semibold nums",
                    // A count is a fact, not an action: it wears the ink. The one "act
                    // here" colour is spent on the button that opens the next comparison.
                    "bg-primary text-primary-foreground",
                  )}
                >
                  {entry.count}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}

      {!unlocked ? (
        <Alert tone="attention" title="Comparación bloqueada">
          <p className="flex items-center gap-1.5">
            <Lock className="size-3.5" />
            Sin aprobar:{" "}
            {(pipeline.data?.stages ?? [])
              .filter((s) => s.status !== "approved")
              .map((s) => s.label)
              .join(", ")}
          </p>
        </Alert>
      ) : null}

      {isEvaluation && run?.job?.status === "failed" && !blocked ? (
        <Alert tone="danger" title="La comparación falló">
          <p>{run.job.error}</p>
        </Alert>
      ) : null}

      {external && !external.configured ? (
        <Alert tone="attention" title="La propuesta comercial no está configurada">
          <p>{external.reason}</p>
          <p className="mt-1 text-muted-foreground">
            La sesión seguirá adelante y esa propuesta quedará registrada como no
            disponible, que es un dato en sí mismo.
          </p>
        </Alert>
      ) : null}

      {running ? (
        <Running
          onCancel={() => run?.job && cancel.mutate(run.job.id)}
          cancelling={cancel.isPending}
        />
      ) : null}

      {tab === "queue" && !showComparison && !running && queue ? (
        <QueueTab
          items={queue.items}
          pending={queue.pending}
          typeLabel={typeLabel}
          onOpen={(id) => {
            setSessionId(id);
          }}
        />
      ) : null}

      {tab === "compose" && !showComparison && !running && canCompose ? (
        <div className="mx-auto w-full max-w-3xl">
          <GenerateForm
            state={form}
            onChange={setForm}
            profile={profile}
            concepts={kg.data?.concepts ?? []}
            graph={kgGraph.data}
            disabled={!unlocked}
            running={false}
            pending={launch.isPending}
            error={launch.isError ? (launch.error as Error).message : null}
            blockedInstructions={blocked}
            variant="evaluation"
            footnote={<FairnessTable />}
            onLaunch={() => launch.mutate(toEvaluationParams(form))}
            onCancel={() => run?.job && cancel.mutate(run.job.id)}
          />
        </div>
      ) : null}

      {tab === "history" && !showComparison && !running && listing.data ? (
        <SessionsTable
          sessions={listing.data.sessions}
          total={listing.data.total}
          onOpen={(id) => {
            setSessionId(id);
          }}
          onDeleted={(ids) => {
            if (sessionId && ids.includes(sessionId)) closeSession();
          }}
        />
      ) : null}

      {showComparison && profile && session && instruments ? (
        <div className="space-y-5">
          <ComparisonGrid
            positions={positions}
            profile={profile}
            itemType={session.item_type}
            revealed={session.revealed}
            choice={session.choice}
            triage={session.triage}
            instruments={instruments}
            onTriage={(position, value) =>
              triage.mutate({ id: session.id, payload: { position, value } })
            }
            onChoose={(choice, comment) =>
              choose.mutate({ id: session.id, payload: { choice, comment } })
            }
            onDecline={() => decline.mutate({ id: session.id, payload: {} })}
            pending={choose.isPending || triage.isPending || decline.isPending}
          />

          {session.revealed ? (
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
              <RevealPanel detail={detail.data!} />
              <div className="space-y-4">
                {/* The rubric is about the system's variant, so a session nobody could
                    judge has nothing for it to describe. */}
                {session.declined_at ? null : (
                  <RubricForm
                    rating={session.rating}
                    instruments={instruments}
                    pending={rate.isPending}
                    onSave={(rating) => rate.mutate({ id: session.id, payload: rating })}
                    onSkip={openNext}
                  />
                )}
                <Button variant="outline" className="w-full" onClick={openNext}>
                  <Scale />
                  {queue && queue.pending > 0
                    ? `Siguiente de la cola (${queue.pending} pendiente${queue.pending === 1 ? "" : "s"})`
                    : "Volver a la lista"}
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

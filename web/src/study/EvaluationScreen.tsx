import { Ban, EyeOff, Lock, Plus, Scale } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useActiveRun } from "@/components/RunDrawer";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Alert, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { EMPTY_FORM, GenerateForm, toParams, type FormState } from "@/features/run/GenerateForm";
import { duration } from "@/lib/format";
import { useCancelJob, useElapsed, useKg, useKgGraph, usePipeline, useProfile } from "@/state/queries";

import { ComparisonGrid } from "./ComparisonGrid";
import { FairnessTable } from "./FairnessTable";
import { RevealPanel } from "./RevealPanel";
import { RubricForm } from "./RubricForm";
import { SessionsTable } from "./SessionsTable";
import { letterFor } from "./arms";
import type { EvaluationParams } from "./types";
import { useChooseProposal, useEvaluation, useEvaluations, useLaunchEvaluation, useRateSession } from "./queries";

const GUARDRAIL_ERROR = "no han pasado la revisión";

/**
 * The commission, minus `n` and minus `think`.
 *
 * `n` goes because one item per arm is what makes the session the statistical unit, and
 * `think` goes because the session draws it: sending the form's value would hand the
 * evaluator control of the very condition being measured. The server ignores the field
 * too — this is the second lock, not the only one.
 */
function toEvaluationParams(form: FormState): EvaluationParams {
  const { n: _n, think: _think, ...rest } = toParams(form);
  return rest;
}

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

export function EvaluationScreen() {
  const pipeline = usePipeline();
  const profileQuery = useProfile();
  const kg = useKg();
  const kgGraph = useKgGraph();
  const listing = useEvaluations();
  const launch = useLaunchEvaluation();
  const choose = useChooseProposal();
  const rate = useRateSession();
  const cancel = useCancelJob();
  const run = useActiveRun();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [composing, setComposing] = useState(true);
  const detail = useEvaluation(sessionId);

  const profile = profileQuery.data?.profile ?? null;
  const unlocked = pipeline.data?.generation_unlocked ?? false;
  const external = listing.data?.external;

  const isEvaluation = run?.job?.kind === "evaluate";
  const running = isEvaluation && (run?.job?.status === "running" || run?.job?.status === "queued");

  // The job result carries the session id and nothing else — the proposals are fetched
  // separately, from the endpoint that knows what it is allowed to show.
  const producedId = isEvaluation ? (run?.job?.result?.session_id as string | undefined) : undefined;

  useEffect(() => {
    if (producedId) {
      setSessionId(producedId);
      setComposing(false);
    }
  }, [producedId]);

  useEffect(() => {
    if (running) setComposing(false);
  }, [running]);

  const blocked = useMemo(() => {
    if (!isEvaluation || run?.job?.status !== "failed") return null;
    const error = run?.job?.error ?? "";
    return error.includes(GUARDRAIL_ERROR) ? error.replace(/^\w+Error:\s*/, "") : null;
  }, [isEvaluation, run]);

  useEffect(() => {
    if (blocked) setComposing(true);
  }, [blocked]);

  if (profileQuery.isLoading || kg.isLoading || pipeline.isLoading) {
    return <Skeleton className="h-96" />;
  }

  const session = detail.data?.session ?? null;
  const positions = detail.data?.positions ?? [];
  const showComparison = Boolean(sessionId) && !running && positions.length > 0;

  const startAnother = () => {
    setSessionId(null);
    setComposing(true);
  };

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="font-display font-expanded text-display">Comparar tres propuestas</h1>
        <InfoHint label="Para qué sirve">
          El mismo encargo se resuelve de tres formas: un modelo comercial con un prompt
          corriente, una búsqueda por similitud sobre el banco, y este sistema con el grafo.
          Eliges a ciegas y solo después se revela cuál era cuál.
        </InfoHint>
        {showComparison ? (
          <Button variant="outline" size="sm" className="ml-auto" onClick={startAnother}>
            <Plus />
            Otra comparación
          </Button>
        ) : null}
      </header>

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

      {composing && !running ? (
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

      {showComparison && profile && session ? (
        <div className="space-y-5">
          <ComparisonGrid
            positions={positions}
            profile={profile}
            itemType={session.item_type}
            revealed={session.revealed}
            choice={session.choice}
            onChoose={(choice, comment) =>
              choose.mutate({ id: session.id, payload: { choice, comment } })
            }
            pending={choose.isPending}
          />

          {session.revealed ? (
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
              <RevealPanel detail={detail.data!} />
              <div className="space-y-4">
                <RubricForm
                  rating={session.rating}
                  pending={rate.isPending}
                  onSave={(rating) => rate.mutate({ id: session.id, payload: rating })}
                />
                <Button variant="outline" className="w-full" onClick={startAnother}>
                  <Scale />
                  Empezar otra comparación
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {!running && listing.data ? (
        <SessionsTable
          sessions={listing.data.sessions}
          total={listing.data.total}
          onOpen={(id) => {
            setSessionId(id);
            setComposing(false);
          }}
        />
      ) : null}
    </div>
  );
}

import { Ban, Copy, Download, Eraser, Lock, Pencil, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useActiveRun } from "@/components/RunDrawer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { Link } from "@/lib/router";
import type { ExemplarsProfile, ItemChecks } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { RunView } from "@/state/runStore";
import {
  useCancelJob,
  useEngineOffline,
  useKg,
  useKgGraph,
  usePipeline,
  useProfile,
  useSubmitJob,
} from "@/state/queries";

import { EMPTY_FORM, fromParams, toParams, type FormState } from "./commission";
import { takeDraft } from "./draft";
import { GenerateForm, summarize } from "./GenerateForm";
import { ResultCard, download, toMarkdown } from "./ResultCard";
import { RunPanel } from "./RunPanel";

/** The job error the guardrail raises, recognised so it can be shown on its own step. */
const GUARDRAIL_ERROR = "no han pasado la revisión";

interface Result {
  item: Record<string, unknown>;
  item_type?: string;
  thinking?: string;
  checks?: ItemChecks | null;
  retried?: number;
  saved_id?: number | null;
}

export function GenerateScreen() {
  const pipeline = usePipeline();
  const profileQuery = useProfile();
  const kg = useKg();
  const kgGraph = useKgGraph();
  const submit = useSubmitJob();
  const cancel = useCancelJob();
  const offline = useEngineOffline();
  const run = useActiveRun();
  const client = useQueryClient();

  // A draft left by «Generar más como esta» in «Mis variantes» is the form's starting point;
  // it is read once and consumed, so a reload starts clean. It also opens the form: a run
  // from before is still in the store, and its collapsed bar would hide the very commission
  // one came here to launch.
  const [draft] = useState(takeDraft);
  const [form, setForm] = useState<FormState>(draft ?? EMPTY_FORM);
  const [editing, setEditing] = useState(Boolean(draft));

  const profile = profileQuery.data?.profile ?? null;
  const conceptList = kg.data?.concepts ?? [];
  const unlocked = pipeline.data?.generation_unlocked ?? false;

  const isGenerate = run?.job?.kind === "generate";
  const running = isGenerate && run?.job?.status === "running";

  const results = useMemo<Result[]>(() => {
    if (!isGenerate) return [];
    const fromResult = (run?.job?.result?.items ?? []) as Result[];
    if (fromResult.length > 0) return fromResult;
    return (run?.items ?? []).map((i) => ({
      item: i.item,
      item_type: i.item_type,
      thinking: i.thinking ?? undefined,
      checks: i.checks,
      retried: i.retried,
      saved_id: i.saved_id,
    }));
  }, [isGenerate, run]);

  const savedCount = results.filter((r) => r.saved_id).length;

  // What the run below actually asked for, read off the job and not off the form: the form
  // is only what is on screen right now, and a reload or a trip to another screen restarts
  // it at its defaults while the run survives in the store.
  const commission = useMemo(
    () => (isGenerate && run?.job ? fromParams(run.job.params) : null),
    [isGenerate, run],
  );

  // Each item becomes a row of «Mis variantes» the moment it validates; the archive is
  // told so that opening it during a run already lists what arrived.
  useEffect(() => {
    if (savedCount > 0) client.invalidateQueries({ queryKey: ["generations"] });
  }, [savedCount, client]);

  // A run that the guardrail stopped is not a generic failure: it is an answer about the
  // text in step 4, so the form comes back with that step's own message attached.
  const blocked = useMemo(() => {
    if (!isGenerate || run?.job?.status !== "failed") return null;
    const error = run?.job?.error ?? "";
    return error.includes(GUARDRAIL_ERROR) ? error.replace(/^\w+Error:\s*/, "") : null;
  }, [isGenerate, run]);

  // The form has to come back holding the text that was blocked, which it no longer does on
  // its own once the state and the run have drifted apart: the commission is the run's.
  useEffect(() => {
    if (!blocked) return;
    if (commission) setForm(commission);
    setEditing(true);
  }, [blocked]);

  useEffect(() => {
    if (running) setEditing(false);
  }, [running]);

  if (profileQuery.isLoading || kg.isLoading || pipeline.isLoading) {
    return <Skeleton className="h-96" />;
  }

  const launch = () => submit.mutate({ kind: "generate", params: { ...toParams(form) } });

  // The bar describes and repeats the commission that ran; only with no job to read it from
  // does it fall back to the form.
  const again = commission ?? form;
  const relaunch = () => submit.mutate({ kind: "generate", params: { ...toParams(again) } });

  // The collapsed bar re-runs the same parameters without reopening the form, so it has to
  // repeat the one precondition the form checks before it enables its own button.
  const canLaunch = unlocked && !offline && again.concepts.length > 0;

  const hasRun = isGenerate && (running || results.length > 0 || run?.job?.status === "failed");
  const collapsed = hasRun && !editing;

  const formPanel = (
    <div className="space-y-3">
      {hasRun && editing ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card px-3 py-2.5">
          <p className="min-w-0 flex-1 text-body text-muted-foreground">
            Parte del encargo anterior. Las variantes de abajo ya están guardadas: la nueva
            tanda las sustituye en pantalla, no en «Mis variantes».
          </p>
          <Button variant="ghost" size="sm" onClick={() => setForm(EMPTY_FORM)}>
            <Eraser />
            Empezar de cero
          </Button>
        </div>
      ) : null}
      <GenerateForm
        state={form}
        onChange={setForm}
        profile={profile}
        concepts={conceptList}
        graph={kgGraph.data}
        disabled={!unlocked || Boolean(offline)}
        running={Boolean(running)}
        pending={submit.isPending}
        error={submit.isError ? (submit.error as Error).message : null}
        blockedInstructions={blocked}
        onLaunch={launch}
        onCancel={() => run?.job && cancel.mutate(run.job.id)}
      />
    </div>
  );

  const runPane = run ? (
    <div className="space-y-4">
      <RunPanel run={run} running={Boolean(running)} profile={profile} />
      {results.length > 0 && profile ? (
        <Results results={results} profile={profile} run={run} savedCount={savedCount} />
      ) : null}
    </div>
  ) : null;

  return (
    <div className="space-y-5">
      <header className="flex items-center gap-2">
        <h1 className="font-display font-expanded text-display">Generar variantes</h1>
        <InfoHint label="Cómo se genera">
          Eliges qué se debe practicar —para ti o para tu clase— y las decisiones que el perfil
          deja en tus manos; el resto lo redacta el modelo, guiado por el grafo y por los
          ejemplos del banco. Cada variante validada se guarda sola en «Mis variantes».
        </InfoHint>
      </header>

      {/* Without an engine nothing is generated: the server refuses with a 503 and the whole form
          is disabled, instead of letting one press and getting a job error back. */}
      {unlocked && offline ? (
        <Alert tone="attention" title="Sin motor de inferencia">
          <p>{offline} Arráncalo y vuelve a intentarlo.</p>
        </Alert>
      ) : null}

      {!unlocked ? (
        <Alert tone="attention" title="Generación bloqueada">
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

      {isGenerate && run?.job?.status === "failed" && !blocked ? (
        <Alert tone="danger" title="La generación falló">
          <p>{run.job.error}</p>
        </Alert>
      ) : null}

      {collapsed ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card px-3 py-2.5">
            <p className="min-w-0 flex-1 truncate text-body text-muted-foreground">
              {summarize(again, profile)}
            </p>
            {running ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => run?.job && cancel.mutate(run.job.id)}
                disabled={cancel.isPending}
              >
                <Ban />
                Cancelar
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setForm(again);
                    setEditing(true);
                  }}
                >
                  <Pencil />
                  Cambiar el encargo
                </Button>
                <Button
                  size="sm"
                  onClick={relaunch}
                  disabled={!canLaunch || submit.isPending}
                  title={offline ?? undefined}
                >
                  {submit.isPending ? <Spinner /> : <Sparkles />}
                  {again.n === 1 ? "Generar otra" : `Generar otras ${again.n}`}
                </Button>
              </>
            )}
          </div>

          {runPane}
        </div>
      ) : (
        <div
          className={cn(
            hasRun
              ? "grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]"
              : "mx-auto w-full max-w-3xl",
          )}
        >
          {formPanel}
          {hasRun ? runPane : null}
        </div>
      )}
    </div>
  );
}

function Results({
  results,
  profile,
  run,
  savedCount,
}: {
  results: Result[];
  profile: ExemplarsProfile;
  run: RunView | null;
  savedCount: number;
}) {
  const requested = run?.job?.result?.requested;
  const produced = run?.job?.result?.produced;
  const asJson = JSON.stringify(
    results.map((r) => r.item),
    null,
    2,
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-body font-semibold">
          Resultados
          <span className="ml-2 font-normal text-muted-foreground nums">
            {results.length}
            {requested ? ` de ${requested}` : ""}
          </span>
        </h2>
        {produced !== undefined && requested !== undefined && produced < requested ? (
          <Badge variant="attention">
            generación parcial: {produced}/{requested}
          </Badge>
        ) : null}
        <div className="ml-auto flex gap-1">
          <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(asJson)}>
            <Copy />
            Copiar JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => download("items.json", asJson, "application/json")}
          >
            <Download />
            JSON
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => download("items.md", toMarkdown(results, profile), "text/markdown")}
          >
            <Download />
            Markdown
          </Button>
        </div>
      </div>

      {results.map((result, index) => (
        <ResultCard
          key={index}
          index={index + 1}
          item={result.item}
          itemType={result.item_type}
          thinking={result.thinking}
          checks={result.checks}
          retried={result.retried}
          profile={profile}
          saved={Boolean(result.saved_id)}
        />
      ))}

      {savedCount > 0 ? (
        <p className="text-small text-muted-foreground">
          {savedCount === 1 ? "Esta variante ya está" : `Estas ${savedCount} variantes ya están`}{" "}
          en{" "}
          <Link to="/perfil/variantes" className="text-primary underline-offset-4 hover:underline">
            Mis variantes
          </Link>
          .
        </p>
      ) : null}
    </div>
  );
}

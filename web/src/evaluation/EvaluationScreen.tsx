import { ArrowLeft, Clock, EyeOff, Plus, Scale } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ChainGate } from "@/components/ChainGate";
import { GuideLink } from "@/components/GuideLink";
import { InfoHint } from "@/components/ui/hint";
import { Alert, Progress, Skeleton, Spinner } from "@/components/ui/misc";
import { EMPTY_FORM, type FormState } from "@/features/generate/commission";
import { GenerateForm } from "@/features/generate/GenerateForm";
import { refusal, stillRefused } from "@/features/generate/screening";
import { ApiError } from "@/lib/api";
import { duration } from "@/lib/format";
import { isQueued, queuedLabel, waitOf, waitReason } from "@/lib/queue";
import { cn } from "@/lib/utils";
import type { RunView } from "@/state/runStore";
import {
  useElapsed,
  useOwnJobRun,
  useKg,
  useKgGraph,
  useLanes,
  usePipeline,
  useProfile,
  useQueuedNotice,
  useSplitEngine,
} from "@/state/queries";

import { toEvaluationParams } from "./commission";
import { CommissionStrip } from "./CommissionStrip";
import { CARDS, ComparisonGrid, columnsFor } from "./ComparisonGrid";
import { FairnessTable } from "./FairnessTable";
import { CROSS_EVALUATION } from "./config";
import { ProposalDialog } from "./ProposalDialog";
import { QueueTab } from "./QueueTab";
import { RevealPanel } from "./RevealPanel";
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
import { useT } from "@/lib/i18n";
import { CancelButton } from "@/components/CancelButton";

/**
 * Only the comparison THIS person has to judge.
 *
 * The run drawer is global, so a batch an administrator ordered from the panel arrives as
 * the active job like any other — and this screen used to take it. Stock is nobody's to
 * judge until it is assigned, so the flag the panel stamps on the job is what is filtered
 * on. Module-level so `useJobRun`'s memo does not re-run every render.
 */
const notStock = (run: RunView) => run.job?.params?.stock !== true;

/**
 * While it runs, the screen deliberately says less than the Generate screen does.
 *
 * The run drawer would give the blinding away — the token stream, the few-shot, the
 * logs — so the server does not publish any of it during an evaluation. Saying so out
 * loud matters: silence that is not explained reads as an app that has frozen. And a
 * comparison waiting its turn is exactly that silence: nothing is being written yet, so
 * it says "en cola" instead of counting proposals that are not being produced.
 */
function Running({
  run,
  queued,
  waiting,
  ahead,
}: {
  run: RunView | null;
  queued: boolean;
  waiting: string | null;
  ahead: string;
}) {
  const { t } = useT();
  const step = useMemo(() => run?.steps.find((s) => s.id === "eval.arms"), [run]);
  const elapsed = useElapsed(run?.job?.started_at ?? null, !queued);
  const done = step?.current ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-3 shadow-sm">
        {queued ? <Clock className="size-4 shrink-0 text-muted-foreground" /> : <Spinner />}
        <div className="min-w-0 flex-1">
          <p className="text-body font-medium">
            {queued ? ahead : t("eval.preparing")}
            {queued ? null : (
              <span className="ml-2 nums text-muted-foreground">
                {t("eval.doneOf", { n: done, total: CARDS })}
              </span>
            )}
          </p>
          <p className={cn("text-small text-muted-foreground", queued || "nums")}>
            {queued ? waiting : duration(elapsed)}
          </p>
        </div>
        {queued ? null : <Progress value={done} max={CARDS} className="hidden w-40 sm:block" />}
        <CancelButton run={run} />
      </div>

      <p className="flex items-start gap-1.5 text-small text-muted-foreground">
        <EyeOff className="mt-0.5 size-3.5 shrink-0" />
        {t("eval.blindNotice")}
      </p>

      {/* One placeholder per card the session will hold. Which two arms are being written
          is the seed's and never said here: a placeholder named after an arm would be the
          reveal before the cards. */}
      <div className={cn("grid items-stretch gap-4", columnsFor(CARDS))}>
        {Array.from({ length: CARDS }, (_, index) => index + 1).map((position) => (
          <div
            key={position}
            className="flex h-64 flex-col overflow-hidden rounded-xl border border-border bg-card"
          >
            <div className="flex items-center gap-2.5 border-b border-border px-3 py-2.5">
              <span className="flex size-8 items-center justify-center rounded-lg bg-muted font-mono text-heading text-muted-foreground">
                {letterFor(position)}
              </span>
              <span className="text-body text-muted-foreground">
                {t("grid.proposal", { letter: letterFor(position) })}
              </span>
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
 * The sub-tabs, in the order the work happens in.
 *
 * With cross evaluation off (`evaluation/config.ts`) there are two: ask for a comparison, and
 * read the ones you have already judged. The queue — what an administrator handed this
 * evaluator — comes first when it is on, because that is somebody else's work waiting;
 * with nobody handing anything over there is nothing to wait for, and a tab that is always
 * empty reads as a broken feature rather than an absent one.
 */
type Tab = "queue" | "compose" | "history";

export function EvaluationScreen() {
  const { plural, t } = useT();
  const tr = useT();
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
  const run = useOwnJobRun("evaluate", notStock);
  const lanes = useLanes();
  const split = useSplitEngine();
  // A comparison is launched through the evaluation's own mutation and not `useSubmitJob`, so
  // the one notice about waiting is asked for here rather than written a second time.
  const announce = useQueuedNotice();

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>(CROSS_EVALUATION ? "queue" : "compose");
  // Which proposal is open at reading size, by position; null while none is. It belongs
  // to the session, so changing session closes it.
  const [reading, setReading] = useState<number | null>(null);
  const detail = useEvaluation(sessionId);

  useEffect(() => {
    setReading(null);
  }, [sessionId]);

  const profile = profileQuery.data?.profile ?? null;
  const unlocked = pipeline.data?.generation_unlocked ?? false;
  const external = listing.data?.external;

  const status = run?.job?.status;
  const queued = isQueued(run?.job);
  const running = status === "running" || queued;
  const wait = waitOf(run?.job, lanes);

  // The job result carries the session id and nothing else — the proposals are fetched
  // separately, from the endpoint that knows what it is allowed to show.
  const producedId = run?.job?.result?.session_id as string | undefined;

  // ONLY A SESSION PRODUCED DURING THIS VISIT IS OPENED (2026-09-08, explicit user request).
  // The stream outlives the screen, so `useOwnJobRun` hands back the last finished run on
  // every mount and the screen used to reopen a comparison already judged an hour ago;
  // what was produced before this mount is "Mis evaluaciones"' business, and the screen
  // opens on the form. A run still going when the screen mounts is inherited: its
  // result arrives later and is this visit's.
  const alreadyProduced = useRef(producedId);
  useEffect(() => {
    if (producedId && producedId !== alreadyProduced.current) {
      setSessionId(producedId);
    }
  }, [producedId]);

  const blocked = useMemo(() => refusal(run?.job), [run]);

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
  // A student is not asked to write a commission WHILE SOMEBODY ELSE FILLS THEIR QUEUE:
  // the form speaks the system's vocabulary — concepts of the graph, a modality — and
  // theirs is the queue. With cross evaluation off nobody fills one, so withholding it
  // leaves a student on an empty "Mis sesiones" with no way to compare anything at all,
  // which is what it did: the flag hid the queue tab and this line hid the other one.
  const canCompose = CROSS_EVALUATION ? instruments?.profile !== "student" : true;

  const closeSession = () => {
    setSessionId(null);
  };

  // A comparison that is over has one honest way on: ordering the next one. Landing on
  // "Mis evaluaciones" left somebody looking at a table of what they had already judged,
  // one more click away from the only thing there is to do here.
  const orderAnother = () => {
    setSessionId(null);
    setTab("compose");
  };

  // Straight on to the next thing somebody handed over, which is what keeps a queue a
  // queue. With nothing left it lands on the form — or, for an evaluator who is not
  // offered one, on the list.
  const openNext = () => {
    const next = (queue?.items ?? []).find(
      (item) => !item.decided && !item.declined && item.id !== sessionId,
    );
    if (next) {
      setSessionId(next.id);
      return;
    }
    setSessionId(null);
    if (CROSS_EVALUATION) setTab("queue");
    else setTab(canCompose ? "compose" : "history");
  };

  const typeLabel = (key: string) => profile?.item_types?.[key]?.label || key;

  /**
   * The one way on from a finished comparison, as icon and label read off ONE choice.
   *
   * They are decided together because they are one statement. The header used to draw
   * `Plus` whatever the label said, so a session opened from "Mis evaluaciones" read
   * "+ Volver a la lista" — a plus sign on the one control that adds nothing; the foot
   * had the same defect for an evaluator who is not offered the form.
   */
  const wayOn = (kind: "queue" | "order" | "list") => {
    if (kind === "queue")
      return {
        icon: <Scale />,
        label: t("eval.nextInQueue", {
          pending: plural("eval.pendingCount", queue?.pending ?? 0),
        }),
      };
    if (kind === "order") return { icon: <Plus />, label: t("eval.orderAnother") };
    return { icon: <ArrowLeft />, label: t("eval.backToList") };
  };

  // The header closes the session; the foot opens whatever comes next. Both land on the
  // form when there is one to land on, and on the list when there is not.
  const headerWay = wayOn(tab === "compose" && canCompose ? "order" : "list");
  const footWay = wayOn(queue && queue.pending > 0 ? "queue" : canCompose ? "order" : "list");

  const TABS: { id: Tab; label: string; count?: number; attention?: boolean }[] = [
    ...(CROSS_EVALUATION
      ? [
          {
            id: "queue" as Tab,
            label: t("eval.tab.queue"),
            count: queue?.pending ?? 0,
            attention: true,
          },
        ]
      : []),
    ...(canCompose ? [{ id: "compose" as Tab, label: t("eval.tab.compose") }] : []),
    { id: "history", label: t("eval.tab.history"), count: listing.data?.total ?? 0 },
  ];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
        {/* The (i) rides on the TITLE and the guide link comes after it: the hint is one
            sentence about this screen, and a destination reads as the end of a line rather
            than as something with a glyph hanging off it. */}
        <h1 className="w-full font-display font-expanded text-display">
          {t("eval.title")}
          <InfoHint className="ml-2 align-middle" label={t("eval.whatFor")}>
            {t("eval.whatFor.body")}
          </InfoHint>
        </h1>
        <GuideLink slug="evaluate" />
        {/* The button is named after where it LANDS: closing a session leaves you on the
            tab you came from, and with the form as the default that was the one control on
            the screen reading "Volver a la lista" while returning to the form. */}
        {showComparison ? (
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={tab === "compose" && canCompose ? orderAnother : closeSession}
          >
            {headerWay.icon}
            {headerWay.label}
          </Button>
        ) : null}
      </header>

      {/* The tabs disappear while a session is open, and that is deliberate: a comparison
          is one task with one way out, and offering three destinations beside the cards
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
                    "inline-grid h-[18px] min-w-5 place-items-center px-1.5 text-[12px] font-semibold nums",
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
        <ChainGate title={t("eval.blocked")} stages={pipeline.data?.stages ?? []} />
      ) : null}

      {status === "failed" && !blocked ? (
        <Alert tone="danger" title={t("eval.failed")}>
          <p>{run?.job?.error}</p>
        </Alert>
      ) : null}

      {external && !external.configured ? (
        <Alert tone="attention" title={t("eval.externalUnset")}>
          <p>{external.reason}</p>
          <p className="mt-1 text-muted-foreground">{t("eval.externalUnset.body")}</p>
        </Alert>
      ) : null}

      {running ? (
        <Running
          run={run}
          queued={queued}
          waiting={wait ? waitReason(wait, split, tr) : t("eval.waitingTurn")}
          ahead={queuedLabel(wait, tr)}
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
        <div className="mx-auto w-full max-w-3xl space-y-4">
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
            blockedInstructions={stillRefused(run?.job, form.instructions)}
            variant="evaluation"
            footnote={<FairnessTable />}
            onLaunch={() =>
              launch.mutate(toEvaluationParams(form), {
                onSuccess: ({ job }) => announce(job),
              })
            }
            run={run ?? null}
          />
        </div>
      ) : null}

      {tab === "history" && !showComparison && !running && listing.data ? (
        <SessionsTable
          sessions={listing.data.sessions}
          total={listing.data.total}
          typeLabel={typeLabel}
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
          <CommissionStrip session={session} profile={profile} />

          {session.revealed ? (
            <RevealPanel
              detail={detail.data!}
              profile={profile}
              instruments={instruments}
              pending={rate.isPending}
              onSave={(rating) => rate.mutate({ id: session.id, payload: rating })}
              onSkip={openNext}
              onRead={setReading}
            />
          ) : (
            <ComparisonGrid
              positions={positions}
              profile={profile}
              itemType={session.item_type}
              triage={session.triage}
              instruments={instruments}
              onTriage={(position, value) =>
                triage.mutate({ id: session.id, payload: { position, value } })
              }
              onChoose={(choice, comment) =>
                choose.mutate({ id: session.id, payload: { choice, comment } })
              }
              onDecline={() => decline.mutate({ id: session.id, payload: {} })}
              onRead={setReading}
              pending={choose.isPending || triage.isPending || decline.isPending}
            />
          )}

          {session.revealed ? (
            <Button variant="outline" className="w-full" onClick={openNext}>
              {footWay.icon}
              {footWay.label}
            </Button>
          ) : null}

          <ProposalDialog
            position={positions.find((p) => p.position === reading) ?? null}
            positions={positions}
            session={session}
            profile={profile}
            instruments={instruments}
            triage={session.triage}
            pending={triage.isPending}
            onTriage={(position, value) =>
              triage.mutate({ id: session.id, payload: { position, value } })
            }
            onMove={setReading}
            onClose={() => setReading(null)}
          />
        </div>
      ) : null}
    </div>
  );
}

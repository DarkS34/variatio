import { Copy, Download, Eraser, Pencil } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChainGate } from "@/components/ChainGate";
import { GuideLink } from "@/components/GuideLink";
import { InfoHint } from "@/components/ui/hint";
import { Alert, Skeleton } from "@/components/ui/misc";
import { isLive, isQueued, waitOf, waitReason } from "@/lib/queue";
import { Link } from "@/lib/router";
import type { ExemplarsProfile, ItemChecks } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { RunView } from "@/state/runStore";
import {
  useEngineOffline,
  useOwnJobRun,
  useKg,
  useKgGraph,
  useLanes,
  usePipeline,
  useProfile,
  useSplitEngine,
  useSubmitJob,
} from "@/state/queries";

import { EMPTY_FORM, fromParams, toParams, type FormState } from "./commission";
import { takeDraft } from "./draft";
import { GenerateForm, summarize } from "./GenerateForm";
import { adjacency, covered } from "./prerequisites";
import { ResultCard, download, toMarkdown } from "./ResultCard";
import { RunPanel } from "./RunPanel";
import { RunStrip, useRunDetail } from "./RunStrip";
import { refusal, stillRefused } from "./screening";
import { useT } from "@/lib/i18n";

interface Result {
  item: Record<string, unknown>;
  item_type?: string;
  checks?: ItemChecks | null;
  retried?: number;
  saved_id?: number | null;
}

export function GenerateScreen() {
  const tr = useT();
  const { t } = tr;
  const pipeline = usePipeline();
  const profileQuery = useProfile();
  const kg = useKg();
  const kgGraph = useKgGraph();
  const submit = useSubmitJob();
  const offline = useEngineOffline();
  // ITS OWN run, by kind, and never "whatever the machine is doing": two lanes mean a build
  // can be running beside this generation, and the screen used to take whichever job the
  // stream had heard from last and then find no items in it.
  //
  // AND ITS OWN VISIT. The stream outlives the screen, and a reload replays it whole, so
  // "mi última generación" opened this page on a batch finished an hour ago with the form
  // collapsed behind it: work already collected, in the one place one comes to ask for
  // more. A finished batch belongs to the visit that ran it, and to "Mis variantes"
  // afterwards; one still going is adopted whenever it started, because a made commission
  // has to stay on screen or the form would offer to queue a second copy of it — leaving
  // and coming back mid-generation must not lose it. Membership only ever grows, so what
  // is being watched does not vanish at the moment it finishes.
  const [visit] = useState(() => new Set<string>());
  const launched = submit.data?.job.id ?? null;
  const ofThisVisit = useMemo(
    () => (candidate: RunView) => {
      if (candidate.jobId === launched || isLive(candidate.job)) visit.add(candidate.jobId);
      return visit.has(candidate.jobId);
    },
    [visit, launched],
  );
  const run = useOwnJobRun("generate", ofThisVisit);
  const lanes = useLanes();
  const split = useSplitEngine();
  const client = useQueryClient();

  // A draft left by "generate more like this one" in the saved list is the form's start;
  // it is read once and consumed, so a reload starts clean. It also opens the form: a run
  // from before is still in the store, and its collapsed bar would hide the very commission
  // one came here to launch.
  const [draft] = useState(takeDraft);
  const [form, setForm] = useState<FormState>(draft ?? EMPTY_FORM);
  const [editing, setEditing] = useState(Boolean(draft));

  const profile = profileQuery.data?.profile ?? null;
  const conceptList = kg.data?.concepts ?? [];
  const unlocked = pipeline.data?.generation_unlocked ?? false;

  const status = run?.job?.status;
  const running = status === "running";
  // A commission that is waiting its turn has already been made. Treating it as "nothing
  // is happening" left the form open over it, so pressing again queued a second copy of
  // the same batch behind the first — which is the bug, not the wait.
  const queued = isQueued(run?.job);
  const active = running || queued;
  const wait = waitOf(run?.job, lanes);
  const detail = useRunDetail(running);

  const results = useMemo<Result[]>(() => {
    if (!run) return [];
    const fromResult = (run?.job?.result?.items ?? []) as Result[];
    if (fromResult.length > 0) return fromResult;
    return (run?.items ?? []).map((i) => ({
      item: i.item,
      item_type: i.item_type,
      checks: i.checks,
      retried: i.retried,
      saved_id: i.saved_id,
    }));
  }, [run]);

  const savedCount = results.filter((r) => r.saved_id).length;

  // What the run below actually asked for, read off the job and not off the form: the form
  // is only what is on screen right now, and a reload or a trip to another screen restarts
  // it at its defaults while the run survives in the store.
  const commission = useMemo(
    () => (run?.job ? fromParams(run.job.params) : null),
    [run],
  );

  // Going back to the form takes the previous batch off the screen: both ways out open a
  // NEW commission, so what stayed below was the answer to an old one, over the form being
  // filled in. Nothing is lost — every item saves itself as it validates, and "Mis
  // ejercicios" is where they are read. Cleared on launch, when there is something to show
  // again.
  //
  // It belongs with the rest of the hooks and not beside the two buttons that move it:
  // below the loading `return` it is a conditional hook, and React unmounts the whole
  // screen with "Rendered more hooks than during the previous render".
  const [dismissed, setDismissed] = useState(false);

  // Each item becomes a row of "Mis variantes" the moment it validates; the archive is
  // told so that opening it during a run already lists what arrived.
  useEffect(() => {
    if (savedCount > 0) client.invalidateQueries({ queryKey: ["generations"] });
  }, [savedCount, client]);

  // A run that the guardrail or the judge stopped is not a generic failure: it is an
  // answer about the text in the instructions step, so the form comes back with that
  // step's own message attached and its launch button locked until the text changes.
  const blocked = useMemo(() => refusal(run?.job), [run]);

  // The form has to come back holding the text that was blocked, which it no longer does on
  // its own once the state and the run have drifted apart: the commission is the run's.
  useEffect(() => {
    if (!blocked) return;
    if (commission) setForm(commission);
    setEditing(true);
  }, [blocked]);

  useEffect(() => {
    if (active) setEditing(false);
  }, [active]);

  if (profileQuery.isLoading || kg.isLoading || pipeline.isLoading) {
    return <Skeleton className="h-96" />;
  }

  // The coverage travels CLOSED, as the form counts it and as `server/curriculum.resolve`
  // would close it anyway: this way the bar under the result, which reads the request back,
  // says the same number the button said before launching.
  const launch = () => {
    setDismissed(false);
    submit.mutate({
      kind: "generate",
      params: {
        ...toParams({ ...form, curriculum: covered(adjacency(kgGraph.data), form.curriculum) }),
      },
    });
  };

  // The bar describes the commission that ran; only with no job to read it from does it
  // fall back to the form.
  const again = commission ?? form;

  // Two ways on, both prominent, and they are the choice a person actually faces once a
  // batch has landed: vary THIS commission, or start from an empty form. Repeating one
  // unchanged is the first of those with nothing touched.
  const vary = () => {
    setForm(again);
    setEditing(true);
    setDismissed(true);
  };
  const fromScratch = () => {
    setForm(EMPTY_FORM);
    setEditing(true);
    setDismissed(true);
  };

  const hasRun =
    !dismissed && Boolean(run) && (active || results.length > 0 || status === "failed");
  const collapsed = hasRun && !editing;

  const formPanel = (
    <div className="space-y-3">
      <GenerateForm
        state={form}
        onChange={setForm}
        profile={profile}
        concepts={conceptList}
        graph={kgGraph.data}
        disabled={!unlocked || Boolean(offline)}
        running={active}
        pending={submit.isPending}
        error={submit.isError ? (submit.error as Error).message : null}
        blockedInstructions={stillRefused(run?.job, form.instructions)}
        onLaunch={launch}
        run={run ?? null}
      />
    </div>
  );

  // The commission sits directly above what it asked for: it is the heading of the result
  // and not a line about the run, so nothing — bar, clock, disclosure — comes between.
  const commissionBar = (
    <div className="space-y-3 rounded-xl border border-border bg-card px-3 py-2.5">
      <p className="truncate text-body text-muted-foreground">{summarize(again, profile, tr)}</p>
      {active ? null : (
        <div className="flex flex-wrap gap-2">
          <Button variant="attention" onClick={vary} disabled={!unlocked || Boolean(offline)}>
            <Pencil />
            {t("generate.vary")}
          </Button>
          <Button variant="outline" onClick={fromScratch} disabled={!unlocked || Boolean(offline)}>
            <Eraser />
            {t("generate.startOver")}
          </Button>
        </div>
      )}
    </div>
  );

  const runPane = run ? (
    <div className="space-y-4">
      <RunStrip
        run={run}
        running={running}
        queued={queued}
        wait={wait}
        expanded={detail.expanded}
        onToggle={detail.toggle}
      >
        <RunPanel
          run={run}
          running={running}
          waiting={queued ? (wait ? waitReason(wait, split, tr) : t("generate.queued")) : null}
          profile={profile}
        />
      </RunStrip>
      {collapsed ? commissionBar : null}
      {results.length > 0 && profile ? (
        <Results results={results} profile={profile} run={run} savedCount={savedCount} />
      ) : null}
    </div>
  ) : null;

  return (
    <div className="space-y-5">
      <header className="space-y-1.5">
        <div className="flex items-center gap-2">
          <h1 className="font-display font-expanded text-display">{t("generate.title")}</h1>
          <InfoHint label={t("generate.howItWorks")}>
            {t("generate.howItWorks.body")}
          </InfoHint>
        </div>
        <GuideLink slug="generate" />
      </header>

      {/* Without an engine nothing is generated: the server refuses with a 503 and the whole form
          is disabled, instead of letting one press and getting a job error back. */}
      {unlocked && offline ? (
        <Alert tone="attention" title={t("generate.noEngine")}>
          <p>{t("generate.noEngineBody", { reason: offline })}</p>
        </Alert>
      ) : null}

      {!unlocked ? (
        <ChainGate title={t("generate.blocked")} stages={pipeline.data?.stages ?? []} />
      ) : null}

      {status === "failed" && !blocked ? (
        <Alert tone="danger" title={t("generate.failed")}>
          <p>{run?.job?.error}</p>
        </Alert>
      ) : null}

      {/* ONE COLUMN, AT A READING WIDTH.
          This screen used to split into two once anything had run — the five-step form on
          the left, the run and the items on the right at 1.1fr — so the thing you came for
          arrived at half the width of the window, beside a form you had already filled in.
          The commission collapses to a line, the run to a strip, and what is left is the
          items, at a width you can read a statement and a block of code in. */}
      <div className="mx-auto w-full max-w-4xl space-y-4">
        {collapsed ? null : formPanel}
        {hasRun ? runPane : null}
      </div>
    </div>
  );
}

/** The three ways out of here, behind the one question they answer. */
function ExportMenu({
  className,
  onCopy,
  onJson,
  onMarkdown,
}: {
  className?: string;
  onCopy: () => void;
  onJson: () => void;
  onMarkdown: () => void;
}) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!holder.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const entries: { label: string; icon: typeof Copy; run: () => void }[] = [
    { label: t("generations.copyJson"), icon: Copy, run: onCopy },
    { label: t("generate.downloadJson"), icon: Download, run: onJson },
    { label: t("generate.downloadMarkdown"), icon: Download, run: onMarkdown },
  ];

  return (
    <div className={cn("relative", className)} ref={holder}>
      <Button
        variant="outline"
        size="sm"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((was) => !was)}
      >
        <Download />
        {t("generate.export")}
      </Button>
      {open ? (
        <div
          role="menu"
          className="animate-fade-in absolute right-0 z-20 mt-1 min-w-48 rounded-lg border border-border bg-popover p-1 shadow-overlay"
        >
          {entries.map((entry) => (
            <button
              key={entry.label}
              role="menuitem"
              onClick={() => {
                entry.run();
                setOpen(false);
              }}
              className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-left text-body transition-colors hover:bg-accent"
            >
              <entry.icon className="size-4 shrink-0 text-muted-foreground" />
              {entry.label}
            </button>
          ))}
        </div>
      ) : null}
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
  const { t, plural } = useT();
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
          {t("generate.results")}
          <span className="ml-2 font-normal text-muted-foreground nums">
            {results.length}
            {requested ? t("generate.ofRequested", { n: requested }) : ""}
          </span>
        </h2>
        {produced !== undefined && requested !== undefined && produced < requested ? (
          <Badge variant="attention">
            {t("generate.partial", { produced, requested })}
          </Badge>
        ) : null}
        {/* One control where there were three. "Copiar JSON", "JSON" and "Markdown" sat in
            a row above the items at the same weight as everything else on the line, and the
            three of them are one question — how do I take this out of here — asked once. */}
        <ExportMenu
          className="ml-auto"
          onCopy={() => navigator.clipboard.writeText(asJson)}
          onJson={() => download("items.json", asJson, "application/json")}
          onMarkdown={() => download("items.md", toMarkdown(results, profile, t), "text/markdown")}
        />
      </div>

      {results.map((result, index) => (
        <ResultCard
          key={index}
          index={index + 1}
          item={result.item}
          itemType={result.item_type}
          checks={result.checks}
          retried={result.retried}
          profile={profile}
          saved={Boolean(result.saved_id)}
        />
      ))}

      {savedCount > 0 ? (
        <p className="text-small text-muted-foreground">
          {plural("generate.savedNotice", savedCount)}{" "}
          <Link to="/account/variants" className="text-primary underline-offset-4 hover:underline">
            {t("menu.savedVariants")}
          </Link>
          .
        </p>
      ) : null}
    </div>
  );
}
